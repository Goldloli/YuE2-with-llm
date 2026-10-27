#!/usr/bin/env python3
"""构建 Windows 专属「CUDA 加速套件」的发布资产。

移植自 ASRbox `scripts/build-cuda-kit.py`，适配 YuE2：套件是一棵 cu128 torch 树，
作为独立 GitHub Release（分卷 + manifest）分发，应用运行时的 `web/cuda_kit.py`
负责下载、校验、解压、安装与注入；主包仍然只带 CPU 版 torch。

流水线：
1. 在 Windows x64 + CPython 上以 ``pip install --target`` 从 ``--index-url``
   安装 ``packaging/cuda-requirements-win.txt``（只钉 torch，依赖由 pip 解析）；
2. 裁剪：只保留 ``torch/`` 与 ``torch-*.dist-info``，并删除 torch 的
   ``include/``、``share/`` 与全部 ``__pycache__``；
3. 逐文件 sha256 清单 -> 固定时间戳的可复现 zip -> 按字节切成每卷 <2 GiB 的分卷
   （manifest 记录 zip 与每一卷的 sha256，应用按顺序拼接还原 zip）；
4. ``--check`` 校验一个已解压/已安装的 kit 目录，``--verify-parts`` 复演安装路径
   （拼接分卷 -> 校验 zip -> 解压 -> 逐文件校验）。

用法::

    python packaging/build_cuda_kit.py --kit-version 2.10.0
    python packaging/build_cuda_kit.py --check <kit-dir>
    python packaging/build_cuda_kit.py --verify-parts

产物默认写到 ``dist/cuda-kit/``（已 gitignore）：manifest + 分卷；
加 ``--keep-zip`` 时额外保留拼接前的 zip。本脚本文本全部使用标准库。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

try:  # Windows 控制台可能默认旧代码页，无法输出中文
    sys.stdout.reconfigure(errors="replace")
    sys.stderr.reconfigure(errors="replace")
except (AttributeError, ValueError):  # pragma: no cover - 仅用于兼容特殊 stdout
    pass

ROOT = Path(__file__).resolve().parents[1]
REQUIREMENTS = ROOT / "packaging" / "cuda-requirements-win.txt"
DEFAULT_OUT_DIR = ROOT / "dist" / "cuda-kit"

ZIP_NAME = "yue2-cuda-kit-windows-x64.zip"
MANIFEST_NAME = "cuda-kit-manifest.json"
PLATFORM = "windows-x64"
SCHEMA_VERSION = 1

DEFAULT_KIT_VERSION = "dev"
DEFAULT_PARTS = 2
DEFAULT_INDEX_URL = "https://download.pytorch.org/whl/cu128"
DEFAULT_TORCH_VERSION = "2.10.0"

# 只留推理需要的 torch 包本体与其 dist-info；cpp_extension 的头文件/CMake 文件不随包。
TORCH_TRIM_DIRS = ("include", "share")
# GitHub Release 单个资产上限 2 GiB；每卷必须严格小于该值。
GITHUB_ASSET_LIMIT_BYTES = 2 * 1024**3
FIXED_ZIP_DATE = (1980, 1, 1, 0, 0, 0)
COPY_BUFFER_BYTES = 1024 * 1024


def _hash_file(path: Path) -> str:
    """返回文件的 sha256 十六进制串。"""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(COPY_BUFFER_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _base_version(version: str) -> str:
    """去掉 wheel 的本地版本后缀（如 ``2.10.0+cu128`` -> ``2.10.0``）。"""
    return version.split("+", 1)[0].strip()


def _requirements_torch_version(path: Path) -> str:
    """从 requirements 文件里读出 ``torch==X`` 的版本，用于和 --torch-version 对账。"""
    if not path.is_file():
        raise SystemExit(f"requirements 文件不存在：{path}")
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        if line.startswith("torch=="):
            version = line[len("torch==") :].split(";", 1)[0].strip()
            if version:
                return version
    raise SystemExit(f"{path} 中没有找到 torch==<version> 钉版行")


def _detect_torch_version(kit_root: Path) -> str:
    """从 kit 里的 torch-*.dist-info 目录名反推 torch 版本。"""
    dist_infos = sorted(path.name for path in kit_root.glob("torch-*.dist-info"))
    if len(dist_infos) != 1:
        raise SystemExit(f"预期恰好一个 torch-*.dist-info，实际 {len(dist_infos)} 个：{dist_infos}")
    name = dist_infos[0]
    return name[len("torch-") : -len(".dist-info")]


def _trim_kit(kit_root: Path) -> None:
    """裁掉除 torch/ 与 torch-*.dist-info 之外的一切，并删除体积大且无用的目录。"""
    if not (kit_root / "torch" / "__init__.py").is_file():
        raise SystemExit(f"pip --target 安装结果里没有 torch 包：{kit_root}")
    for entry in sorted(kit_root.iterdir()):
        if entry.name == "torch" and entry.is_dir():
            continue
        if entry.name.startswith("torch-") and entry.name.endswith(".dist-info"):
            continue
        if entry.is_dir():
            shutil.rmtree(entry)
        else:
            entry.unlink()
    for trim_name in TORCH_TRIM_DIRS:
        target = kit_root / "torch" / trim_name
        if target.exists():
            shutil.rmtree(target)
    for cache_dir in sorted(kit_root.rglob("__pycache__")):
        shutil.rmtree(cache_dir, ignore_errors=True)


def _kit_files(kit_root: Path) -> list[Path]:
    """kit 目录下所有普通文件，按相对路径排序（保证 manifest/zip 顺序稳定）。"""
    return sorted(path for path in kit_root.rglob("*") if path.is_file())


def _build_manifest(kit_root: Path, kit_version: str, torch_version: str) -> dict:
    """生成逐文件 sha256 清单（schema 与 ASRbox 对齐，另加 zip/分卷字段）。"""
    files = []
    for path in _kit_files(kit_root):
        files.append(
            {
                "path": path.relative_to(kit_root).as_posix(),
                "size": path.stat().st_size,
                "sha256": _hash_file(path),
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "kit_version": kit_version,
        "torch_version": torch_version,
        "python": f"{sys.version_info.major}.{sys.version_info.minor}",
        "platform": PLATFORM,
        "file_count": len(files),
        "total_bytes": sum(item["size"] for item in files),
        "files": files,
    }


def _write_zip(kit_root: Path, zip_path: Path) -> None:
    """写可复现 zip：固定时间戳、固定权限位、按排序后的文件列表写入。"""
    with zipfile.ZipFile(
        zip_path,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=6,
        allowZip64=True,
    ) as archive:
        for path in _kit_files(kit_root):
            info = zipfile.ZipInfo(path.relative_to(kit_root).as_posix(), date_time=FIXED_ZIP_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            with path.open("rb") as handle:
                with archive.open(info, "w", force_zip64=True) as target:
                    shutil.copyfileobj(handle, target, length=COPY_BUFFER_BYTES)


def _split_parts(zip_path: Path, part_count: int) -> list[dict]:
    """把 zip 按字节切成 part_count 份；按顺序拼接即可还原（每卷 <2 GiB）。"""
    if part_count < 1:
        raise SystemExit("--parts 必须是正整数")
    zip_size = zip_path.stat().st_size
    chunk = (zip_size + part_count - 1) // part_count
    parts = []
    with zip_path.open("rb") as source:
        for index in range(part_count):
            part_path = zip_path.with_name(f"{zip_path.name}.part{index + 1}")
            digest = hashlib.sha256()
            written = 0
            with part_path.open("wb") as target:
                while written < chunk:
                    block = source.read(min(COPY_BUFFER_BYTES, chunk - written))
                    if not block:
                        break
                    digest.update(block)
                    target.write(block)
                    written += len(block)
            if written == 0:
                part_path.unlink(missing_ok=True)
                break
            parts.append({"name": part_path.name, "size": written, "sha256": digest.hexdigest()})
    oversized = [part["name"] for part in parts if part["size"] >= GITHUB_ASSET_LIMIT_BYTES]
    if oversized:
        raise SystemExit(
            "分卷超过 GitHub 单资产 2 GiB 上限，请增大 --parts："
            f"{oversized}（当前每卷 {chunk / 1024**3:.2f} GiB）"
        )
    return parts


def _safe_zip_member(name: str) -> Path:
    """拒绝绝对路径、``..``、反斜杠与盘符（和 web/cuda_kit.py 的校验保持一致）。"""
    if not isinstance(name, str) or not name or "\\" in name or ":" in name:
        raise SystemExit(f"zip 内包含非法路径：{name!r}")
    path = PurePosixPath(name)
    if path.is_absolute() or any(part == ".." for part in path.parts):
        raise SystemExit(f"zip 内包含非法路径：{name!r}")
    return Path(*path.parts)


def _check_kit(kit_dir: Path, manifest_path: Path) -> int:
    """校验一个已解压目录：文件集合、size 与 sha256 都必须和 manifest 一致。"""
    if not kit_dir.is_dir():
        print(f"CHECK FAILED: kit 目录不存在：{kit_dir}", file=sys.stderr)
        return 1
    if not manifest_path.is_file():
        print(f"CHECK FAILED: manifest 不存在：{manifest_path}", file=sys.stderr)
        return 1
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"CHECK FAILED: manifest 无法解析：{exc}", file=sys.stderr)
        return 1
    expected = {item["path"]: item for item in manifest.get("files", [])}
    actual: dict[str, Path] = {}
    for path in _kit_files(kit_dir):
        rel_path = path.relative_to(kit_dir).as_posix()
        if rel_path == MANIFEST_NAME:  # 安装后 kit 目录里会多一份 manifest 副本
            continue
        actual[rel_path] = path
    problems: list[str] = []
    for rel_path in sorted(set(expected) | set(actual)):
        if rel_path not in expected:
            problems.append(f"unexpected file: {rel_path}")
            continue
        if rel_path not in actual:
            problems.append(f"missing file: {rel_path}")
            continue
        path = actual[rel_path]
        item = expected[rel_path]
        if path.stat().st_size != item["size"] or _hash_file(path) != item["sha256"]:
            problems.append(f"hash/size mismatch: {rel_path}")
    if problems:
        for problem in problems[:20]:
            print(f"CHECK FAILED: {problem}", file=sys.stderr)
        print(f"{len(problems)} problem(s)", file=sys.stderr)
        return 1
    print(
        f"kit 与 manifest 一致：{len(expected)} 个文件，torch {manifest.get('torch_version')}，"
        f"{manifest.get('total_bytes', 0) / 1024**3:.2f} GiB"
    )
    return 0


def _verify_parts(out_dir: Path) -> int:
    """复演应用的安装路径：拼接分卷 -> 校验 zip -> 解压 -> 逐文件校验。

    只依赖已发布的 manifest 与分卷，证明「仅有这些资产也能装出可用的 kit」。
    """
    manifest_path = out_dir / MANIFEST_NAME
    if not manifest_path.is_file():
        print(f"CHECK FAILED: manifest 不存在：{manifest_path}", file=sys.stderr)
        return 1
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"CHECK FAILED: manifest 无法解析：{exc}", file=sys.stderr)
        return 1
    parts = manifest.get("parts")
    if not isinstance(parts, list) or not parts:
        print("CHECK FAILED: manifest 没有分卷列表", file=sys.stderr)
        return 1
    with tempfile.TemporaryDirectory(prefix="cuda-kit-verify-", dir=out_dir) as work:
        work_dir = Path(work)
        zip_path = work_dir / str(manifest.get("zip_name") or ZIP_NAME)
        zip_digest = hashlib.sha256()
        with zip_path.open("wb") as target:
            for part in parts:
                part_name = str(part.get("name") or "")
                part_path = out_dir / part_name
                if not part_path.is_file():
                    print(f"CHECK FAILED: 缺少分卷 {part_name}", file=sys.stderr)
                    return 1
                part_digest = hashlib.sha256()
                part_size = 0
                with part_path.open("rb") as source:
                    for chunk in iter(lambda: source.read(COPY_BUFFER_BYTES), b""):
                        part_digest.update(chunk)
                        zip_digest.update(chunk)
                        target.write(chunk)
                        part_size += len(chunk)
                if part_size != part.get("size") or part_digest.hexdigest() != part.get("sha256"):
                    print(f"CHECK FAILED: 分卷 size/sha256 不符 {part_name}", file=sys.stderr)
                    return 1
        if (
            zip_path.stat().st_size != manifest.get("zip_size")
            or zip_digest.hexdigest() != manifest.get("zip_sha256")
        ):
            print("CHECK FAILED: 拼接后的 zip size/sha256 不符", file=sys.stderr)
            return 1
        print("分卷拼接通过：zip sha256 一致")
        kit_dir = work_dir / "kit"
        try:
            with zipfile.ZipFile(zip_path) as archive:
                for member in archive.infolist():
                    if member.is_dir():
                        continue
                    target = kit_dir / _safe_zip_member(member.filename)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(member) as source, target.open("wb") as output:
                        shutil.copyfileobj(source, output, length=COPY_BUFFER_BYTES)
        except (OSError, zipfile.BadZipFile) as exc:
            print(f"CHECK FAILED: zip 解压失败：{exc}", file=sys.stderr)
            return 1
        return _check_kit(kit_dir, manifest_path)


def build(args: argparse.Namespace) -> int:
    """执行完整构建：安装 -> 裁剪 -> 清单 -> zip -> 分卷 -> manifest。"""
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    expected_torch = _base_version(args.torch_version)
    pinned_torch = _requirements_torch_version(REQUIREMENTS)
    if _base_version(pinned_torch) != expected_torch:
        raise SystemExit(
            f"requirements 钉的是 torch=={pinned_torch}，与 --torch-version {args.torch_version} 不一致；"
            "请先同步 packaging/cuda-requirements-win.txt"
        )

    with tempfile.TemporaryDirectory(prefix="yue2-cuda-kit-") as work:
        kit_root = Path(work) / "kit-root"
        kit_root.mkdir(parents=True)
        print(f"安装 torch=={pinned_torch}（index: {args.index_url}）...")
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--target",
                str(kit_root),
                "--index-url",
                args.index_url,
                "--no-warn-script-location",
                "--disable-pip-version-check",
                "-r",
                str(REQUIREMENTS),
            ],
            check=True,
        )
        _trim_kit(kit_root)
        torch_version = _detect_torch_version(kit_root)
        if _base_version(torch_version) != expected_torch:
            raise SystemExit(
                f"安装得到的 torch=={torch_version} 与 --torch-version {args.torch_version} 不一致；"
                "请检查 --index-url 是否提供了对应的 cu 轮子"
            )
        print(f"裁剪完成：torch {torch_version}，正在计算逐文件 sha256 ...")
        manifest = _build_manifest(kit_root, args.kit_version, torch_version)

        zip_path = out_dir / ZIP_NAME
        manifest_path = out_dir / MANIFEST_NAME
        print(f"打包可复现 zip：{zip_path}")
        _write_zip(kit_root, zip_path)
        print(f"切分 {args.parts} 个分卷 ...")
        parts = _split_parts(zip_path, args.parts)
        zip_size = zip_path.stat().st_size
        manifest.update(
            {
                "zip_name": zip_path.name,
                "zip_size": zip_size,
                "zip_sha256": _hash_file(zip_path),
                "parts": parts,
            }
        )
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        if not args.keep_zip:
            zip_path.unlink()

        raw_gib = manifest["total_bytes"] / 1024**3
        zip_gib = zip_size / 1024**3
        parts_summary = ", ".join(
            f"{part['name']} {part['size'] / 1024**3:.2f} GiB" for part in parts
        )
        print(f"kit：{manifest['file_count']} 个文件，原始 {raw_gib:.2f} GiB，zip {zip_gib:.2f} GiB")
        print(f"分卷：{parts_summary}")
        print(f"manifest：{manifest_path}")
        print("提示：运行 --verify-parts 复演应用的拼接/解压/逐文件校验。")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--kit-version", default=DEFAULT_KIT_VERSION, help="写进 manifest 的套件版本")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR), help="产物输出目录（默认 dist/cuda-kit）")
    parser.add_argument(
        "--parts",
        type=int,
        default=DEFAULT_PARTS,
        help=f"分卷数量（默认 {DEFAULT_PARTS}，每卷必须 <2 GiB）",
    )
    parser.add_argument("--keep-zip", action="store_true", help="分卷后保留未切分的 zip")
    parser.add_argument("--check", metavar="KIT_DIR", default=None, help="校验一个已解压/已安装的 kit 目录")
    parser.add_argument(
        "--verify-parts",
        action="store_true",
        help="复演应用安装路径（拼接分卷 -> zip sha256 -> 解压 -> 逐文件校验）",
    )
    parser.add_argument("--index-url", default=DEFAULT_INDEX_URL, help="torch cu128 索引地址")
    parser.add_argument("--torch-version", default=DEFAULT_TORCH_VERSION, help="期望的 torch 版本（与 requirements 对账）")
    args = parser.parse_args(argv)

    if args.check:
        kit_dir = Path(args.check)
        manifest_path = kit_dir / MANIFEST_NAME
        if not manifest_path.is_file():
            manifest_path = Path(args.out_dir) / MANIFEST_NAME
        return _check_kit(kit_dir, manifest_path)
    if args.verify_parts:
        return _verify_parts(Path(args.out_dir))
    return build(args)


if __name__ == "__main__":
    raise SystemExit(main())
