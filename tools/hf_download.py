#!/usr/bin/env python3
"""Portable YuE2 model downloader (Windows / macOS / Linux).

Fetches model files from hf-mirror.com with parallel ranged downloads, resume,
and SHA-256 verification against weights_manifest.json. No third-party deps.

    python tools/hf_download.py core      # YuE2-3B + YuE2-Vae (required)
    python tools/hf_download.py extras    # everything optional below, in one go
    python tools/hf_download.py mlx       # YuE2-3B-MLX 8-bit (Apple Silicon; alias of mlx-8bit)

Fine-grained modes (used by the web model manager):
    decoders | realaudio | lora-deathmetal | lora-jpop | lora-instrumental
    mlx-8bit | mlx-bf16 | mlx-4bit | transcribe

Set YUE2_HF_ENDPOINT to use a different mirror.
"""
from __future__ import annotations

import shutil
import subprocess

import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

BASE = os.environ.get("YUE2_HF_ENDPOINT", "https://hf-mirror.com").rstrip("/")
ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "models"
CHUNK = 8 << 20
WORKERS = 12

SMALL_FILES = {
    "m-a-p/YuE2-3B": ("YuE2-3B", [
        "config.json", "generation_config.json", "yue2_generation_config.json",
        "weights_manifest.json", "qwen.tiktoken", "modeling_yue2.py",
        "LICENSE", "THIRD_PARTY_NOTICES.md",
        "licenses/stable-audio-tools-MIT.txt", "licenses/SnakeBeta-NVIDIA-MIT.txt",
    ]),
    "m-a-p/YuE2-Vae": ("YuE2-Vae", [
        "config.json", "weights_manifest.json", "modeling_vae.py",
        "LICENSE", "THIRD_PARTY_NOTICES.md",
        "licenses/stable-audio-tools-MIT.txt", "licenses/SnakeBeta-NVIDIA-MIT.txt",
    ]),
    "m-a-p/YuE2-Vae-legacy": ("YuE2-Vae-legacy", [
        "config.json", "weights_manifest.json", "modeling_vae.py",
        "LICENSE", "THIRD_PARTY_NOTICES.md",
        "licenses/stable-audio-tools-MIT.txt", "licenses/SnakeBeta-NVIDIA-MIT.txt",
    ]),
}

PLANS = {
    "core": [
        ("m-a-p/YuE2-3B", "model.safetensors", "YuE2-3B/model.safetensors", 7261441640),
        ("m-a-p/YuE2-Vae", "model.safetensors", "YuE2-Vae/model.safetensors", 530512720),
    ],
    "extras": [
        ("m-a-p/YuE2-Vae-legacy", "model.safetensors", "YuE2-Vae-legacy/model.safetensors", 530512720),
        ("Mothersuperior/YuE2-Vae-merge-0.666", "model.safetensors",
         "YuE2-Vae-merge/model.safetensors", 530512792),
        ("Mothersuperior/yue2-mothersuperior-realaudio-tokenizer-v4",
         "tokenizer_head_joint_v9.bf16.safetensors",
         "YuE2-Realaudio/tokenizer_head_joint_v9.bf16.safetensors", 85644856),
        ("Mothersuperior/yue2-mothersuperior-realaudio-tokenizer-v4",
         "nar_lora_joint_v9.bf16.safetensors",
         "YuE2-Realaudio/nar_lora_joint_v9.bf16.safetensors", 70301896),
        ("Mothersuperior/yue2-mothersuperior-realaudio-tokenizer-v4", "assets/sem_nbr_idx.npy",
         "YuE2-Realaudio/assets/sem_nbr_idx.npy", 2097280),
        ("Mothersuperior/yue2-mothersuperior-realaudio-tokenizer-v4", "assets/sem_nbr_cos.npy",
         "YuE2-Realaudio/assets/sem_nbr_cos.npy", 2097280),
        ("pduncan/YuE2_Deathmetalv1_lora", "deathmetalv1_step-000600.safetensors",
         "loras/deathmetal-v1/lora.safetensors", 278968264),
        ("storagejuju/yue2-jpop-t4-lora", "yue2_jpop_t4.safetensors", "loras/jpop-t4/lora.safetensors", None),
        ("Mothersuperior/YuE2-instrumental-cot-full-loras", "ar_lora_inst_v3abc.safetensors",
         "loras/instrumental-v3abc/lora.safetensors", None),
    ],
    "mlx": [
        ("ahmadw/YuE2-3B-MLX", "8bit/model.safetensors", "YuE2-3B-MLX/8bit/model.safetensors", 4264488042),
        ("ahmadw/YuE2-3B-MLX", "8bit/vae.safetensors", "YuE2-3B-MLX/8bit/vae.safetensors", 265441814),
    ],
    "decoders": [
        ("m-a-p/YuE2-Vae-legacy", "model.safetensors", "YuE2-Vae-legacy/model.safetensors", 530512720),
        ("Mothersuperior/YuE2-Vae-merge-0.666", "model.safetensors",
         "YuE2-Vae-merge/model.safetensors", 530512792),
    ],
    "realaudio": [
        ("Mothersuperior/yue2-mothersuperior-realaudio-tokenizer-v4",
         "tokenizer_head_joint_v9.bf16.safetensors",
         "YuE2-Realaudio/tokenizer_head_joint_v9.bf16.safetensors", 85644856),
        ("Mothersuperior/yue2-mothersuperior-realaudio-tokenizer-v4",
         "nar_lora_joint_v9.bf16.safetensors",
         "YuE2-Realaudio/nar_lora_joint_v9.bf16.safetensors", 70301896),
        ("Mothersuperior/yue2-mothersuperior-realaudio-tokenizer-v4", "assets/sem_nbr_idx.npy",
         "YuE2-Realaudio/assets/sem_nbr_idx.npy", 2097280),
        ("Mothersuperior/yue2-mothersuperior-realaudio-tokenizer-v4", "assets/sem_nbr_cos.npy",
         "YuE2-Realaudio/assets/sem_nbr_cos.npy", 2097280),
    ],
    "lora-deathmetal": [
        ("pduncan/YuE2_Deathmetalv1_lora", "deathmetalv1_step-000600.safetensors",
         "loras/deathmetal-v1/lora.safetensors", 278968264),
    ],
    "lora-jpop": [
        ("storagejuju/yue2-jpop-t4-lora", "yue2_jpop_t4.safetensors",
         "loras/jpop-t4/lora.safetensors", 106474864),
    ],
    "lora-instrumental": [
        ("Mothersuperior/YuE2-instrumental-cot-full-loras", "ar_lora_inst_v3abc.safetensors",
         "loras/instrumental-v3abc/lora.safetensors", 278962592),
    ],
    "mlx-8bit": [
        ("ahmadw/YuE2-3B-MLX", "8bit/model.safetensors", "YuE2-3B-MLX/8bit/model.safetensors", 4264488042),
        ("ahmadw/YuE2-3B-MLX", "8bit/vae.safetensors", "YuE2-3B-MLX/8bit/vae.safetensors", 265441814),
    ],
    "mlx-bf16": [
        ("ahmadw/YuE2-3B-MLX", "bf16/model.safetensors", "YuE2-3B-MLX/bf16/model.safetensors", 7261441586),
        ("ahmadw/YuE2-3B-MLX", "bf16/vae.safetensors", "YuE2-3B-MLX/bf16/vae.safetensors", 265441814),
    ],
    "mlx-4bit": [
        ("ahmadw/YuE2-3B-MLX", "4bit/model.safetensors", "YuE2-3B-MLX/4bit/model.safetensors", 3370707798),
        ("ahmadw/YuE2-3B-MLX", "4bit/vae.safetensors", "YuE2-3B-MLX/4bit/vae.safetensors", 265441814),
    ],
}

MLX_CODE = ["generate.py", "convert.py", "test_parity.py", "yue2_model.py", "yue2_vae.py", "README.md"]
MLX_SMALL = [f"8bit/{name}" for name in
             ("config.json", "qwen.tiktoken", "vae_config.json", "yue2_generation_config.json")]

SMALL_FOR_MODE = {
    "core": [("m-a-p/YuE2-3B", "YuE2-3B"), ("m-a-p/YuE2-Vae", "YuE2-Vae")],
    "extras": [("m-a-p/YuE2-Vae-legacy", "YuE2-Vae-legacy"),
               ("Mothersuperior/YuE2-Vae-merge-0.666", "YuE2-Vae-merge"),
               ("Mothersuperior/yue2-mothersuperior-realaudio-tokenizer-v4", "YuE2-Realaudio")],
    "mlx": [],
    "transcribe": [],
    "decoders": [("m-a-p/YuE2-Vae-legacy", "YuE2-Vae-legacy"),
                 ("Mothersuperior/YuE2-Vae-merge-0.666", "YuE2-Vae-merge")],
    "realaudio": [],
    "lora-deathmetal": [],
    "lora-jpop": [],
    "lora-instrumental": [],
    "mlx-8bit": [],
    "mlx-bf16": [],
    "mlx-4bit": [],
}


CURL = shutil.which("curl")


def curl_download(url, out: Path, start=None, end=None, retries=4):
    """Fetch with curl (3-10x faster than urllib against these mirrors).

    Writes fresh to `out`; the caller owns completeness checks and retries.
    """
    if CURL is None:
        raise RuntimeError("curl is required for downloads "
                           "(macOS/Linux ship it; Windows 10+ includes curl.exe)")
    cmd = [CURL, "-sSL", "--fail", "--retry", str(retries), "--retry-delay", "2",
           "-o", str(out)]
    if start is not None:
        cmd += ["-r", f"{start}-{end}" if end is not None else str(start)]
    cmd.append(url)
    try:
        return subprocess.run(cmd, timeout=900).returncode == 0
    except subprocess.TimeoutExpired:
        return False


def url_for(repo, name):
    return f"{BASE}/{repo}/resolve/main/{name}"


def head_size(repo, name):
    request = urllib.request.Request(url_for(repo, name), method="HEAD")
    with urllib.request.urlopen(request, timeout=60) as response:
        return int(response.headers.get("Content-Length") or 0)


def download_small(repo, name, out: Path, retries=5):
    out.parent.mkdir(parents=True, exist_ok=True)
    remote = None
    try:
        remote = head_size(repo, name) or None
    except (urllib.error.URLError, TimeoutError, OSError):
        remote = None
    if remote is not None and out.exists() and out.stat().st_size == remote:
        print(f"  skip {out.relative_to(ROOT)} (complete)")
        return True
    for attempt in range(retries):
        try:
            if out.exists():
                out.unlink()
            if curl_download(url_for(repo, name), out, retries=2):
                if remote is None or (out.exists() and out.stat().st_size == remote):
                    return True
                last = f"size {out.stat().st_size} != {remote}"
            else:
                last = "curl failed"
        except RuntimeError as exc:
            last = str(exc)
        if attempt == retries - 1:
            print(f"  FAILED {repo}/{name}: {last}")
            return False
        time.sleep(2 + attempt * 2)
    return False


def download_big(repo, name, out: Path, size, retries=6):
    out.parent.mkdir(parents=True, exist_ok=True)
    if not size:
        try:
            size = head_size(repo, name) or 0
        except (urllib.error.URLError, TimeoutError):
            size = 0
    if size and out.exists() and out.stat().st_size == size:
        print(f"  skip {out.relative_to(ROOT)} (complete)")
        return True
    parts_dir = out.parent / (out.name + ".parts")
    parts_dir.mkdir(exist_ok=True)

    def fetch(start):
        part = parts_dir / f"{start:012d}"
        want = min(CHUNK, size - start) if size else None
        have = part.stat().st_size if part.exists() else 0
        if want is not None and have >= want:
            return
        for attempt in range(retries):
            if part.exists():
                part.unlink()  # curl writes the whole chunk in one go
            ok = curl_download(url_for(repo, name), part, start,
                               (start + want - 1) if want else None, retries=3)
            got = part.stat().st_size if part.exists() else 0
            if ok and (want is None or got == want):
                return
            if attempt == retries - 1:
                raise RuntimeError(f"{name} range {start}: chunk incomplete ({got}/{want})")
            time.sleep(2 + attempt * 2)

    starts = list(range(0, size, CHUNK)) if size else [0]
    with ThreadPoolExecutor(max_workers=min(WORKERS, max(1, len(starts)))) as pool:
        list(pool.map(fetch, starts))
    with out.open("wb") as target:
        for start in starts:
            with (parts_dir / f"{start:012d}").open("rb") as part:
                while True:
                    block = part.read(1 << 22)
                    if not block:
                        break
                    target.write(block)
    if size and out.stat().st_size != size:
        raise RuntimeError(f"{out} size mismatch ({out.stat().st_size} != {size})")
    for part in parts_dir.iterdir():
        part.unlink()
    parts_dir.rmdir()
    print(f"  done {out.relative_to(ROOT)} ({out.stat().st_size / 2**20:.0f} MiB)")
    return True


def verify(model_dir: Path, name: str, path: Path):
    manifest = model_dir / "weights_manifest.json"
    if not manifest.exists():
        return
    try:
        expected = json.loads(manifest.read_text(encoding="utf-8"))["files"][name]["sha256"]
    except (ValueError, KeyError):
        return
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 22), b""):
            digest.update(block)
    ok = digest.hexdigest() == expected
    print(f"  sha256 {'OK' if ok else 'MISMATCH'}: {path.relative_to(ROOT)}")
    if not ok:
        raise RuntimeError(f"{path} failed hash verification; delete it and retry")


def tree_files(repo):
    request = urllib.request.Request(f"{BASE}/api/models/{repo}/tree/main?recursive=1")
    with urllib.request.urlopen(request, timeout=60) as response:
        entries = json.loads(response.read().decode("utf-8"))
    return [(e["path"], e.get("size") or 0) for e in entries
            if e.get("type") == "file" and e["path"] != ".gitattributes"]


def snapshot(repo, folder, skip_prefixes=()):
    """Download a whole repo (used for the SheetSage2 / MERT transcription stack)."""
    target = DEST / folder
    files = [(path, size) for path, size in tree_files(repo)
             if not path.startswith(tuple(skip_prefixes))]
    print(f"== {repo} snapshot ({len(files)} files) ==")
    for path, size in files:
        out = target / path
        if out.exists() and out.stat().st_size >= size and size:
            continue
        if size >= CHUNK:
            download_big(repo, path, out, size)
        elif not download_small(repo, path, out):
            raise SystemExit(1)


def run(mode):
    if mode == "transcribe":
        snapshot("m-a-p/MERT-v2-FullSong", "MERT-v2-FullSong", skip_prefixes=("assets/",))
        snapshot("m-a-p/SheetSage2", "SheetSage2", skip_prefixes=("assets/", "benchmarks/"))
        print("DONE")
        return
    for repo, folder in SMALL_FOR_MODE[mode]:
        print(f"== {repo} (small files) ==")
        for name in SMALL_FILES[repo][1]:
            if not download_small(repo, name, DEST / folder / name):
                raise SystemExit(1)
    if mode.startswith("mlx"):
        variant = "8bit" if mode in ("mlx", "mlx-8bit") else mode.split("-", 1)[1]
        print(f"== ahmadw/YuE2-3B-MLX (config for {variant}) ==")
        names = list(MLX_CODE) if variant == "8bit" else []
        names += [f"{variant}/{n}" for n in
                  ("config.json", "qwen.tiktoken", "vae_config.json", "yue2_generation_config.json")]
        for name in names:
            if not download_small("ahmadw/YuE2-3B-MLX", name, DEST / "YuE2-3B-MLX" / name):
                raise SystemExit(1)
    for repo, name, rel, size in PLANS[mode]:
        print(f"== {repo}/{name} ==")
        out = DEST / rel
        download_big(repo, name, out, size)
        verify(DEST / Path(rel).parts[0], name, out)
    print("DONE")


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "core"
    if mode not in PLANS:
        print(__doc__)
        return 2
    run(mode)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
