"""Windows 专属「CUDA 加速套件」的下载、校验、安装与注入。

本模块由 ASRbox ``backend/services/cuda_kit.py``（配合
``backend/pyi_rth_cuda_kit.py`` / ``backend/server.py::_maybe_inject_cuda_kit``）
移植而来，保持相同的数据流与安全约束，按 YuE2 的目录与状态机裁剪：

- 数据流：读 ``tools/cuda_kit.json`` 里的固定 GitHub Release manifest（HTTPS +
  ``github.com`` 白名单，重定向仅允许 ``*.githubusercontent.com``）→ 逐卷 Range
  下载（续传/取消/进度，每卷校验 sha256）→ 拼接并校验 zip_sha256 → 安全解压
  （拒绝绝对路径、``..``、反斜杠、盘符）→ 逐文件 sha256 校验 → 原子替换到
  ``<KIT_ROOT>/kit`` 并写入 manifest → job completed；
- 目录：``KIT_ROOT = <repo>/web/data/cuda-kit``（``web/data/`` 已被 .gitignore
  忽略），``kit/`` 是安装后的注入目标，``downloads/`` 是下载暂存，
  ``state.json`` 记录最近一次任务状态（进程重启后恢复展示）；
- 注入：``web/server.py`` 必须在导入 torch 之前调用 :func:`maybe_inject`，把 kit
  目录插到 ``sys.path`` 最前；Windows 上再把 ``torch/lib`` 加入 DLL 搜索目录；
- 状态机：``not_downloaded`` / ``downloading``（job.status=running）/
  ``ready``（installed 且当前进程未启用，需重启）/ ``enabled``（本进程 torch 来自
  kit 且 CUDA 可用）/ ``invalidated``（manifest 的 torch 版本与当前应用不一致）；
- 与 ASRbox 的差异：不设「启用开关」（安装即待重启生效、移除即回退 CPU），不引入
  httpx/ASRboxError 等第三方或项目内依赖——只用标准库，由 ``status()`` 返回的
  扁平字段供 server.py 组合模型页数据。

注意：本模块是「Windows 专属能力」；非 Windows 上 ``SUPPORTED`` 为 False，
``status()`` 返回 ``supported=False``，下载入口直接报错。测试通过 monkeypatch
``KIT_ROOT`` / ``SUPPORTED`` / ``_default_fetch`` 在任意平台覆盖全流程。
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from typing import Any, Callable
import urllib.error
import urllib.parse
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]

# 运行期数据目录：kit 安装到 <KIT_ROOT>/kit，下载暂存在 <KIT_ROOT>/downloads。
KIT_ROOT = ROOT / "web" / "data" / "cuda-kit"
KIT_DIR = KIT_ROOT / "kit"
KIT_DIR_NAME = "kit"
DOWNLOADS_DIR_NAME = "downloads"
STATE_FILENAME = "state.json"

# tools/cuda_kit.json 随包分发，固定 manifest URL 与期望 torch 版本/tag。
CONFIG_FILE = ROOT / "tools" / "cuda_kit.json"

# 导入时的默认路径，用于识别宿主/测试覆盖了 KIT_ROOT 还是 KIT_DIR（见 kit_root()）。
_DEFAULT_KIT_ROOT = KIT_ROOT
_DEFAULT_KIT_DIR = KIT_DIR

MANIFEST_NAME = "cuda-kit-manifest.json"
LOCAL_ZIP_NAME = "kit.zip"
EXTRACT_DIR_NAME = "extract"

PART_NAME_PATTERN = re.compile(r"^yue2-cuda-kit-windows-x64\.zip\.part\d+$")
GITHUB_HOST = "github.com"
# GitHub Release 资产会 302 到 objects.githubusercontent.com，属于 GitHub 自有域名：
# 初始 URL 固定为配置里的 github.com release 路径，重定向目标只允许该后缀。
REDIRECT_HOST_SUFFIX = ".githubusercontent.com"
MAX_REDIRECTS = 5
DOWNLOAD_CHUNK_BYTES = 1024 * 1024
EXTRACT_CHUNK_BYTES = 4 * 1024 * 1024
FETCH_TIMEOUT_SECONDS = 60

SUPPORTED = sys.platform == "win32"

PHASE_IDLE = "idle"
PHASE_MANIFEST = "manifest"
PHASE_PARTS = "parts"
PHASE_VERIFY = "verify"
PHASE_EXTRACT = "extract"
PHASE_VERIFY_FILES = "verify_files"

_IDLE_JOB: dict[str, Any] = {
    "status": "idle",
    "phase": PHASE_IDLE,
    "current_part": None,
    "parts_total": 0,
    "downloaded_bytes": 0,
    "total_bytes": 0,
    "error": None,
}

_job_lock = threading.Lock()
_cancel_event = threading.Event()
_job: dict[str, Any] = dict(_IDLE_JOB)
_state_recovered = False

_gpu_lock = threading.Lock()
_gpu_started = False
_gpu_result: bool | None = None

_size_cache: int | None = None

_inject_lock = threading.Lock()
_dll_handles: list[Any] = []
_injected_dll_dirs: set[str] = set()


class CudaKitError(RuntimeError):
    """CUDA 套件下载/校验/安装失败。"""


class CudaKitCancelled(CudaKitError):
    """用户取消了 CUDA 套件下载。"""


# ---------------------------------------------------------------------------
# 路径与配置
# ---------------------------------------------------------------------------


def kit_root() -> Path:
    """套件数据根目录。

    默认是 ``KIT_ROOT``；宿主/测试也可以只覆盖 ``KIT_DIR``（kit 安装目录），
    此时把它的父目录当作根目录，避免 downloads/state.json 落回仓库真实目录。
    """
    root = Path(KIT_ROOT)
    if root != _DEFAULT_KIT_ROOT:
        return root
    configured_kit = Path(KIT_DIR)
    if configured_kit != _DEFAULT_KIT_DIR:
        return configured_kit.parent
    return root


def kit_dir() -> Path:
    """安装后的 kit 目录；``maybe_inject`` 注入的就是它。"""
    configured_kit = Path(KIT_DIR)
    if configured_kit != _DEFAULT_KIT_DIR:
        return configured_kit
    return kit_root() / KIT_DIR_NAME


def downloads_dir() -> Path:
    """下载暂存目录（分卷、manifest、拼接中的 zip）。"""
    return kit_root() / DOWNLOADS_DIR_NAME


def _state_path() -> Path:
    return kit_root() / STATE_FILENAME


def _installed_manifest_path() -> Path:
    return kit_dir() / MANIFEST_NAME


def _on_windows() -> bool:
    """运行期平台判断；抽成函数便于测试在非 Windows 主机覆盖 win32 分支。"""
    return sys.platform == "win32"


def _load_config() -> dict[str, Any]:
    """读取 tools/cuda_kit.json；缺失/损坏时抛 CudaKitError。"""
    try:
        payload = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CudaKitError(f"无法读取 CUDA 套件配置 {CONFIG_FILE}：{exc}") from exc
    if not isinstance(payload, dict):
        raise CudaKitError("CUDA 套件配置不是 JSON 对象")
    return payload


def manifest_url() -> str:
    """从配置读出并校验 manifest URL（HTTPS + github.com）。"""
    url = _load_config().get("manifest_url")
    if not isinstance(url, str) or not url:
        raise CudaKitError("tools/cuda_kit.json 缺少 manifest_url")
    _validate_release_url(url)
    if not urllib.parse.urlparse(url).path.endswith("/" + MANIFEST_NAME):
        raise CudaKitError(f"CUDA 套件 manifest URL 必须以 /{MANIFEST_NAME} 结尾：{url!r}")
    kit_tag = _load_config().get("kit_release_tag")
    if isinstance(kit_tag, str) and kit_tag:
        if f"/download/{kit_tag}/" not in urllib.parse.urlparse(url).path:
            raise CudaKitError(f"manifest URL 与 kit_release_tag（{kit_tag}）不一致：{url!r}")
    return url


def part_url(part_name: str) -> str:
    """由 manifest URL 推导分卷 URL，并校验分卷名格式。"""
    if not isinstance(part_name, str) or not PART_NAME_PATTERN.fullmatch(part_name):
        raise CudaKitError(f"拒绝非预期的 CUDA 套件分卷名：{part_name!r}")
    url = f"{manifest_url().rsplit('/', 1)[0]}/{part_name}"
    _validate_release_url(url)
    return url


def _validate_release_url(url: str) -> None:
    """下载入口只接受 HTTPS 的 github.com 地址。"""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https":
        raise CudaKitError(f"CUDA 套件下载仅允许 HTTPS：{url!r}")
    if (parsed.hostname or "").lower() != GITHUB_HOST:
        raise CudaKitError(f"CUDA 套件下载仅限 {GITHUB_HOST}：{url!r}")


def _validate_redirect_url(url: str) -> str:
    """重定向目标只允许 github.com 或 *.githubusercontent.com（且必须 HTTPS）。"""
    parsed = urllib.parse.urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or (host != GITHUB_HOST and not host.endswith(REDIRECT_HOST_SUFFIX)):
        raise CudaKitError(f"拒绝 CUDA 套件下载重定向到不可信地址：{url!r}")
    return url


# ---------------------------------------------------------------------------
# 原子写 / 状态 / 任务快照
# ---------------------------------------------------------------------------


def _write_bytes_atomic(path: Path, data: bytes) -> None:
    """同目录临时文件 + os.replace，避免读到半截文件。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    _write_bytes_atomic(path, text.encode("utf-8"))


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _write_state(payload: dict[str, Any]) -> None:
    _write_json_atomic(_state_path(), payload)


def _set_job(persist: bool = True, **updates: Any) -> None:
    """更新任务快照；先落盘再让 current_job() 的读者看到，保证恢复语义。"""
    with _job_lock:
        _job.update(updates)
        payload = dict(_job)
        if persist:
            _write_state(payload)


def _bump_downloaded(delta_bytes: int) -> None:
    if delta_bytes <= 0:
        return
    with _job_lock:
        _job["downloaded_bytes"] = int(_job.get("downloaded_bytes") or 0) + delta_bytes


def _recover_state_locked() -> None:
    """一次性的 state.json 恢复：上次进程里的 running 任务视为失败/中断。"""
    global _job, _state_recovered
    if _state_recovered:
        return
    _state_recovered = True
    payload = _read_json(_state_path())
    if not isinstance(payload, dict) or "status" not in payload:
        return
    recovered = {**_IDLE_JOB, **payload}
    if recovered.get("status") == "running":
        recovered.update(
            status="failed",
            current_part=None,
            error="上次 CUDA 套件下载被应用重启中断，请重新下载",
        )
        _job = recovered
        _write_state(dict(recovered))
    elif recovered.get("status") in {"completed", "failed", "cancelled"}:
        _job = recovered


def current_job() -> dict[str, Any]:
    """返回当前下载任务快照（无任务时 status=idle）。"""
    with _job_lock:
        _recover_state_locked()
        return dict(_job)


def download_active() -> bool:
    return current_job().get("status") == "running"


# ---------------------------------------------------------------------------
# GPU 探测（后台线程 + 缓存，不阻塞状态接口）
# ---------------------------------------------------------------------------


def _detect_nvidia_gpu() -> bool:
    """有界 nvidia-smi 探测：驱动可见 NVIDIA GPU 时返回 True。"""
    kwargs: dict[str, Any] = {"capture_output": True, "timeout": 5}
    if _on_windows():
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        result = subprocess.run(["nvidia-smi", "-L"], **kwargs)
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0 and b"GPU" in (result.stdout or b"")


def _gpu_detected_cached() -> bool | None:
    """NVIDIA 显卡探测结果；首次调用拉起后台线程并返回 None。

    仅 Windows 有意义（其他平台恒定 None）；结果（包括 False=没装驱动）
    由缓存提供，避免每次状态查询都启动子进程。
    """
    global _gpu_started, _gpu_result
    if not SUPPORTED:
        return None
    with _gpu_lock:
        if _gpu_started:
            return _gpu_result
        _gpu_started = True

    def detect() -> None:
        global _gpu_result
        try:
            detected = _detect_nvidia_gpu()
        except Exception:  # noqa: BLE001 - 探测绝不能拖垮状态接口
            detected = False
        with _gpu_lock:
            _gpu_result = detected

    threading.Thread(target=detect, daemon=True, name="cuda-kit-gpu-detect").start()
    return None


def redetect() -> dict[str, Any]:
    """清空 GPU 探测缓存并立即返回状态（新探测仍在后台进行）。"""
    global _gpu_started, _gpu_result
    with _gpu_lock:
        # 正在进行的探测保留（不重复拉起线程），只重置已完成/未开始的状态。
        if not (_gpu_started and _gpu_result is None):
            _gpu_started = False
            _gpu_result = None
    return status()


# ---------------------------------------------------------------------------
# torch 版本、kit 就位判断与注入
# ---------------------------------------------------------------------------


def _current_torch_version() -> str | None:
    """当前环境的 torch 版本；不为此导入 torch（启动阶段可能还没导入）。

    优先用 importlib.metadata 读已安装 dist-info；读不到再看 sys.modules 中已
    导入的 torch。拿不到返回 None（maybe_inject 会按「版本未知」放行）。
    """
    try:
        from importlib import metadata

        return metadata.version("torch")
    except Exception:  # noqa: BLE001 - 未安装/元数据损坏都按未知处理
        pass
    torch_module = sys.modules.get("torch")
    version = getattr(torch_module, "__version__", None) if torch_module is not None else None
    return str(version) if version else None


def _base_version(version: str) -> str:
    """去掉本地版本后缀：``2.10.0+cu128`` 与 ``2.10.0`` 视为同一版本。"""
    return str(version).split("+", 1)[0].strip()


def _read_installed_manifest() -> dict[str, Any] | None:
    payload = _read_json(_installed_manifest_path())
    return payload if isinstance(payload, dict) else None


def _kit_present() -> bool:
    """kit 是否就位：判据是 torch 包本体（manifest 缺失时仍视为已安装）。"""
    return (kit_dir() / "torch" / "__init__.py").is_file()


def _torch_from_kit(torch_module: Any) -> bool:
    """判断已导入的 torch 是否来自 kit 目录。"""
    torch_file = getattr(torch_module, "__file__", None)
    if not isinstance(torch_file, str) or not torch_file:
        return False
    try:
        torch_path = os.path.normcase(str(Path(torch_file).resolve()))
        kit_path = os.path.normcase(str(kit_dir().resolve()))
    except OSError:
        return False
    return torch_path.startswith(kit_path + os.sep)


def _process_torch_enabled() -> bool:
    """当前进程 torch 来自 kit 且 CUDA 可用；torch 未导入时恒 False（不主动导入）。"""
    torch_module = sys.modules.get("torch")
    if torch_module is None or not _torch_from_kit(torch_module):
        return False
    try:
        return bool(torch_module.cuda.is_available())
    except Exception:  # noqa: BLE001 - CUDA 状态探测失败按未启用处理
        return False


def _torch_version_matches(kit_manifest: dict[str, Any] | None) -> bool:
    """kit manifest 的 torch 主版本与当前 torch 是否一致（未知时按一致处理）。"""
    if not isinstance(kit_manifest, dict):
        return True
    kit_torch = str(kit_manifest.get("torch_version") or "")
    current_torch = _current_torch_version()
    if not kit_torch or not current_torch:
        return True
    return _base_version(kit_torch) == _base_version(current_torch)


def maybe_inject() -> bool:
    """把已安装的 kit 注入当前进程（必须在 ``import torch`` 之前调用）。

    条件：``<kit>/torch/__init__.py`` 存在，且 manifest 的 torch 主版本与当前
    环境一致（版本未知时放行）。满足时 ``sys.path.insert(0, kit_dir)``；Windows
    上再把 ``torch/lib`` 加入 DLL 搜索目录。幂等：重复调用不会重复插入路径或
    DLL 目录，不会导入 torch。返回是否注入。
    """
    kit = kit_dir()
    if not (kit / "torch" / "__init__.py").is_file():
        return False
    if not _torch_version_matches(_read_installed_manifest()):
        print(
            "CUDA 加速套件的 torch 版本与当前应用不一致，已忽略注入；"
            "请移除后在模型页重新下载。",
            file=sys.stderr,
        )
        return False

    inserted = False
    with _inject_lock:
        kit_text = str(kit)
        if kit_text not in sys.path:
            sys.path.insert(0, kit_text)
            inserted = True
        torch_lib = kit / "torch" / "lib"
        if _on_windows() and torch_lib.is_dir():
            add_dll_directory = getattr(os, "add_dll_directory", None)
            torch_lib_text = str(torch_lib)
            if callable(add_dll_directory) and torch_lib_text not in _injected_dll_dirs:
                try:
                    # 句柄必须保活，否则 DLL 目录可能在 GC 时被移除。
                    _dll_handles.append(add_dll_directory(torch_lib_text))
                    _injected_dll_dirs.add(torch_lib_text)
                except OSError as exc:
                    print(f"无法把 {torch_lib} 加入 DLL 搜索目录：{exc}", file=sys.stderr)
    if inserted:
        print(f"CUDA 加速套件已注入：{kit}", file=sys.stderr)
    return True


# ---------------------------------------------------------------------------
# manifest 校验
# ---------------------------------------------------------------------------


def _looks_like_sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(
        char in "0123456789abcdef" for char in value.lower()
    )


def _safe_relative_path(value: Any) -> Path:
    """把 manifest/zip 里的相对路径转成安全 Path。

    拒绝：非字符串、空串、反斜杠、冒号（盘符/ADS）、绝对路径、含 ``..`` 的路径。
    """
    if not isinstance(value, str) or not value or "\\" in value or ":" in value:
        raise CudaKitError(f"CUDA 套件载荷包含非法路径：{value!r}")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".."} for part in path.parts):
        raise CudaKitError(f"CUDA 套件载荷包含非法路径：{value!r}")
    return Path(*path.parts)


def _validate_manifest(payload: Any) -> dict[str, Any]:
    """校验 manifest 结构（schema/zip/parts/files）与全部路径/哈希字段。"""
    if not isinstance(payload, dict):
        raise CudaKitError("CUDA 套件 manifest 不是 JSON 对象")
    if payload.get("schema_version") != 1:
        raise CudaKitError(f"不支持的 CUDA 套件 manifest 版本：{payload.get('schema_version')!r}")
    for field in ("kit_version", "torch_version"):
        if not isinstance(payload.get(field), str) or not payload[field]:
            raise CudaKitError(f"CUDA 套件 manifest 缺少 {field}")
    if payload.get("platform") != "windows-x64":
        raise CudaKitError(f"CUDA 套件平台不符：{payload.get('platform')!r}")
    for field in ("file_count", "total_bytes", "zip_size"):
        if not isinstance(payload.get(field), int) or payload[field] < 0:
            raise CudaKitError(f"CUDA 套件 manifest 缺少 {field}")
    if not _looks_like_sha256(payload.get("zip_sha256")):
        raise CudaKitError("CUDA 套件 manifest 缺少 zip_sha256")

    parts = payload.get("parts")
    if not isinstance(parts, list) or not parts:
        raise CudaKitError("CUDA 套件 manifest 缺少分卷列表")
    seen_parts: set[str] = set()
    for part in parts:
        if not isinstance(part, dict):
            raise CudaKitError("CUDA 套件 manifest 的分卷项不是对象")
        name = part.get("name")
        if not isinstance(name, str) or not PART_NAME_PATTERN.fullmatch(name):
            raise CudaKitError(f"CUDA 套件 manifest 含非法分卷名：{name!r}")
        if name in seen_parts:
            raise CudaKitError(f"CUDA 套件 manifest 含重复分卷：{name!r}")
        seen_parts.add(name)
        if not isinstance(part.get("size"), int) or part["size"] < 0:
            raise CudaKitError(f"CUDA 套件 manifest 分卷缺少 size：{name!r}")
        if not _looks_like_sha256(part.get("sha256")):
            raise CudaKitError(f"CUDA 套件 manifest 分卷缺少 sha256：{name!r}")

    files = payload.get("files")
    if not isinstance(files, list) or not files:
        raise CudaKitError("CUDA 套件 manifest 缺少文件清单")
    seen_files: set[str] = set()
    for entry in files:
        if not isinstance(entry, dict):
            raise CudaKitError("CUDA 套件 manifest 的文件项不是对象")
        relative = _safe_relative_path(entry.get("path"))
        relative_text = relative.as_posix()
        if relative_text in seen_files:
            raise CudaKitError(f"CUDA 套件 manifest 含重复文件：{relative_text!r}")
        seen_files.add(relative_text)
        if not isinstance(entry.get("size"), int) or entry["size"] < 0:
            raise CudaKitError(f"CUDA 套件 manifest 文件缺少 size：{relative_text!r}")
        if not _looks_like_sha256(entry.get("sha256")):
            raise CudaKitError(f"CUDA 套件 manifest 文件缺少 sha256：{relative_text!r}")
    return payload


def _check_manifest_torch_version(manifest: dict[str, Any]) -> None:
    """下载前先对账：套件 torch 主版本必须与当前应用一致，避免白下 3 GB。"""
    kit_torch = str(manifest.get("torch_version") or "")
    current_torch = _current_torch_version()
    if kit_torch and current_torch and _base_version(kit_torch) != _base_version(current_torch):
        raise CudaKitError(
            f"套件的 torch 版本（{kit_torch}）与当前应用（{current_torch}）不一致，"
            "请等待/构建对应版本的套件"
        )


# ---------------------------------------------------------------------------
# HTTP 下载（urllib，标准库）
# ---------------------------------------------------------------------------


class _GithubRedirectHandler(urllib.request.HTTPRedirectHandler):
    """逐跳跟随重定向，每一跳都重新校验允许的 host。"""

    max_repeats = 4
    max_redirections = MAX_REDIRECTS

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        _validate_redirect_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _default_fetch(
    url: str,
    target: Path,
    *,
    offset: int = 0,
    on_progress: Callable[[int], None] | None = None,
    cancel_event: threading.Event | None = None,
) -> None:
    """流式下载 *url* 到 *target*，offset>0 时用 HTTP Range 续传。

    重定向由 :class:`_GithubRedirectHandler` 逐跳校验。``on_progress`` 报告的是
    目标文件当前总字节数（而非本块增量），所以服务器忽略 Range、从头重写文件
    时进度仍然真实。取消通过 ``cancel_event`` 检查，抛 CudaKitCancelled。
    """
    headers = {"Range": f"bytes={offset}-"} if offset else {}
    request = urllib.request.Request(url, headers=headers, method="GET")
    opener = urllib.request.build_opener(_GithubRedirectHandler())
    try:
        with opener.open(request, timeout=FETCH_TIMEOUT_SECONDS) as response:
            status = getattr(response, "status", None) or response.getcode()
            if status == 206 and offset:
                mode, written = "ab", offset
            elif status == 200:
                # 服务器忽略了 Range：从头重写该文件。
                mode, written = "wb", 0
            else:
                raise CudaKitError(f"CUDA 套件下载失败：HTTP {status}")
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open(mode) as handle:
                while True:
                    if cancel_event is not None and cancel_event.is_set():
                        raise CudaKitCancelled("CUDA 加速套件下载已取消")
                    chunk = response.read(DOWNLOAD_CHUNK_BYTES)
                    if not chunk:
                        break
                    handle.write(chunk)
                    written += len(chunk)
                    if on_progress is not None:
                        on_progress(written)
    except urllib.error.HTTPError as exc:
        raise CudaKitError(f"CUDA 套件下载失败：HTTP {exc.code}") from exc
    except (urllib.error.URLError, OSError) as exc:
        raise CudaKitError(f"CUDA 套件下载失败：{exc}") from exc


def _check_cancel() -> None:
    if _cancel_event.is_set():
        raise CudaKitCancelled("CUDA 加速套件下载已取消")


# ---------------------------------------------------------------------------
# 下载与安装流程
# ---------------------------------------------------------------------------


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(DOWNLOAD_CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _download_manifest(downloads: Path) -> dict[str, Any]:
    target = downloads / MANIFEST_NAME
    _set_job(phase=PHASE_MANIFEST)
    _default_fetch(manifest_url(), target, cancel_event=_cancel_event)
    _check_cancel()
    payload = _read_json(target)
    if payload is None:
        raise CudaKitError("CUDA 套件 manifest 不是合法 JSON")
    manifest = _validate_manifest(payload)
    _check_manifest_torch_version(manifest)
    return manifest


def _download_part(part: dict[str, Any], downloads: Path) -> None:
    """下载单个分卷；已有 .part 文件跳过或按 Range 续传，下载后立即校验。"""
    name = str(part["name"])
    expected_size = int(part["size"])
    part_path = downloads / f"{name}.part"
    existing = part_path.stat().st_size if part_path.is_file() else 0
    if existing == expected_size:
        if _file_hash(part_path) == part["sha256"]:
            _bump_downloaded(expected_size)
            return
        part_path.unlink(missing_ok=True)
        existing = 0
    elif existing > expected_size:
        part_path.unlink(missing_ok=True)
        existing = 0

    _set_job(current_part=name)
    _bump_downloaded(existing)
    accounted = existing

    def on_progress(size: int) -> None:
        nonlocal accounted
        if size > accounted:
            _bump_downloaded(size - accounted)
            accounted = size

    _default_fetch(
        part_url(name),
        part_path,
        offset=existing,
        on_progress=on_progress,
        cancel_event=_cancel_event,
    )
    _check_cancel()
    if part_path.stat().st_size != expected_size or _file_hash(part_path) != part["sha256"]:
        part_path.unlink(missing_ok=True)
        raise CudaKitError(f"CUDA 套件分卷完整性校验失败，已删除并请重试：{name}")


def _concatenate_parts(parts: list[dict[str, Any]], downloads: Path) -> Path:
    zip_path = downloads / LOCAL_ZIP_NAME
    with zip_path.open("wb") as output:
        for part in parts:
            part_path = downloads / f"{part['name']}.part"
            with part_path.open("rb") as source:
                while True:
                    _check_cancel()
                    chunk = source.read(EXTRACT_CHUNK_BYTES)
                    if not chunk:
                        break
                    output.write(chunk)
    return zip_path


def _verify_zip(manifest: dict[str, Any], zip_path: Path) -> None:
    expected_size = manifest.get("zip_size")
    if isinstance(expected_size, int) and zip_path.stat().st_size != expected_size:
        zip_path.unlink(missing_ok=True)
        raise CudaKitError("CUDA 套件压缩包大小与 manifest 不符")
    if _file_hash(zip_path) != manifest["zip_sha256"]:
        zip_path.unlink(missing_ok=True)
        raise CudaKitError("CUDA 套件压缩包完整性校验失败")


def _extract_kit(zip_path: Path, downloads: Path) -> Path:
    """安全解压到 downloads/extract：逐条路径校验，任何失败都清理半成品。"""
    extract_dir = downloads / EXTRACT_DIR_NAME
    shutil.rmtree(extract_dir, ignore_errors=True)
    extract_dir.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(zip_path) as archive:
            for member in archive.infolist():
                _check_cancel()
                if member.is_dir():
                    continue
                relative = _safe_relative_path(member.filename)
                target = extract_dir / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member) as source, target.open("wb") as output:
                    while True:
                        _check_cancel()
                        chunk = source.read(EXTRACT_CHUNK_BYTES)
                        if not chunk:
                            break
                        output.write(chunk)
    except BaseException:
        shutil.rmtree(extract_dir, ignore_errors=True)
        raise
    return extract_dir


def _verify_extracted_files(manifest: dict[str, Any], extract_dir: Path) -> None:
    for entry in manifest["files"]:
        _check_cancel()
        relative = _safe_relative_path(entry["path"])
        target = extract_dir / relative
        if not target.is_file():
            raise CudaKitError(f"CUDA 套件解压后缺少文件：{entry['path']}")
        if target.stat().st_size != entry["size"] or _file_hash(target) != entry["sha256"]:
            raise CudaKitError(f"CUDA 套件文件完整性校验失败：{entry['path']}")


def _install_kit(extract_dir: Path, downloads: Path) -> None:
    """校验通过的目录 + manifest 原子替换到 kit/；旧 kit 作为备份，失败回滚。"""
    manifest_bytes = (downloads / MANIFEST_NAME).read_bytes()
    _write_bytes_atomic(extract_dir / MANIFEST_NAME, manifest_bytes)
    target = kit_dir()
    target.parent.mkdir(parents=True, exist_ok=True)
    backup = target.parent / f".{KIT_DIR_NAME}.backup-{os.getpid()}-{int(time.time() * 1000)}"
    if target.exists():
        os.replace(target, backup)
    try:
        os.replace(extract_dir, target)
    except Exception:
        if backup.exists() and not target.exists():
            os.replace(backup, target)
        raise
    shutil.rmtree(backup, ignore_errors=True)


def _cleanup_transient(downloads: Path) -> None:
    """清理不可续传的中间产物，保留 .part 分卷与 manifest 供重试/续传。"""
    shutil.rmtree(downloads / EXTRACT_DIR_NAME, ignore_errors=True)
    (downloads / LOCAL_ZIP_NAME).unlink(missing_ok=True)


def _invalidate_size_cache() -> None:
    global _size_cache
    _size_cache = None


def _run_download() -> None:
    """后台下载线程主流程；失败时保留已安装 kit 与可续传的分卷。"""
    downloads = downloads_dir()
    try:
        downloads.mkdir(parents=True, exist_ok=True)
        _set_job(
            phase=PHASE_MANIFEST,
            current_part=None,
            parts_total=0,
            downloaded_bytes=0,
            total_bytes=0,
            error=None,
        )
        manifest = _download_manifest(downloads)
        parts = manifest["parts"]
        total_bytes = manifest.get("zip_size")
        if not isinstance(total_bytes, int) or total_bytes < 0:
            total_bytes = sum(int(part["size"]) for part in parts)
        _set_job(
            phase=PHASE_PARTS,
            parts_total=len(parts),
            total_bytes=total_bytes,
            downloaded_bytes=0,
        )
        for part in parts:
            _check_cancel()
            _download_part(part, downloads)

        _check_cancel()
        _set_job(phase=PHASE_VERIFY, current_part=None)
        zip_path = _concatenate_parts(parts, downloads)
        _verify_zip(manifest, zip_path)

        _check_cancel()
        _set_job(phase=PHASE_EXTRACT)
        extract_dir = _extract_kit(zip_path, downloads)

        _set_job(phase=PHASE_VERIFY_FILES)
        _verify_extracted_files(manifest, extract_dir)

        _check_cancel()
        _install_kit(extract_dir, downloads)
        shutil.rmtree(downloads, ignore_errors=True)
        _invalidate_size_cache()
        _set_job(status="completed", phase=PHASE_IDLE, current_part=None, error=None)
    except CudaKitCancelled as exc:
        # 保留各分卷 .part 供断点续传；只清理不可续传的拼接/解压产物。
        _cleanup_transient(downloads)
        _set_job(status="cancelled", current_part=None, error=str(exc))
    except Exception as exc:  # noqa: BLE001 - 任何失败都要落成 job.error 供 UI 展示
        _cleanup_transient(downloads)
        _set_job(status="failed", current_part=None, error=str(exc))


# ---------------------------------------------------------------------------
# 对外接口（server.py 按此契约集成）
# ---------------------------------------------------------------------------


def status() -> dict[str, Any]:
    """模型页需要的套件状态快照。

    返回字段：
        supported   当前平台是否支持（仅 Windows）
        gpu_detected NVIDIA 显卡探测（非 Windows 为 None；探测中为 None）
        installed   kit 是否已安装到磁盘
        invalidated kit 的 torch 版本与当前应用是否不一致
        enabled     当前进程 torch 是否来自 kit 且 torch.cuda.is_available()
        reason      需要展示给用户的原因（unsupported/invalidated/待重启/无 CUDA）
        kit         {"torch_version", "total_bytes"} 或 None
        job         当前/最近一次任务快照，idle 时为 None
    """
    supported = bool(SUPPORTED)
    installed = _kit_present()
    manifest = _read_installed_manifest() if installed else None
    invalidated = False
    reason: str | None = None

    kit_torch = str(manifest.get("torch_version") or "") if manifest else ""
    current_torch = _current_torch_version()
    if manifest is not None and kit_torch and current_torch:
        if _base_version(kit_torch) != _base_version(current_torch):
            invalidated = True
            reason = (
                f"加速套件的 torch 版本（{kit_torch}）与当前应用（{current_torch}）不一致，"
                "请重新下载"
            )

    enabled = False
    if not supported:
        reason = "CUDA 加速套件仅支持 Windows 平台"
    elif installed and not invalidated:
        enabled = _process_torch_enabled()
        if not enabled:
            torch_module = sys.modules.get("torch")
            if torch_module is not None:
                if not _torch_from_kit(torch_module):
                    reason = "加速套件已安装，重启应用后生效"
                else:
                    reason = "加速套件已加载，但未检测到可用的 CUDA 设备"

    kit_info = None
    if manifest is not None:
        kit_info = {
            "torch_version": kit_torch,
            "total_bytes": int(manifest.get("total_bytes") or 0),
        }
    job = current_job()
    return {
        "supported": supported,
        "gpu_detected": _gpu_detected_cached(),
        "installed": installed,
        "invalidated": invalidated,
        "enabled": enabled,
        "reason": reason,
        "kit": kit_info,
        "job": job if job.get("status") != "idle" else None,
    }


def start_download() -> dict[str, Any]:
    """后台开始下载并安装；已有任务运行时抛 RuntimeError("下载已在进行中")。"""
    if not SUPPORTED:
        raise RuntimeError("CUDA 加速套件仅支持 Windows 平台")
    global _job
    with _job_lock:
        _recover_state_locked()
        if _job.get("status") == "running":
            raise RuntimeError("下载已在进行中")
        _job = {
            **_IDLE_JOB,
            "status": "running",
            "phase": PHASE_MANIFEST,
        }
        payload = dict(_job)
        _write_state(payload)
    _cancel_event.clear()
    threading.Thread(target=_run_download, daemon=True, name="cuda-kit-download").start()
    return dict(payload)


def cancel() -> dict[str, Any]:
    """请求取消当前下载（保留已下载分卷）；返回任务快照。"""
    if current_job().get("status") == "running":
        _cancel_event.set()
    return current_job()


def remove() -> dict[str, Any]:
    """移除已安装 kit 与下载暂存；下载进行中时抛 RuntimeError。"""
    if current_job().get("status") == "running":
        raise RuntimeError("下载进行中，无法移除 CUDA 加速套件")
    shutil.rmtree(kit_dir(), ignore_errors=True)
    shutil.rmtree(downloads_dir(), ignore_errors=True)
    _state_path().unlink(missing_ok=True)
    global _job
    with _job_lock:
        _job = dict(_IDLE_JOB)
    _invalidate_size_cache()
    return status()


def size_bytes() -> int:
    """套件总大小（优先已安装 manifest，其次是下载暂存里的 manifest），读不到返回 0。"""
    global _size_cache
    if _size_cache is not None:
        return _size_cache
    for manifest_path in (_installed_manifest_path(), downloads_dir() / MANIFEST_NAME):
        payload = _read_json(manifest_path)
        if not isinstance(payload, dict):
            continue
        total = payload.get("total_bytes")
        if isinstance(total, int) and total > 0:
            _size_cache = total
            return total
    return 0
