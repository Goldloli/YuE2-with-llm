"""CUDA 加速套件管理器单测。

全部离线、跨平台：通过 monkeypatch 把 ``KIT_ROOT`` 指到 tmp_path、把
``_default_fetch`` 换成本地假下载器（在内存里构造小 zip 与分卷），因此不联网、
不依赖 Windows，也不碰仓库里真实的 ``web/data/cuda-kit``。
"""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from types import SimpleNamespace
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
KIT_TORCH_VERSION = "2.10.0+cu128"
CURRENT_TORCH_VERSION = "2.10.0"
KIT_TAG = "cuda-kit-cu128-torch2.10.0"
MANIFEST_URL = (
    "https://github.com/Goldloli/YuE2-with-llm/releases/download/"
    f"{KIT_TAG}/cuda-kit-manifest.json"
)
PART1_NAME = "yue2-cuda-kit-windows-x64.zip.part1"
PART2_NAME = "yue2-cuda-kit-windows-x64.zip.part2"


def _load_cuda_kit():
    """按文件路径加载 web/cuda_kit.py（它不依赖 web 包，也不是安装包模块）。"""
    spec = importlib.util.spec_from_file_location("yue2_web_cuda_kit", ROOT / "web" / "cuda_kit.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


cuda_kit = _load_cuda_kit()


@pytest.fixture(autouse=True)
def _isolated_kit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """把套件目录/配置/平台/任务状态全部隔离到当前测试。"""
    monkeypatch.setattr(cuda_kit, "KIT_ROOT", tmp_path / "cuda-kit")
    monkeypatch.setattr(cuda_kit, "KIT_DIR", tmp_path / "cuda-kit" / "kit")
    config = tmp_path / "cuda_kit.json"
    config.write_text(
        json.dumps(
            {
                "manifest_url": MANIFEST_URL,
                "torch_version": CURRENT_TORCH_VERSION,
                "kit_release_tag": KIT_TAG,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(cuda_kit, "CONFIG_FILE", config)
    monkeypatch.setattr(cuda_kit, "SUPPORTED", True)
    monkeypatch.setattr(cuda_kit, "_job", dict(cuda_kit._IDLE_JOB))
    monkeypatch.setattr(cuda_kit, "_state_recovered", False)
    monkeypatch.setattr(cuda_kit, "_cancel_event", threading.Event())
    # GPU 探测默认表现为「已启动但暂无结果」：真实函数短路返回 None，不拉起线程/子进程
    monkeypatch.setattr(cuda_kit, "_gpu_started", True)
    monkeypatch.setattr(cuda_kit, "_gpu_result", None)
    monkeypatch.setattr(cuda_kit, "_current_torch_version", lambda: CURRENT_TORCH_VERSION)
    monkeypatch.setattr(cuda_kit, "_size_cache", None)
    monkeypatch.setattr(cuda_kit, "_dll_handles", [])
    monkeypatch.setattr(cuda_kit, "_injected_dll_dirs", set())
    monkeypatch.setattr(sys, "path", list(sys.path))


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _build_fake_kit(tmp_path: Path) -> tuple[dict, dict[str, bytes]]:
    """构造含 torch/__init__.py 的小假树，打成真 zip 后按字节分两卷。"""
    source = tmp_path / "kit-source"
    torch_pkg = source / "torch"
    (torch_pkg / "lib").mkdir(parents=True)
    (torch_pkg / "nn").mkdir()
    (torch_pkg / "__init__.py").write_text(
        f'__version__ = "{KIT_TORCH_VERSION}"\n', encoding="utf-8"
    )
    (torch_pkg / "lib" / "cudart64_128.dll").write_bytes(b"fake-cuda-dll-" * 64)
    (torch_pkg / "nn" / "__init__.py").write_text("# fake nn module\n", encoding="utf-8")
    dist_info = source / f"torch-{KIT_TORCH_VERSION}.dist-info"
    dist_info.mkdir()
    (dist_info / "METADATA").write_text(
        f"Name: torch\nVersion: {KIT_TORCH_VERSION}\n", encoding="utf-8"
    )

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(source.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(source).as_posix())
    zip_bytes = zip_buffer.getvalue()
    midpoint = len(zip_bytes) // 2
    part_bytes = (zip_bytes[:midpoint], zip_bytes[midpoint:])

    files = []
    for path in sorted(source.rglob("*")):
        if path.is_file():
            files.append(
                {
                    "path": path.relative_to(source).as_posix(),
                    "size": path.stat().st_size,
                    "sha256": _sha256(path.read_bytes()),
                }
            )
    manifest = {
        "schema_version": 1,
        "kit_version": "2.10.0",
        "torch_version": KIT_TORCH_VERSION,
        "python": "3.11",
        "platform": "windows-x64",
        "file_count": len(files),
        "total_bytes": sum(entry["size"] for entry in files),
        "files": files,
        "zip_name": "yue2-cuda-kit-windows-x64.zip",
        "zip_size": len(zip_bytes),
        "zip_sha256": _sha256(zip_bytes),
        "parts": [
            {"name": name, "size": len(data), "sha256": _sha256(data)}
            for name, data in zip((PART1_NAME, PART2_NAME), part_bytes)
        ],
    }
    payloads = {
        cuda_kit.manifest_url(): json.dumps(manifest).encode("utf-8"),
        cuda_kit.part_url(PART1_NAME): part_bytes[0],
        cuda_kit.part_url(PART2_NAME): part_bytes[1],
    }
    return manifest, payloads


def _install_fake_kit(tmp_path: Path) -> tuple[Path, dict]:
    """直接把假套件「装好」（不做下载），用于状态机/注入测试。"""
    manifest, payloads = _build_fake_kit(tmp_path)
    zip_bytes = payloads[cuda_kit.part_url(PART1_NAME)] + payloads[cuda_kit.part_url(PART2_NAME)]
    kit = cuda_kit.kit_dir()
    kit.mkdir(parents=True)
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        archive.extractall(kit)
    (kit / cuda_kit.MANIFEST_NAME).write_text(json.dumps(manifest), encoding="utf-8")
    return kit, manifest


class _FakeFetcher:
    """本地假下载器：offset 语义等于生产 ``_default_fetch`` 的 Range 起点。"""

    def __init__(
        self,
        payloads: dict[str, bytes],
        *,
        chunk_bytes: int = 64,
        chunk_delay: float = 0.0,
        delay_on=None,
    ) -> None:
        self.payloads = payloads
        self.chunk_bytes = chunk_bytes
        self.chunk_delay = chunk_delay
        self.delay_on = delay_on
        self.requests: list[tuple[str, int]] = []
        self._lock = threading.Lock()

    def __call__(self, url, target, *, offset=0, on_progress=None, cancel_event=None):
        with self._lock:
            self.requests.append((url, offset))
        data = self.payloads[url]
        if offset > len(data):
            raise cuda_kit.CudaKitError(f"range not satisfiable: {offset}")
        body = data[offset:]
        mode = "ab" if offset else "wb"
        written = offset
        with Path(target).open(mode) as handle:
            for index in range(0, len(body), self.chunk_bytes):
                if cancel_event is not None and cancel_event.is_set():
                    raise cuda_kit.CudaKitCancelled("cancelled by test")
                chunk = body[index : index + self.chunk_bytes]
                handle.write(chunk)
                written += len(chunk)
                if on_progress is not None:
                    on_progress(written)
                if self.chunk_delay and (self.delay_on is None or self.delay_on(url)):
                    time.sleep(self.chunk_delay)


def _wait_for_job(predicate=None, timeout: float = 15.0) -> dict:
    predicate = predicate or (lambda job: job["status"] in {"completed", "failed", "cancelled"})
    deadline = time.time() + timeout
    job = cuda_kit.current_job()
    while time.time() < deadline:
        job = cuda_kit.current_job()
        if predicate(job):
            return job
        time.sleep(0.01)
    raise AssertionError(f"job never reached the expected state; last={job}")


# ---------------------------------------------------------------------------
# manifest 校验与路径安全
# ---------------------------------------------------------------------------


def test_manifest_validation_accepts_built_manifest(tmp_path: Path) -> None:
    manifest, _payloads = _build_fake_kit(tmp_path)
    assert cuda_kit._validate_manifest(manifest) is manifest


@pytest.mark.parametrize("missing", ["schema_version", "torch_version", "parts", "files", "zip_sha256"])
def test_manifest_missing_field_rejected(tmp_path: Path, missing: str) -> None:
    manifest, _payloads = _build_fake_kit(tmp_path)
    manifest.pop(missing)
    with pytest.raises(cuda_kit.CudaKitError):
        cuda_kit._validate_manifest(manifest)


@pytest.mark.parametrize("bad_sha", ["not-a-sha", "", "0" * 63, "z" * 64])
def test_manifest_bad_sha_rejected(tmp_path: Path, bad_sha: str) -> None:
    manifest, _payloads = _build_fake_kit(tmp_path)
    manifest["parts"][0]["sha256"] = bad_sha
    with pytest.raises(cuda_kit.CudaKitError):
        cuda_kit._validate_manifest(manifest)

    manifest, _payloads = _build_fake_kit(tmp_path / "second")
    manifest["files"][0]["sha256"] = bad_sha
    with pytest.raises(cuda_kit.CudaKitError):
        cuda_kit._validate_manifest(manifest)


@pytest.mark.parametrize(
    "bad_path",
    ["../evil.py", "/etc/passwd", "torch\\__init__.py", "C:/torch/__init__.py", "torch/../../evil.py", ""],
)
def test_manifest_illegal_path_rejected(tmp_path: Path, bad_path: str) -> None:
    manifest, _payloads = _build_fake_kit(tmp_path)
    manifest["files"][0]["path"] = bad_path
    with pytest.raises(cuda_kit.CudaKitError):
        cuda_kit._validate_manifest(manifest)


def test_manifest_duplicate_file_rejected(tmp_path: Path) -> None:
    manifest, _payloads = _build_fake_kit(tmp_path)
    manifest["files"].append(dict(manifest["files"][0]))
    with pytest.raises(cuda_kit.CudaKitError):
        cuda_kit._validate_manifest(manifest)


def test_safe_relative_path_accepts_normal_paths() -> None:
    assert cuda_kit._safe_relative_path("torch/__init__.py") == Path("torch", "__init__.py")
    assert cuda_kit._safe_relative_path("torch/lib/cudart64_128.dll") == Path(
        "torch", "lib", "cudart64_128.dll"
    )


@pytest.mark.parametrize(
    "value",
    ["..", "../x", "torch/../../x", "/abs/path", "C:/drive", "torch\\win", "", None, 5],
)
def test_safe_relative_path_rejects_unsafe_values(value: object) -> None:
    with pytest.raises(cuda_kit.CudaKitError):
        cuda_kit._safe_relative_path(value)


@pytest.mark.parametrize(
    "name",
    ["../../x", "..\\..\\x", f"{PART1_NAME}/../../x", f"{PART1_NAME}.exe", "evil.zip.part1", ""],
)
def test_part_name_rejected(name: str) -> None:
    with pytest.raises(cuda_kit.CudaKitError):
        cuda_kit.part_url(name)


@pytest.mark.parametrize(
    "url",
    [
        "http://github.com/Goldloli/YuE2-with-llm/releases/download/x/cuda-kit-manifest.json",
        "https://evil.com/Goldloli/YuE2-with-llm/releases/download/x/cuda-kit-manifest.json",
    ],
)
def test_release_url_rejects_non_https_or_other_host(url: str) -> None:
    with pytest.raises(cuda_kit.CudaKitError):
        cuda_kit._validate_release_url(url)


def test_redirect_targets_limited_to_github_domains() -> None:
    assert cuda_kit._validate_redirect_url(MANIFEST_URL)
    assert cuda_kit._validate_redirect_url(
        "https://objects.githubusercontent.com/release-asset?token=1"
    )
    for url in (
        "https://evil.com/x",
        "http://objects.githubusercontent.com/x",
        "https://githubusercontent.com.evil.com/x",
    ):
        with pytest.raises(cuda_kit.CudaKitError):
            cuda_kit._validate_redirect_url(url)


def test_extract_rejects_path_traversal(tmp_path: Path) -> None:
    evil_zip = tmp_path / "evil.zip"
    with zipfile.ZipFile(evil_zip, "w") as archive:
        archive.writestr("../evil.txt", "boom")
    downloads = cuda_kit.downloads_dir()
    downloads.mkdir(parents=True)
    with pytest.raises(cuda_kit.CudaKitError):
        cuda_kit._extract_kit(evil_zip, downloads)
    assert not (tmp_path / "evil.txt").exists()
    assert not (downloads / cuda_kit.EXTRACT_DIR_NAME).exists()


def test_paths_follow_kit_root_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """宿主只覆盖 KIT_ROOT 时，kit/downloads/state 全部跟着走。"""
    monkeypatch.setattr(cuda_kit, "KIT_DIR", cuda_kit._DEFAULT_KIT_DIR)
    root = tmp_path / "only-root"
    monkeypatch.setattr(cuda_kit, "KIT_ROOT", root)
    assert cuda_kit.kit_root() == root
    assert cuda_kit.kit_dir() == root / "kit"
    assert cuda_kit.downloads_dir() == root / "downloads"
    assert cuda_kit._state_path() == root / "state.json"


def test_paths_follow_kit_dir_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """宿主只覆盖 KIT_DIR 时，根目录取其父目录，避免写回真实的 web/data。"""
    monkeypatch.setattr(cuda_kit, "KIT_ROOT", cuda_kit._DEFAULT_KIT_ROOT)
    kit = tmp_path / "only-kit" / "kit"
    monkeypatch.setattr(cuda_kit, "KIT_DIR", kit)
    assert cuda_kit.kit_dir() == kit
    assert cuda_kit.kit_root() == kit.parent
    assert cuda_kit.downloads_dir() == kit.parent / "downloads"
    assert cuda_kit._state_path() == kit.parent / "state.json"


# ---------------------------------------------------------------------------
# 完整下载 -> 校验 -> 解压 -> 安装
# ---------------------------------------------------------------------------


def test_download_job_end_to_end(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    manifest, payloads = _build_fake_kit(tmp_path)
    fetcher = _FakeFetcher(payloads)
    monkeypatch.setattr(cuda_kit, "_default_fetch", fetcher)

    started = cuda_kit.start_download()
    assert started["status"] == "running"
    assert started["phase"] == "manifest"

    final = _wait_for_job()
    assert final["status"] == "completed"
    assert final["phase"] == "idle"
    assert final["current_part"] is None
    assert final["parts_total"] == 2
    assert final["downloaded_bytes"] == final["total_bytes"] == manifest["zip_size"]
    assert final["error"] is None

    kit = cuda_kit.kit_dir()
    assert (kit / "torch" / "__init__.py").is_file()
    assert (kit / "torch" / "lib" / "cudart64_128.dll").is_file()
    assert (kit / cuda_kit.MANIFEST_NAME).is_file()
    assert not cuda_kit.downloads_dir().exists(), "安装成功后暂存目录应清空"

    state = cuda_kit.status()
    assert state["supported"] is True
    assert state["installed"] is True
    assert state["invalidated"] is False
    assert state["enabled"] is False, "未导入 torch 时不得探测 CUDA"
    assert state["kit"] == {
        "torch_version": KIT_TORCH_VERSION,
        "total_bytes": manifest["total_bytes"],
    }
    assert state["job"]["status"] == "completed"
    assert cuda_kit.size_bytes() == manifest["total_bytes"]

    persisted = json.loads(cuda_kit._state_path().read_text(encoding="utf-8"))
    assert persisted["status"] == "completed"


def test_download_resumes_existing_part(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    manifest, payloads = _build_fake_kit(tmp_path)
    part1_url = cuda_kit.part_url(PART1_NAME)
    part1_data = payloads[part1_url]
    resume_from = len(part1_data) // 3
    downloads = cuda_kit.downloads_dir()
    downloads.mkdir(parents=True)
    (downloads / f"{PART1_NAME}.part").write_bytes(part1_data[:resume_from])

    fetcher = _FakeFetcher(payloads)
    monkeypatch.setattr(cuda_kit, "_default_fetch", fetcher)
    cuda_kit.start_download()
    final = _wait_for_job()
    assert final["status"] == "completed"
    part1_offsets = [offset for url, offset in fetcher.requests if url == part1_url]
    assert part1_offsets == [resume_from], "已有 .part 字节应作为 Range 起点"
    assert final["downloaded_bytes"] == manifest["zip_size"]


def test_tampered_part_fails_without_touching_installed_kit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    old_kit, _old_manifest = _install_fake_kit(tmp_path / "old")
    old_init = old_kit / "torch" / "__init__.py"
    old_bytes = old_init.read_bytes()

    manifest, payloads = _build_fake_kit(tmp_path / "bad")
    part2_url = cuda_kit.part_url(PART2_NAME)
    tampered = bytearray(payloads[part2_url])
    tampered[0] ^= 0xFF
    payloads[part2_url] = bytes(tampered)
    monkeypatch.setattr(cuda_kit, "_default_fetch", _FakeFetcher(payloads))

    cuda_kit.start_download()
    final = _wait_for_job()
    assert final["status"] == "failed"
    assert PART2_NAME in (final["error"] or "")
    assert old_init.read_bytes() == old_bytes, "下载失败不得破坏已安装的 kit"
    assert cuda_kit.status()["installed"] is True
    assert not (cuda_kit.downloads_dir() / f"{PART2_NAME}.part").exists(), "校验失败的分卷应删除"
    assert (cuda_kit.downloads_dir() / f"{PART1_NAME}.part").is_file(), "完好分卷保留供重试"
    assert manifest["zip_sha256"]  # 构造的 manifest 本身有效


def test_cancel_midway_preserves_parts_and_retry_resumes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest, payloads = _build_fake_kit(tmp_path)
    part1_url = cuda_kit.part_url(PART1_NAME)
    part1_size = manifest["parts"][0]["size"]
    # 只放慢分卷下载（manifest 快速通过）；轮询 job 内存进度而非文件大小。
    fetcher = _FakeFetcher(
        payloads,
        chunk_bytes=8,
        chunk_delay=0.01,
        delay_on=lambda url: url != cuda_kit.manifest_url(),
    )
    monkeypatch.setattr(cuda_kit, "_default_fetch", fetcher)

    cuda_kit.start_download()
    _wait_for_job(
        lambda job: job["current_part"] == PART1_NAME
        and 0 < job["downloaded_bytes"] < part1_size
    )
    cuda_kit.cancel()
    final = _wait_for_job()
    assert final["status"] == "cancelled"
    part1_path = cuda_kit.downloads_dir() / f"{PART1_NAME}.part"
    assert part1_path.is_file(), "取消后应保留已下载分卷供续传"
    partial = part1_path.stat().st_size
    assert 0 < partial < part1_size

    fetcher.chunk_delay = 0.0
    cuda_kit.start_download()
    retried = _wait_for_job()
    assert retried["status"] == "completed"
    part1_offsets = [offset for url, offset in fetcher.requests if url == part1_url]
    assert part1_offsets[0] == 0
    assert part1_offsets[-1] == partial, "重试应从取消时保留的字节续传"


def test_start_download_rejected_while_running(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _manifest, payloads = _build_fake_kit(tmp_path)
    fetcher = _FakeFetcher(payloads, chunk_bytes=8, chunk_delay=0.02)
    monkeypatch.setattr(cuda_kit, "_default_fetch", fetcher)
    cuda_kit.start_download()
    _wait_for_job(lambda job: job["status"] == "running" and job["downloaded_bytes"] > 0)
    with pytest.raises(RuntimeError, match="下载已在进行中"):
        cuda_kit.start_download()
    cuda_kit.cancel()
    assert _wait_for_job()["status"] == "cancelled"


# ---------------------------------------------------------------------------
# 移除 / 失效 / 注入
# ---------------------------------------------------------------------------


def test_remove_deletes_kit_downloads_and_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _manifest, payloads = _build_fake_kit(tmp_path)
    monkeypatch.setattr(cuda_kit, "_default_fetch", _FakeFetcher(payloads))
    cuda_kit.start_download()
    assert _wait_for_job()["status"] == "completed"
    assert cuda_kit.status()["installed"] is True

    state = cuda_kit.remove()
    assert state["installed"] is False
    assert state["job"] is None
    assert not cuda_kit.kit_dir().exists()
    assert not cuda_kit.downloads_dir().exists()
    assert not cuda_kit._state_path().exists()


def test_remove_rejected_while_downloading(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _manifest, payloads = _build_fake_kit(tmp_path)
    fetcher = _FakeFetcher(payloads, chunk_bytes=8, chunk_delay=0.02)
    monkeypatch.setattr(cuda_kit, "_default_fetch", fetcher)
    cuda_kit.start_download()
    _wait_for_job(lambda job: job["current_part"] == PART1_NAME and job["downloaded_bytes"] > 0)
    with pytest.raises(RuntimeError):
        cuda_kit.remove()
    cuda_kit.cancel()
    assert _wait_for_job()["status"] == "cancelled"
    assert cuda_kit.remove()["installed"] is False


def test_status_invalidated_on_torch_version_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    kit, _manifest = _install_fake_kit(tmp_path)
    monkeypatch.setattr(cuda_kit, "_current_torch_version", lambda: "2.11.0")
    state = cuda_kit.status()
    assert state["installed"] is True
    assert state["invalidated"] is True
    assert state["enabled"] is False
    assert state["reason"] and "不一致" in state["reason"]
    assert state["kit"]["torch_version"] == KIT_TORCH_VERSION
    assert cuda_kit.maybe_inject() is False, "版本不匹配时不得注入旧 kit"
    assert str(kit) not in sys.path


def test_local_version_suffix_does_not_invalidate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_kit(tmp_path)
    monkeypatch.setattr(cuda_kit, "_current_torch_version", lambda: "2.10.0+cpu")
    state = cuda_kit.status()
    assert state["installed"] is True
    assert state["invalidated"] is False


def test_maybe_inject_absent_kit_returns_false() -> None:
    assert cuda_kit.maybe_inject() is False


def test_maybe_inject_is_idempotent(tmp_path: Path) -> None:
    kit, _manifest = _install_fake_kit(tmp_path)
    assert cuda_kit.maybe_inject() is True
    kit_text = str(kit)
    assert sys.path[0] == kit_text
    assert sys.path.count(kit_text) == 1
    assert cuda_kit.maybe_inject() is True
    assert sys.path.count(kit_text) == 1, "重复调用不得重复插入 sys.path"


def test_maybe_inject_adds_windows_dll_directory_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    kit, _manifest = _install_fake_kit(tmp_path)
    calls: list[str] = []

    def fake_add_dll_directory(path: str):
        calls.append(path)
        return object()

    monkeypatch.setattr(cuda_kit, "_on_windows", lambda: True)
    monkeypatch.setattr(os, "add_dll_directory", fake_add_dll_directory, raising=False)
    assert cuda_kit.maybe_inject() is True
    assert cuda_kit.maybe_inject() is True
    assert calls == [str(kit / "torch" / "lib")], "DLL 目录只添加一次"


def test_enabled_when_torch_comes_from_kit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    kit, _manifest = _install_fake_kit(tmp_path)
    fake_torch = SimpleNamespace(
        __file__=str(kit / "torch" / "__init__.py"),
        __version__=KIT_TORCH_VERSION,
        cuda=SimpleNamespace(is_available=lambda: True),
    )
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    state = cuda_kit.status()
    assert state["enabled"] is True
    assert state["reason"] is None
    assert state["invalidated"] is False

    fake_torch.cuda = SimpleNamespace(is_available=lambda: False)
    state = cuda_kit.status()
    assert state["enabled"] is False
    assert state["reason"] and "CUDA" in state["reason"]


def test_unsupported_platform_short_circuits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cuda_kit, "SUPPORTED", False)
    state = cuda_kit.status()
    assert state["supported"] is False
    assert state["gpu_detected"] is None
    assert state["installed"] is False
    assert state["enabled"] is False
    assert state["reason"]
    assert state["job"] is None
    with pytest.raises(RuntimeError):
        cuda_kit.start_download()


def test_detect_nvidia_gpu_subprocess_outcomes(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Result:
        returncode = 0
        stdout = b"GPU 0: NVIDIA GeForce RTX 3080 Ti"

    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: _Result())
    assert cuda_kit._detect_nvidia_gpu() is True

    def _missing(*args, **kwargs):
        raise FileNotFoundError("nvidia-smi")

    monkeypatch.setattr(subprocess, "run", _missing)
    assert cuda_kit._detect_nvidia_gpu() is False
