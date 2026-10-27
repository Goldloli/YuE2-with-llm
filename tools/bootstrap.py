#!/usr/bin/env python3
"""Environment setup for YuE2 Studio (Windows / macOS / Linux).

The one-click package never embeds model weights: the first launch only
prepares the environment, then the studio opens on the **Models** page where
each component is downloaded on demand, with a switchable download channel
(domestic mirror hf-mirror.com or direct huggingface.co).

    python tools/bootstrap.py                    # environment only (what the launcher runs)
    python tools/bootstrap.py --models           # also download the core models (~7.3 GiB)
    python tools/bootstrap.py --models --extras --transcribe --mlx
    python tools/bootstrap.py --models --download-source huggingface
    python tools/bootstrap.py --skip-deps --skip-models     # check only

Creates `.venv`, installs the pinned dependencies (torch from PyPI by default;
set YUE2_TORCH_INDEX to pick a specific CUDA wheel index) and, on Apple Silicon,
the MLX runtime. Everything is idempotent: existing pieces are reused.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENV = ROOT / ".venv"
SHEETSAGE_VENV = ROOT / ".venv-sheetsage2"
MLX_VENV = ROOT / ".venv-mlx"
MIN_PYTHON = (3, 10)

CHANNELS = ("mirror", "huggingface")
DEFAULT_CHANNEL = "mirror"

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


def settings_file() -> Path:
    return ROOT / "web" / "data" / "settings.json"


def saved_channel() -> str | None:
    """Download channel persisted by the app's Models page, if any."""
    try:
        data = json.loads(settings_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    source = data.get("download_source") if isinstance(data, dict) else None
    return source if source in CHANNELS else None


def save_channel(source: str):
    """Persist the channel so the studio's Models page starts on the same one."""
    if source not in CHANNELS:
        return
    path = settings_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {}
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
    if not isinstance(data, dict):
        data = {}
    data["download_source"] = source
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def choose_channel(assume_yes: bool, fixed: str | None = None) -> str:
    """Pick the download channel (interactive once, then remembered)."""
    if fixed in CHANNELS:
        return fixed
    current = saved_channel()
    if current:
        print(f"下载渠道（已保存）：{'国内镜像 hf-mirror.com' if current == 'mirror' else '国际直连 huggingface.co'}")
        return current
    current = DEFAULT_CHANNEL
    if assume_yes or not sys.stdin.isatty():
        return current
    print("\n下载渠道 / Download source:")
    print("  1) 国内网络 — hf-mirror.com（大陆直连，默认）")
    print("  2) 国外网络 — huggingface.co（海外或可访问外网）")
    hint = "1" if current == DEFAULT_CHANNEL else "2"
    while True:
        answer = input(f"请选择 [1/2] ({hint}): ").strip().lower()
        if not answer:
            selected = current
            break
        if answer in {"1", "mirror", "cn", "国内"}:
            selected = "mirror"
            break
        if answer in {"2", "huggingface", "hf", "国外"}:
            selected = "huggingface"
            break
        print("请输入 1 或 2")
    save_channel(selected)
    print(f"下载渠道：{'国内镜像 hf-mirror.com' if selected == 'mirror' else '国际直连 huggingface.co'}")
    return selected


def download(mode: str, channel: str | None = None):
    import hf_download
    endpoint, label = hf_download.resolve_endpoint(source=channel)
    hf_download.set_endpoint(endpoint)
    print(f"download source: {label} ({endpoint})")
    hf_download.run(mode)


def ensure_mlx_runtime():
    """Install the MLX Python runtime (no weights; macOS Apple Silicon only)."""
    if not (sys.platform == "darwin" and platform.machine() == "arm64"):
        return
    if venv_python(MLX_VENV).exists():
        return
    print("Setting up the MLX runtime (Apple Silicon) …")
    run([sys.executable, "-m", "venv", str(MLX_VENV)])
    run([venv_python(MLX_VENV), "-m", "pip", "install", "-q",
         "mlx", "tiktoken", "numpy", "soundfile"])


def setup_models(source: str | None = None, extras=False, transcribe=False,
                 mlx=False, assume_yes=False):
    """Download model components (only when the user asked for them)."""
    channel = choose_channel(assume_yes=assume_yes, fixed=source)
    if any_engine_ready():
        print("Models present (engine ready)")
    else:
        print("Downloading core models (YuE2-3B + YuE2-Vae, about 7.3 GiB) …")
        download("core", channel)

    want_extras = extras or ask(
        "Fetch extras (legacy decoder + LoRA adapters, ~1.4 GiB)?",
        default=True, assume_yes=assume_yes)
    if want_extras and not (ROOT / "models" / "YuE2-Vae-legacy" / "model.safetensors").exists():
        download("extras", channel)

    want_mlx = mlx or (sys.platform == "darwin" and platform.machine() == "arm64" and ask(
        "Download the MLX weights (Apple Silicon, ~4.2 GiB, about 5x faster)?",
        default=True, assume_yes=assume_yes))
    if want_mlx:
        ensure_mlx_runtime()
        if not mlx_variants():
            download("mlx", channel)

    want_transcribe = transcribe or ask(
        "Set up audio transcription (uploads/covers, ~2.6 GiB)?",
        default=True, assume_yes=assume_yes)
    if want_transcribe:
        if not venv_python(SHEETSAGE_VENV).exists():
            run([sys.executable, "-m", "venv", str(SHEETSAGE_VENV)])
            run([venv_python(SHEETSAGE_VENV), "-m", "pip", "install", "-q",
                 "torch", "torchaudio", "transformers", "safetensors", "numpy", "soundfile"])
        if not (ROOT / "models" / "SheetSage2" / "model.safetensors").exists():
            download("transcribe", channel)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--yes", action="store_true", help="accept defaults, no prompts")
    parser.add_argument("--models", action="store_true",
                        help="download the core models now (~7.3 GiB); the app does it otherwise")
    parser.add_argument("--extras", action="store_true", help="also fetch legacy decoder + LoRA adapters")
    parser.add_argument("--transcribe", action="store_true", help="also set up audio transcription (SheetSage2)")
    parser.add_argument("--mlx", action="store_true", help="also fetch the Apple MLX weights (macOS only)")
    parser.add_argument("--download-source", choices=CHANNELS, default=None,
                        help="download channel for --models: mirror (domestic) or huggingface (overseas)")
    parser.add_argument("--skip-deps", action="store_true")
    parser.add_argument("--skip-models", action="store_true",
                        help="environment only (default; model downloads live in the app)")
    args = parser.parse_args()

    ensure_python()

    if not args.skip_deps:
        py = ensure_venv()
        install_deps(py)
        ensure_mlx_runtime()

    wants_models = bool(args.models or args.extras or args.transcribe or args.mlx)
    if args.skip_models:
        wants_models = False
    elif not wants_models and not args.yes:
        wants_models = ask(
            "现在下载核心模型（YuE2-3B + YuE2-Vae，约 7.3 GiB）？\n"
            "也可以稍后在应用「模型」页下载（可选国内/国外下载源）",
            default=False, assume_yes=False)

    if wants_models:
        setup_models(source=args.download_source, extras=args.extras,
                     transcribe=args.transcribe, mlx=args.mlx, assume_yes=args.yes)
    else:
        print("\n未下载模型：启动 YuE2 Studio 后，在左侧「模型」页按需下载。")
        print("下载源可在页面切换：国内镜像 hf-mirror.com / 国际直连 huggingface.co。")
        if not any_engine_ready():
            print("提示：首次生成前需要先下载「核心模型」（约 7.3 GiB）。")

    print("\nSetup complete. Start YuE2 Studio with:")
    if os.name == "nt":
        print("  start.bat          (or: %s tools\\start.py)" % sys.executable)
    else:
        print("  ./start.command    (or: %s tools/start.py)" % sys.executable)


if __name__ == "__main__":
    main()
