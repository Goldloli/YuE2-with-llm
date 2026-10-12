#!/usr/bin/env python3
"""Real-audio CLI: encode audio into YuE2 semantic tokens, or rebuild audio from them.

    python tools/realaudio.py encode  <audio> --output tokens.npy
    python tools/realaudio.py rebuild tokens.npy --output out.flac [--style ... --lyrics ...]

`encode` runs inside the transcription environment (.venv-sheetsage2, MERT +
head); `rebuild` runs the torch pipeline with the NAR LoRA folded, restoring
the resident model afterwards.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHEETSAGE_PY = ROOT / ".venv-sheetsage2" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
ENCODE_SCRIPT = ROOT / "tools" / "realaudio_encode.py"
DEFAULT_NAR_LORA = ROOT / "models" / "YuE2-Realaudio" / "nar_lora_joint_v9.bf16.safetensors"


def cmd_encode(args):
    cmd = [str(SHEETSAGE_PY), str(ENCODE_SCRIPT), str(args.audio), "--output", str(args.output)]
    if args.device:
        cmd += ["--device", args.device]
    proc = subprocess.run(cmd, cwd=str(ROOT))
    return proc.returncode


def cmd_rebuild(args):
    sys.path.insert(0, str(ROOT / "src"))
    import numpy as np
    import soundfile as sf
    from yue2.pipeline import YuE2Pipeline
    from yue2.realaudio import nar_lora_applied, render_tokens

    codes = np.load(args.tokens)
    model = ROOT / "models" / "YuE2-3B"
    t0 = time.perf_counter()
    pipe = YuE2Pipeline.from_pretrained(str(model), vae=str(ROOT / "models" / "YuE2-Vae"),
                                        device="auto", local_files_only=model.exists(), progress=False)
    try:
        with nar_lora_applied(pipe, args.nar_lora or DEFAULT_NAR_LORA):
            audio, latents = render_tokens(pipe, codes, style=args.style or "", lyrics=args.lyrics or "")
    finally:
        pipe.close()
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(out), audio, 48000, subtype="PCM_24")
    report = {"tokens": int(np.asarray(codes).size), "seconds": round(len(audio) / 48000, 2),
              "wall_seconds": round(time.perf_counter() - t0, 1), "output": str(out)}
    print(json.dumps(report, ensure_ascii=False), flush=True)
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="command", required=True)
    enc = sub.add_parser("encode", help="audio -> semantic tokens (transcription env)")
    enc.add_argument("audio", type=Path)
    enc.add_argument("--output", type=Path, required=True)
    enc.add_argument("--device", default="cpu")
    enc.set_defaults(func=cmd_encode)
    reb = sub.add_parser("rebuild", help="semantic tokens -> rendered audio (torch pipeline)")
    reb.add_argument("tokens", type=Path)
    reb.add_argument("--output", type=Path, required=True)
    reb.add_argument("--nar-lora", type=Path, default=None)
    reb.add_argument("--style", default="")
    reb.add_argument("--lyrics", default="")
    reb.set_defaults(func=cmd_rebuild)
    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
