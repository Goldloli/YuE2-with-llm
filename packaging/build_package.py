#!/usr/bin/env python3
"""Build a platform-specific, self-contained YuE2 Studio one-click package.

Each package ships exactly one launcher: `macos` gets `start.command`, `win-x64`
gets `start.bat`. The default build is *self-contained*: it embeds a portable
CPython runtime (`runtime/`) plus every Python dependency (`envs/web/`, and
`envs/mlx/` on macOS), so double-clicking the launcher starts the web studio
without any network access or pip install. Model weights are never embedded —
the app opens the Models page, where the user downloads what they need and picks
a download channel (domestic mirror hf-mirror.com or direct huggingface.co).

    python packaging/build_package.py --platform macos
    python packaging/build_package.py --platform win-x64
    python packaging/build_package.py --platform macos --runtime slim   # dev-only

Output: oneclick-packages/<platform>/yue2-studio-oneclick-<YYYYMMDD>-<platform>.zip
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import platform as platform_module
import shutil
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import urllib.request
import zipfile
from pathlib import Path

try:  # Windows consoles may default to a legacy code page that cannot print CJK
    sys.stdout.reconfigure(errors="replace")
except (AttributeError, ValueError):
    pass

ROOT = Path(__file__).resolve().parents[1]
PACKAGING = ROOT / "packaging"
PACKAGE_NAME = "yue2-studio-oneclick"

# One launcher per platform; the other launcher is a hard red line.
LAUNCHERS = {"macos": "start.command", "win-x64": "start.bat"}
OTHER_LAUNCHERS = {"macos": "start.bat", "win-x64": "start.command"}
PLATFORMS = sorted(LAUNCHERS)
RUNTIMES = ("bundle", "slim")
HOOKS_MESSAGE = "双击启动器即可打开网页，不需要联网安装依赖（模型在应用内下载）"

# Portable CPython (python-build-standalone). Pin both values: bump deliberately.
PBS_TAG = "20261026"
PBS_VERSION = "3.11.18"
PBS_TRIPLES = {"macos": "aarch64-apple-darwin", "win-x64": "x86_64-pc-windows-msvc"}
PBS_URL = ("https://github.com/astral-sh/python-build-standalone/releases/download/"
           "{tag}/cpython-{version}+{tag}-{triple}-install_only_stripped.tar.gz")

# macOS-only MLX runtime (small: mlx + mlx-metal). The app also keeps working
# with the torch backend if the user never touches MLX.
MLX_PINS = ["mlx==0.32.4", "tiktoken==0.12.0", "numpy==2.2.6", "soundfile==0.13.1"]

# GitHub caps release assets at 2 GiB; keep a clear margin.
MAX_ZIP_BYTES = 1_900_000_000

# Whitelist: everything that ships as source. New top-level dirs stay OUT.
INCLUDE_ROOTS = [
    "web", "src", "tools", "skills", "examples", "licenses", "docs", "tests",
    ".github",
]
INCLUDE_FILES = [
    "pyproject.toml", "README.md", "LICENSE", "MODEL_LICENSE",
    "THIRD_PARTY_NOTICES.md", "MANIFEST.in", ".gitattributes",
]

EXCLUDE_PATTERNS = ["__pycache__", "*.pyc", "*.pyo", ".DS_Store", "*.egg-info",
                    "*.partial", ".coverage"]

# Red lines: if any of these appear inside the staged source, fail the build.
FORBIDDEN = [".git", ".venv", ".venv-mlx", ".venv-sheetsage2", ".env",
             "outputs", "web/data", ".playwright-mcp", ".pytest_cache",
             ".codegraph", ".kimi-code", "compare", "ref-suno", "openspec",
             "packaging", "oneclick-packages"]

REQUIRED_INSIDE = [
    "使用说明.md",
    "tools/start.py", "tools/bootstrap.py", "tools/hf_download.py",
    "web/server.py", "web/static/index.html", "docs/style-terms.md",
    "pyproject.toml",
]


def detect_platform(sys_platform: str | None = None, os_name: str | None = None) -> str | None:
    """Infer the package platform from the build machine, or None when unknown."""
    sys_platform = sys.platform if sys_platform is None else sys_platform
    os_name = os.name if os_name is None else os_name
    if sys_platform == "darwin":
        return "macos"
    if os_name == "nt":
        return "win-x64"
    return None


def launcher_name(platform: str) -> str:
    return LAUNCHERS[platform]


def other_launcher_name(platform: str) -> str:
    return OTHER_LAUNCHERS[platform]


def package_zip_name(platform: str, stamp: str | None = None) -> str:
    stamp = stamp or datetime.date.today().strftime("%Y%m%d")
    return f"{PACKAGE_NAME}-{stamp}-{platform}.zip"


def runtime_python(pkg: Path, platform: str) -> Path:
    """Interpreter path inside a bundled package."""
    return pkg / "runtime" / ("python.exe" if platform == "win-x64" else "bin/python3")


def env_dir(pkg: Path, name: str) -> Path:
    return pkg / "envs" / name


def cache_dir() -> Path:
    override = os.environ.get("YUE2_ONECLICK_CACHE")
    if override:
        return Path(override)
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "yue2-oneclick"
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home())
        return Path(base) / "yue2-oneclick"
    return Path.home() / ".cache" / "yue2-oneclick"


def _download(url: str, target: Path):
    target.parent.mkdir(parents=True, exist_ok=True)
    print(f"  download: {url}")
    with urllib.request.urlopen(url, timeout=300) as response, \
            target.open("wb") as handle:
        shutil.copyfileobj(response, handle, length=1 << 20)


def fetch_runtime_archive(platform: str) -> Path:
    """Download (once) the portable CPython tarball for the target platform."""
    triple = PBS_TRIPLES[platform]
    name = f"cpython-{PBS_VERSION}+{PBS_TAG}-{triple}-install_only_stripped.tar.gz"
    cache = cache_dir()
    archive = cache / name
    if archive.exists() and archive.stat().st_size > 0:
        print(f"  reuse cached runtime: {archive}")
        return archive
    url = PBS_URL.format(tag=PBS_TAG, version=PBS_VERSION, triple=triple)
    _download(url, archive.with_suffix(".part"))
    archive.with_suffix(".part").replace(archive)
    return archive


def extract_runtime(archive: Path, pkg: Path):
    """Extract the tarball's top-level ``python/`` tree into ``pkg/runtime``."""
    runtime = pkg / "runtime"
    if runtime.exists():
        shutil.rmtree(runtime)
    with tempfile.TemporaryDirectory(prefix="yue2-pbs-") as work:
        with tarfile.open(archive, "r:gz") as tar:
            tar.extractall(work, filter="data")
        source = Path(work) / "python"
        if not source.is_dir():
            raise SystemExit(f"portable runtime archive has no python/ root: {archive}")
        shutil.move(str(source), str(runtime))
    print(f"  + runtime/ ({runtime})")


def bundle_requirements() -> list[str]:
    """Runtime dependencies = pyproject deps + [web] extras + torchaudio (pinned).

    Keeping this derived from pyproject avoids a second pin list drifting out of
    date; torchaudio uses the same version as torch for the audio transcribe env.
    """
    with (ROOT / "pyproject.toml").open("rb") as handle:
        project = tomllib.load(handle)["project"]
    requirements = list(project.get("dependencies", []))
    requirements += list(project.get("optional-dependencies", {}).get("web", []))
    torch_pin = next((req for req in requirements if req.startswith("torch==")), None)
    if torch_pin is None:
        raise SystemExit("pyproject.toml must pin torch with == for bundling")
    requirements.append("torchaudio" + torch_pin[len("torch"):])
    return requirements


def pip_install(target: Path, requirements: list[str], runtime: Path):
    target.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["PYTHONNOUSERSITE"] = "1"
    env["PYTHONUTF8"] = "1"
    env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    cmd = [str(runtime), "-m", "pip", "install", "--quiet", "--no-warn-script-location",
           "--target", str(target), *requirements]
    subprocess.run(cmd, check=True, env=env)


def bundle_envs(pkg: Path, platform: str):
    runtime = runtime_python(pkg, platform)
    if not runtime.exists():
        raise SystemExit(f"bundled runtime interpreter missing: {runtime}")
    print("  installing envs/web …")
    pip_install(env_dir(pkg, "web"), bundle_requirements(), runtime)
    print("  + envs/web/")
    if platform == "macos":
        print("  installing envs/mlx …")
        pip_install(env_dir(pkg, "mlx"), list(MLX_PINS), runtime)
        print("  + envs/mlx/")


def verify_runtime_imports(pkg: Path, platform: str):
    runtime = runtime_python(pkg, platform)
    env = dict(os.environ)
    env["PYTHONNOUSERSITE"] = "1"
    env["PYTHONUTF8"] = "1"
    env["PYTHONPATH"] = os.pathsep.join(
        [str(env_dir(pkg, "web")), str(pkg / "src")])
    check = ("import torch, transformers, fastapi, uvicorn, soundfile, numpy; "
             "import yue2; print(torch.__version__)")
    result = subprocess.run([str(runtime), "-c", check], capture_output=True,
                            text=True, env=env)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()[-2000:]
        raise SystemExit(f"bundled runtime self-check failed: {detail}")
    print(f"  self-check ok (torch {result.stdout.strip()})")


def copy_tree(src: Path, dest: Path):
    shutil.copytree(src, dest, ignore=shutil.ignore_patterns(*EXCLUDE_PATTERNS),
                    dirs_exist_ok=True)


def strip_user_data(pkg: Path):
    """web/data holds the user's library, uploads and settings — never ships."""
    data = pkg / "web" / "data"
    if data.exists():
        shutil.rmtree(data)
        print("  - web/data (user data excluded)")


def stage_source(stage_root: Path, platform: str) -> Path:
    pkg = stage_root / PACKAGE_NAME
    pkg.mkdir(parents=True)
    for name in INCLUDE_ROOTS:
        src = ROOT / name
        if not src.exists():
            print(f"  skip missing: {name}")
            continue
        copy_tree(src, pkg / name)
        print(f"  + {name}/")
    for name in INCLUDE_FILES:
        src = ROOT / name
        if not src.exists():
            print(f"  skip missing: {name}")
            continue
        shutil.copy2(src, pkg / name)
        print(f"  + {name}")
    wanted = launcher_name(platform)
    for launcher in sorted((PACKAGING / "launchers").iterdir()):
        if launcher.name != wanted:
            continue
        shutil.copy2(launcher, pkg / launcher.name)
        if launcher.suffix == ".command":
            (pkg / launcher.name).chmod(0o755)
        print(f"  + {launcher.name} (launcher)")
    if not (pkg / wanted).exists():
        raise SystemExit(f"launcher {wanted} missing from packaging/launchers/")
    shutil.copy2(PACKAGING / "使用说明.md", pkg / "使用说明.md")
    print("  + 使用说明.md")
    strip_user_data(pkg)
    return pkg


def scan_forbidden(pkg: Path):
    hits = []
    for path in pkg.rglob("*"):
        rel = path.relative_to(pkg).as_posix()
        for bad in FORBIDDEN:
            if rel == bad or rel.startswith(bad + "/"):
                hits.append(rel)
                break
    if hits:
        raise SystemExit(f"FORBIDDEN content inside the package: {hits[:8]} (build aborted)")


def self_check(pkg: Path, platform: str, runtime: str):
    missing = [name for name in REQUIRED_INSIDE if not (pkg / name).exists()]
    wanted = launcher_name(platform)
    if not (pkg / wanted).exists():
        missing.append(wanted)
    if runtime == "bundle":
        if not runtime_python(pkg, platform).exists():
            missing.append("runtime/<python>")
        if not (env_dir(pkg, "web") / "torch").is_dir():
            missing.append("envs/web/torch")
        if platform == "macos" and not (env_dir(pkg, "mlx") / "mlx").is_dir():
            missing.append("envs/mlx/mlx")
    if missing:
        raise SystemExit(f"Package is incomplete, missing: {missing}")
    stray = other_launcher_name(platform)
    if (pkg / stray).exists():
        raise SystemExit(f"Package must not contain the {stray} launcher (platform {platform})")
    # The POSIX launcher can only be validated on a POSIX host (exec bit and
    # bash syntax); Windows runners cannot build the macos package anyway.
    if platform == "macos" and sys.platform != "win32":
        launcher = pkg / wanted
        if not launcher.stat().st_mode & 0o111:
            raise SystemExit("start.command lost its executable bit")
        if shutil.which("bash"):
            check = subprocess.run(["bash", "-n", str(launcher)],
                                   capture_output=True, text=True)
            if check.returncode != 0:
                detail = (check.stderr or check.stdout).strip()
                raise SystemExit(f"start.command failed syntax check: {detail}")


def make_zip(pkg: Path, out_dir: Path, platform: str) -> tuple[Path, int]:
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / package_zip_name(platform)
    if out.exists():
        out.unlink()
    total_files = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
        for path in sorted(pkg.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(pkg.parent))
                total_files += 1
    if out.stat().st_size > MAX_ZIP_BYTES:
        raise SystemExit(f"package exceeds the GitHub asset budget: "
                         f"{out.stat().st_size / 2 ** 30:.2f} GiB > "
                         f"{MAX_ZIP_BYTES / 2 ** 30:.2f} GiB")
    return out, total_files


def check_style_terms():
    """Ship only the current glossary: fail when docs/style-terms.md is stale."""
    result = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "export_style_terms.py"), "--check"],
        capture_output=True, text=True)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise SystemExit("docs/style-terms.md is out of date with the dictionary — "
                         f"run: python tools/export_style_terms.py\n{detail}")
    print(f"  {result.stdout.strip()}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--platform", choices=PLATFORMS, default=None,
                    help="target platform (default: infer from the build machine)")
    ap.add_argument("--runtime", choices=RUNTIMES, default="bundle",
                    help="bundle = self-contained (default); slim = source-only for dev")
    ap.add_argument("--keep-stage", action="store_true", help="Keep the staging directory for inspection")
    ap.add_argument("--out-dir", type=Path, default=None,
                    help="Override the output directory")
    ap.add_argument("--scan-only", type=Path, help="Run the forbidden-content scan against an existing directory")
    args = ap.parse_args()

    if args.scan_only:
        scan_forbidden(args.scan_only)
        print(f"scan passed: {args.scan_only}")
        return 0

    target = args.platform or detect_platform()
    if target is None:
        raise SystemExit("无法判定构建平台，请显式指定 --platform macos|win-x64")
    out_dir = args.out_dir or ROOT / "oneclick-packages" / target
    check_style_terms()
    stage_root = Path(tempfile.mkdtemp(prefix="yue2-oneclick-"))
    print(f"build: {args.runtime} {target} package | staging: {stage_root}")
    try:
        pkg = stage_source(stage_root, target)
        if args.runtime == "bundle":
            extract_runtime(fetch_runtime_archive(target), pkg)
            bundle_envs(pkg, target)
            verify_runtime_imports(pkg, target)
        scan_forbidden(pkg)
        self_check(pkg, target, args.runtime)
        out, files = make_zip(pkg, out_dir, target)
        size_mb = out.stat().st_size / 2 ** 20
        print(f"\nbuilt: {out}  ({size_mb:.0f} MiB, {files} files)")
        print(HOOKS_MESSAGE)
        return 0
    finally:
        if args.keep_stage:
            print(f"stage kept at {stage_root}")
        else:
            shutil.rmtree(stage_root, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
