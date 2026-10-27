#!/usr/bin/env python3
"""Build the YuE2 Studio one-click package into oneclick-packages/.

The package is always a slim universal bundle (launchers + usage guide + source,
~10 MiB). It never embeds model weights: after the first launch the app opens the
Models page, where the user downloads what they need and picks a download
channel (domestic mirror hf-mirror.com or direct huggingface.co).

    python packaging/build_package.py [--keep-stage]
"""
from __future__ import annotations

import argparse
import datetime
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

try:  # Windows consoles may default to a legacy code page that cannot print CJK
    sys.stdout.reconfigure(errors="replace")
except (AttributeError, ValueError):
    pass

ROOT = Path(__file__).resolve().parents[1]
PACKAGING = ROOT / "packaging"
PACKAGE_NAME = "yue2-studio-oneclick"

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
    "start.command", "start.bat", "使用说明.md",
    "tools/start.py", "tools/bootstrap.py", "tools/hf_download.py",
    "web/server.py", "web/static/index.html", "docs/style-terms.md",
    "pyproject.toml",
]


def copy_tree(src: Path, dest: Path):
    shutil.copytree(src, dest, ignore=shutil.ignore_patterns(*EXCLUDE_PATTERNS),
                    dirs_exist_ok=True)


def strip_user_data(pkg: Path):
    """web/data holds the user's library, uploads and settings — never ships."""
    data = pkg / "web" / "data"
    if data.exists():
        shutil.rmtree(data)
        print("  - web/data (user data excluded)")


def stage_source(stage_root: Path) -> Path:
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
    for launcher in sorted((PACKAGING / "launchers").iterdir()):
        shutil.copy2(launcher, pkg / launcher.name)
        if launcher.suffix == ".command":
            (pkg / launcher.name).chmod(0o755)
        print(f"  + {launcher.name} (launcher)")
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


def self_check(pkg: Path):
    missing = [name for name in REQUIRED_INSIDE if not (pkg / name).exists()]
    if missing:
        raise SystemExit(f"Package is incomplete, missing: {missing}")
    # The POSIX launcher can only be validated on a POSIX host (exec bit and
    # bash syntax); the macos runner covers the shared source tree.
    if sys.platform != "win32":
        launcher = pkg / "start.command"
        if not launcher.stat().st_mode & 0o111:
            raise SystemExit("start.command lost its executable bit")
        if shutil.which("bash"):
            check = subprocess.run(["bash", "-n", str(launcher)],
                                   capture_output=True, text=True)
            if check.returncode != 0:
                detail = (check.stderr or check.stdout).strip()
                raise SystemExit(f"start.command failed syntax check: {detail}")


def make_zip(pkg: Path, out_dir: Path) -> tuple[Path, int]:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.date.today().strftime("%Y%m%d")
    out = out_dir / f"{PACKAGE_NAME}-{stamp}.zip"
    if out.exists():
        out.unlink()
    total_files = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
        for path in sorted(pkg.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(pkg.parent))
                total_files += 1
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
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--keep-stage", action="store_true", help="Keep the staging directory for inspection")
    ap.add_argument("--out-dir", type=Path, default=None,
                    help="Override the output directory")
    ap.add_argument("--scan-only", type=Path, help="Run the forbidden-content scan against an existing directory")
    args = ap.parse_args()

    if args.scan_only:
        scan_forbidden(args.scan_only)
        print(f"scan passed: {args.scan_only}")
        return 0

    out_dir = args.out_dir or ROOT / "oneclick-packages"
    check_style_terms()
    stage_root = Path(tempfile.mkdtemp(prefix="yue2-oneclick-"))
    print(f"build: source only (slim) | staging: {stage_root}")
    try:
        pkg = stage_source(stage_root)
        scan_forbidden(pkg)
        self_check(pkg)
        out, files = make_zip(pkg, out_dir)
        size_gb = out.stat().st_size / 2 ** 30
        print(f"\nbuilt: {out}  ({size_gb:.2f} GiB, {files} files)")
        return 0
    finally:
        if args.keep_stage:
            print(f"stage kept at {stage_root}")
        else:
            shutil.rmtree(stage_root, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
