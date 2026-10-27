#!/usr/bin/env python3
"""One-shot setup for YuE2 Studio (Windows / macOS / Linux).

    python tools/bootstrap.py            # interactive
    python tools/bootstrap.py --yes      # accept all defaults
    python tools/bootstrap.py --yes --extras --transcribe
    python tools/bootstrap.py --skip-models --skip-deps   # check only

Creates .venv, installs the pinned dependencies (torch from PyPI by default;
set YUE2_TORCH_INDEX to pick a specific CUDA wheel index), and downloads the
required models. Everything is idempotent: existing pieces are reused.
"""
from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENV = ROOT / ".venv"
SHEETSAGE_VENV = ROOT / ".venv-sheetsage2"
MLX_VENV = ROOT / ".venv-mlx"
MIN_PYTHON = (3, 10)

sys.path.insert(0, str(ROOT / "tools"))


def venv_python(venv: Path) -> Path:
    return venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def run(cmd, **kwargs):
    print("  $", " ".join(str(c) for c in cmd))
    subprocess.run([str(c) for c in cmd], check=True, **kwargs)


def ask(question, default=True, assume_yes=False):
    if assume_yes:
        return default
    answer = input(f"{question} [{'Y/n' if default else 'y/N'}] ").strip().lower()
    if not answer:
        return default
    return answer in {"y", "yes"}


def ensure_python():
    if sys.version_info < MIN_PYTHON:
        raise SystemExit(
            f"Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+ is required, found {sys.version.split()[0]}.\n"
            "Windows: install from https://www.python.org/downloads/  ·  macOS: brew install python@3.12")
    print(f"Python {sys.version.split()[0]} at {sys.executable}")


def ensure_venv():
    py = venv_python(VENV)
    if py.exists():
        print(f"Reusing {VENV.name}")
        return py
    print(f"Creating {VENV.name} …")
    run([sys.executable, "-m", "venv", str(VENV)])
    return py


def install_deps(py: Path):
    marker = VENV / ".deps-installed"
    if marker.exists():
        print("Dependencies already installed (delete .venv/.deps-installed to redo)")
        return
    run([py, "-m", "pip", "install", "-q", "--upgrade", "pip"])
    index = os.environ.get("YUE2_TORCH_INDEX")
    if index:
        run([py, "-m", "pip", "install", "torch==2.10.0", "--index-url", index])
    run([py, "-m", "pip", "install", "-e", f"{ROOT}[web]"])
    marker.write_text("ok\n", encoding="utf-8")


def core_ready() -> bool:
    model = ROOT / "models" / "YuE2-3B" / "model.safetensors"
    vae = ROOT / "models" / "YuE2-Vae" / "model.safetensors"
    return model.exists() and model.stat().st_size > 7_000_000_000 and vae.exists()


def mlx_variants() -> list:
    mlx_dir = ROOT / "models" / "YuE2-3B-MLX"
    if not mlx_dir.exists():
        return []
    return sorted(p.parent.name for p in mlx_dir.glob("*/model.safetensors"))


def any_engine_ready() -> bool:
    """A usable inference engine exists: torch core or any MLX variant."""
    return core_ready() or bool(mlx_variants())


def bundled_package() -> bool:
    """True for model-embedded bundles (marker written by build_model_bundle.py).

    Optional components not shipped in the bundle are fetched later from the
    in-app Models page instead of being re-downloaded on first run.
    """
    return (ROOT / "models" / ".bundle").exists()


def download(mode: str):
    import hf_download
    hf_download.run(mode)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--yes", action="store_true", help="accept defaults, no prompts")
    parser.add_argument("--extras", action="store_true", help="also fetch legacy decoder + LoRA adapters")
    parser.add_argument("--transcribe", action="store_true", help="also set up audio transcription (SheetSage2)")
    parser.add_argument("--mlx", action="store_true", help="also set up the Apple MLX engine (macOS only)")
    parser.add_argument("--skip-deps", action="store_true")
    parser.add_argument("--skip-models", action="store_true")
    args = parser.parse_args()

    ensure_python()

    if not args.skip_deps:
        py = ensure_venv()
        install_deps(py)

    if not args.skip_models:
        bundled = bundled_package()
        if any_engine_ready():
            print("Models present (engine ready)")
        else:
            print("Downloading core models (YuE2-3B + YuE2-Vae, about 7.3 GiB) …")
            download("core")

        want_extras = args.extras or (not bundled and ask(
            "Fetch extras (legacy decoder + LoRA adapters, ~1.4 GiB)?",
            default=True, assume_yes=args.yes))
        if want_extras and not (ROOT / "models" / "YuE2-Vae-legacy" / "model.safetensors").exists():
            download("extras")

        want_mlx = args.mlx or (sys.platform == "darwin" and platform.machine() == "arm64" and ask(
            "Set up the MLX engine (Apple Silicon, ~4.2 GiB, about 5x faster)?",
            default=True, assume_yes=args.yes))
        if want_mlx:
            if not venv_python(MLX_VENV).exists():
                run([sys.executable, "-m", "venv", str(MLX_VENV)])
                run([venv_python(MLX_VENV), "-m", "pip", "install", "-q", "mlx", "tiktoken", "numpy", "soundfile"])
            if not mlx_variants():
                download("mlx")

        want_transcribe = args.transcribe or (not bundled and ask(
            "Set up audio transcription (uploads/covers, ~2.6 GiB)?",
            default=True, assume_yes=args.yes))
        if want_transcribe:
            if not venv_python(SHEETSAGE_VENV).exists():
                run([sys.executable, "-m", "venv", str(SHEETSAGE_VENV)])
                run([venv_python(SHEETSAGE_VENV), "-m", "pip", "install", "-q",
                     "torch", "torchaudio", "transformers", "safetensors", "numpy", "soundfile"])
            if not (ROOT / "models" / "SheetSage2" / "model.safetensors").exists():
                download("transcribe")

    print("\nSetup complete. Start YuE2 Studio with:")
    if os.name == "nt":
        print("  start.bat          (or: %s tools\\start.py)" % sys.executable)
    else:
        print("  ./start.command    (or: %s tools/start.py)" % sys.executable)


if __name__ == "__main__":
    main()
