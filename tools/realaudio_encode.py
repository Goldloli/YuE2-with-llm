#!/usr/bin/env python3
"""Encode real audio into YuE2 semantic tokens (MERT-v2-FullSong L20 + v9 head).

Runs inside the transcription environment (.venv-sheetsage2) where torch,
torchaudio, scipy and transformers are pinned; the main environment stays
untouched. Mirrors the publisher's feature pipeline: 24 kHz mono, 30-second
MERT chunks, hidden_states[20], linear interpolation to 25 Hz, per-track
instance normalisation, then 512-frame head windows with greedy argmax.

Emits JSON progress lines ({"phase": ...}) on stdout.
"""
from __future__ import annotations

import argparse
import json
import sys
import time

from pathlib import Path

import numpy as np
import torch

WIN = 512
D_MODEL = 512
VOCAB = 32768
MERT_LAYER = 20


def emit(obj):
    print(json.dumps(obj), flush=True)


class Head(torch.nn.Module):
    """The v9 tokenizer head: Linear(1024->512) + pos + 8x TransformerEncoderLayer."""

    def __init__(self, din=1024):
        super().__init__()
        self.inp = torch.nn.Linear(din, D_MODEL)
        self.pos = torch.nn.Parameter(torch.zeros(1, WIN, D_MODEL))
        layer = torch.nn.TransformerEncoderLayer(D_MODEL, 8, 4 * D_MODEL, dropout=0.2,
                                                 batch_first=True, norm_first=True,
                                                 activation="gelu")
        self.enc = torch.nn.TransformerEncoder(layer, 8)
        self.norm = torch.nn.LayerNorm(D_MODEL)
        self.head = torch.nn.Linear(D_MODEL, VOCAB)

    def forward(self, x):
        return self.head(self.norm(self.enc(self.inp(x) + self.pos[:, : x.shape[1]])))


def load_head(path, device):
    from safetensors.torch import load_file
    state = load_file(str(path), device="cpu")
    model = Head()
    model.load_state_dict({k: v.float() for k, v in state.items()})
    return model.eval().to(device)


def load_audio_24k(path):
    """Decode to 24 kHz mono f32 via ffmpeg (the transcription stack's proven path)."""
    import shutil
    import subprocess
    if not shutil.which("ffmpeg"):
        raise RuntimeError("FFmpeg is required to read audio files; install it and add it to PATH")
    cmd = ["ffmpeg", "-v", "error", "-nostdin", "-i", str(Path(path).resolve()),
           "-vn", "-ac", "1", "-ar", "24000", "-f", "f32le", "pipe:1"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    if not raw:
        raise ValueError("No audio decoded from the input file")
    return np.frombuffer(raw, dtype=np.float32).copy()


def mert_layer20(model, proc, mono, device, chunk_seconds=30):
    sr_t = 24000
    chunk = sr_t * chunk_seconds
    pieces = [mono[s:s + chunk] for s in range(0, len(mono), chunk)]
    pieces = [p for p in pieces if len(p) >= sr_t]
    full = [p for p in pieces if len(p) == chunk]
    tail = [p for p in pieces if len(p) < chunk]
    feats = []
    with torch.inference_mode():
        for group in ([full] if full else []) + [[p] for p in tail]:
            inputs = proc(group, sampling_rate=sr_t, return_tensors="pt")
            inputs = {k: v.to(device) for k, v in inputs.items()}
            out = model(**inputs, output_hidden_states=True)
            feats.append(out.hidden_states[MERT_LAYER].reshape(-1, 1024))
    hidden = torch.cat(feats, 0).float()
    frames25 = int(round(len(mono) / sr_t * 25))
    if frames25 <= 0:
        raise ValueError("Audio is too short to tokenize")
    return torch.nn.functional.interpolate(hidden.T[None], size=frames25, mode="linear",
                                           align_corners=False)[0].T


def tokenize(head, features25, device):
    x = features25.numpy().astype(np.float32)
    x = (x - x.mean(0)) / (x.std(0) + 1e-5)  # per-track instance normalisation
    codes = []
    total = x.shape[0]
    with torch.inference_mode():
        for start in range(0, total, WIN):
            window = x[start:start + WIN]
            pad = WIN - len(window)
            if pad:
                window = np.pad(window, ((0, pad), (0, 0)))
            logits = head(torch.tensor(window[None], device=device))
            codes.append(logits.argmax(-1)[0][: WIN - pad].cpu().numpy())
    return np.concatenate(codes).astype(np.int32)


def run(args):
    device = args.device
    torch.set_num_threads(args.threads)
    model_root = Path(args.model_root)
    mert_dir = model_root / "MERT-v2-FullSong"
    head_path = Path(args.head) if args.head else model_root / "YuE2-Realaudio" / "tokenizer_head_joint_v9.bf16.safetensors"

    t0 = time.perf_counter()
    emit({"phase": "loading"})
    from transformers import AutoFeatureExtractor, AutoModel
    proc = AutoFeatureExtractor.from_pretrained(str(mert_dir), trust_remote_code=True,
                                                local_files_only=True)
    mert = AutoModel.from_pretrained(str(mert_dir), trust_remote_code=True,
                                     local_files_only=True).eval().to(device)
    head = load_head(head_path, device)

    mono = load_audio_24k(args.audio)
    seconds = len(mono) / 24000
    emit({"phase": "mert", "seconds": round(seconds, 1)})
    features = mert_layer20(mert, proc, mono, device)

    emit({"phase": "tokenizing", "frames25": int(features.shape[0])})
    codes = tokenize(head, features, device)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    np.save(out, codes)
    emit({"phase": "done", "tokens": int(codes.shape[0]), "seconds": round(seconds, 1),
          "wall_seconds": round(time.perf_counter() - t0, 1), "output": str(out)})


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("audio", type=Path)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--model-root", type=Path, default=Path(__file__).resolve().parents[1] / "models")
    ap.add_argument("--head", type=Path, help="Override the tokenizer head safetensors path")
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--threads", type=int, default=8)
    args = ap.parse_args()
    try:
        run(args)
        return 0
    except Exception as exc:  # noqa: BLE001 - report any failure to the caller
        import traceback
        traceback.print_exc()
        emit({"phase": "error", "error": f"{type(exc).__name__}: {exc}"})
        return 2


if __name__ == "__main__":
    sys.exit(main())
