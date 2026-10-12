#!/usr/bin/env python3
"""Build the YuE2 Studio one-click package into oneclick-packages/.

Default: a slim universal bundle (launchers + usage guide + source, ~10 MiB).
Models are downloaded on first run (bootstrap) and managed afterwards from the
in-app Models page.

Opt-in big bundles with embedded weights (`--with-models`):

    --with-models --platform macos     all models (torch + MLX + extras), ~23 GB
    --with-models --platform win-x64   all torch models (no YuE2-3B-MLX), ~12.4 GB

In model mode, weights are written into the archive *directly from the repo*
with STORED (no recompression, no double IO).

    python packaging/build_package.py [--with-models --platform macos] [--keep-stage]
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

ROOT = Path(__file__).resolve().parents[1]
PACKAGING = ROOT / "packaging"
PACKAGE_NAME = "yue2-studio-oneclick"

PLATFORMS = {
    "macos": {"label": "macos-applesilicon", "models": "all",
              "required_models": ["YuE2-3B/model.safetensors",
                                  "YuE2-Vae/model.safetensors",
                                  "YuE2-Vae-legacy/model.safetensors",
                                  "YuE2-Vae-merge/model.safetensors",
                                  "YuE2-3B-MLX/8bit/model.safetensors",
                                  "YuE2-3B-MLX/bf16/model.safetensors",
                                  "YuE2-Realaudio/nar_lora_joint_v9.bf16.safetensors",
                                  "MERT-v2-FullSong/config.json",
                                  "SheetSage2/config.json"],
              "forbidden_models": []},
    "win-x64": {"label": "win-x64", "models": "torch",
                "required_models": ["YuE2-3B/model.safetensors",
                                    "YuE2-Vae/model.safetensors",
                                    "YuE2-Vae-legacy/model.safetensors",
                                    "YuE2-Vae-merge/model.safetensors",
                                    "YuE2-Realaudio/nar_lora_joint_v9.bf16.safetensors",
                                    "MERT-v2-FullSong/config.json",
                                    "SheetSage2/config.json"],
                "forbidden_models": ["YuE2-3B-MLX"]},
}

# Models are pure weights; never recompress them (zip stores by extension below).
STORE_SUFFIXES = {".safetensors", ".npy", ".pt", ".ckpt", ".bin"}
MODEL_EXCLUDE = ["__pycache__", "*.pyc", ".DS_Store", "._*", "*.partial"]

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


def model_dirs(platform: str) -> list[str]:
    spec = PLATFORMS[platform]
    names = sorted(p.name for p in (ROOT / "models").iterdir() if p.is_dir())
    if spec["models"] == "torch":
        names = [n for n in names if n not in spec["forbidden_models"]]
    return names


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


def self_check(pkg: Path, platform: str):
    missing = [name for name in REQUIRED_INSIDE if not (pkg / name).exists()]
    if missing:
        raise SystemExit(f"Package is incomplete, missing: {missing}")
    launcher = pkg / "start.command"
    if sys.platform != "win32" and not launcher.stat().st_mode & 0o111:
        raise SystemExit("start.command lost its executable bit")
    if shutil.which("bash"):
        # Git Bash on Windows needs forward slashes in the path argument
        check = subprocess.run(["bash", "-n", str(launcher).replace("\\", "/")],
                               capture_output=True, text=True)
        if check.returncode != 0:
            raise SystemExit(f"start.command failed syntax check: {check.stderr.strip()}")


def check_models(platform: str):
    spec = PLATFORMS[platform]
    for rel in spec["required_models"]:
        if not (ROOT / "models" / rel).exists():
            raise SystemExit(f"Required model file missing from the repo: models/{rel}")
    for name in spec["forbidden_models"]:
        if (ROOT / "models" / name).exists() and name in model_dirs(platform):
            raise SystemExit(f"Platform {platform} must not bundle models/{name}")


def make_zip(pkg: Path, out_dir: Path, platform, with_models: bool) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.date.today().strftime("%Y%m%d")
    label = f"-{PLATFORMS[platform]['label']}" if with_models else ""
    out = out_dir / f"{PACKAGE_NAME}{label}-{stamp}.zip"
    if out.exists():
        out.unlink()
    total_files = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
        # 1) staged source
        for path in sorted(pkg.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(pkg.parent))
                total_files += 1
        # 2) models straight from the repo, uncompressed
        if with_models:
            import fnmatch
            for name in model_dirs(platform):
                base = ROOT / "models" / name
                print(f"  ~ models/{name}/ ...", flush=True)
                for path in sorted(base.rglob("*")):
                    if not path.is_file():
                        continue
                    if any(fnmatch.fnmatch(path.name, pat) for pat in MODEL_EXCLUDE):
                        continue
                    arcname = Path(PACKAGE_NAME) / "models" / name / path.relative_to(base)
                    zf.write(path, arcname,
                             compress_type=zipfile.ZIP_STORED
                             if path.suffix.lower() in STORE_SUFFIXES else zipfile.ZIP_DEFLATED)
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
    ap.add_argument("--with-models", action="store_true",
                    help="Opt-in big bundle with embedded model weights")
    ap.add_argument("--platform", choices=sorted(PLATFORMS), default=None,
                    help="Target platform for --with-models (default macos)")
    ap.add_argument("--keep-stage", action="store_true", help="Keep the staging directory for inspection")
    ap.add_argument("--skip-models", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--out-dir", type=Path, default=None,
                    help="Override the output directory")
    ap.add_argument("--scan-only", type=Path, help="Run the forbidden-content scan against an existing directory")
    args = ap.parse_args()

    if args.scan_only:
        scan_forbidden(args.scan_only)
        print(f"scan passed: {args.scan_only}")
        return 0

    with_models = args.with_models and not args.skip_models
    platform = args.platform or ("macos" if with_models else None)
    if args.platform and not with_models:
        raise SystemExit("--platform only applies to --with-models bundles")
    if with_models:
        out_dir = args.out_dir or ROOT / "oneclick-packages" / platform
        check_models(platform)
    else:
        out_dir = args.out_dir or ROOT / "oneclick-packages"

    check_style_terms()
    stage_root = Path(tempfile.mkdtemp(prefix="yue2-oneclick-"))
    mode = f"models embedded ({platform})" if with_models else "source only (slim)"
    print(f"build: {mode} | staging: {stage_root}")
    try:
        pkg = stage_source(stage_root)
        scan_forbidden(pkg)
        self_check(pkg, platform)
        out, files = make_zip(pkg, out_dir, platform, with_models)
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
