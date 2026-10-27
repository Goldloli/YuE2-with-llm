#!/usr/bin/env python3
"""Build a model-embedded one-click bundle (CI or local), split into release parts.

Unlike build_package.py --with-models (which requires the models to be present
locally beforehand), this script downloads each model component on the fly via
tools/hf_download.py, appends it to the zip STORED, and deletes the raw files
right away — peak disk stays near (zip size + largest single component).

    python packaging/build_model_bundle.py --platform macos --tier mini
    python packaging/build_model_bundle.py --platform win-x64 --tier full \
        --use-local-models          # skip downloads, pack from models/

Tiers (single source of truth: TIERS below, imported by smoke_package.py):
    macos:   mini (MLX 4bit + Vae) | standard (MLX 8bit + Vae) | full (everything)
    win-x64: standard (torch core) | full (all torch models)

On CI set YUE2_HF_ENDPOINT=https://huggingface.co for direct HF access.
Output: oneclick-packages/<platform>/<name>.zip split into <=1.9 GiB
<name>.zip.part-aa/.part-ab/... parts plus a single <name>.zip.sha256 manifest
(last line holds the merged zip's own sha256).
"""
from __future__ import annotations

import argparse
import datetime
import fnmatch
import hashlib
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

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

import build_package as bp  # noqa: E402  (stage/scan/self-check reuse)

PACKAGE_NAME = bp.PACKAGE_NAME
MODELS = ROOT / "models"

# GitHub Release caps assets at 2 GiB; stay clearly below it.
PART_SIZE = 1_900_000_000

# hf_download mode -> model subtrees it populates (relative to models/).
MODE_PATHS = {
    "vae": ["YuE2-Vae"],
    "core": ["YuE2-3B", "YuE2-Vae"],
    "extras": ["YuE2-Vae-legacy", "YuE2-Vae-merge", "YuE2-Realaudio", "loras"],
    "transcribe": ["MERT-v2-FullSong", "SheetSage2"],
    "mlx-4bit": ["YuE2-3B-MLX/4bit"],
    "mlx-8bit": ["YuE2-3B-MLX/8bit"],
    "mlx-bf16": ["YuE2-3B-MLX/bf16"],
}
MLX_DIR = "YuE2-3B-MLX"

_VAE = "YuE2-Vae/model.safetensors"
_VAE_SIZE = 530512720
_MLX_CODE = {f"{MLX_DIR}/{n}": None for n in
             ("generate.py", "convert.py", "test_parity.py", "yue2_model.py",
              "yue2_vae.py", "README.md")}
_EXTRAS_REQUIRED = {
    "YuE2-Vae-legacy/model.safetensors": 530512720,
    "YuE2-Vae-merge/model.safetensors": 530512792,
    "YuE2-Realaudio/nar_lora_joint_v9.bf16.safetensors": 70301896,
    "loras/deathmetal-v1/lora.safetensors": 278968264,
    "loras/jpop-t4/lora.safetensors": 106474864,
    "loras/instrumental-v3abc/lora.safetensors": 278962592,
}
_TRANSCRIBE_REQUIRED = {
    "MERT-v2-FullSong/config.json": None,
    "SheetSage2/config.json": None,
}
_CORE_REQUIRED = {"YuE2-3B/model.safetensors": 7261441640, _VAE: _VAE_SIZE}
_MLX_REQUIRED = {
    "4bit": {f"{MLX_DIR}/4bit/model.safetensors": 3370707798,
             f"{MLX_DIR}/4bit/vae.safetensors": 265441814},
    "8bit": {f"{MLX_DIR}/8bit/model.safetensors": 4264488042,
             f"{MLX_DIR}/8bit/vae.safetensors": 265441814},
    "bf16": {f"{MLX_DIR}/bf16/model.safetensors": 7261441586,
             f"{MLX_DIR}/bf16/vae.safetensors": 265441814},
}
_NON_CORE_FORBIDDEN = ["YuE2-Vae-legacy/", "YuE2-Vae-merge/", "YuE2-Realaudio/",
                       "loras/", "MERT-v2-FullSong/", "SheetSage2/"]

TIERS = {
    ("macos", "mini"): {
        "modes": ["vae", "mlx-4bit"],
        "required": {**_MLX_REQUIRED["4bit"], **_MLX_CODE, _VAE: _VAE_SIZE},
        "forbidden": ["YuE2-3B/", f"{MLX_DIR}/8bit/", f"{MLX_DIR}/bf16/",
                      *_NON_CORE_FORBIDDEN],
        "est_gb": 4.6, "max_component_gb": 3.5,
    },
    ("macos", "standard"): {
        "modes": ["vae", "mlx-8bit"],
        "required": {**_MLX_REQUIRED["8bit"], **_MLX_CODE, _VAE: _VAE_SIZE},
        "forbidden": ["YuE2-3B/", f"{MLX_DIR}/4bit/", f"{MLX_DIR}/bf16/",
                      *_NON_CORE_FORBIDDEN],
        "est_gb": 5.4, "max_component_gb": 4.3,
    },
    ("macos", "full"): {
        "modes": ["core", "extras", "transcribe", "mlx-4bit", "mlx-8bit", "mlx-bf16"],
        "required": {**_CORE_REQUIRED, **_EXTRAS_REQUIRED, **_TRANSCRIBE_REQUIRED,
                     **_MLX_CODE, **_MLX_REQUIRED["4bit"], **_MLX_REQUIRED["8bit"],
                     **_MLX_REQUIRED["bf16"]},
        "forbidden": [],
        "est_gb": 26.6, "max_component_gb": 7.3,
    },
    ("win-x64", "standard"): {
        "modes": ["core"],
        "required": dict(_CORE_REQUIRED),
        "forbidden": [f"{MLX_DIR}/", *_NON_CORE_FORBIDDEN],
        "est_gb": 7.4, "max_component_gb": 7.3,
    },
    ("win-x64", "full"): {
        "modes": ["core", "extras", "transcribe"],
        "required": {**_CORE_REQUIRED, **_EXTRAS_REQUIRED, **_TRANSCRIBE_REQUIRED},
        "forbidden": [f"{MLX_DIR}/"],
        "est_gb": 12.4, "max_component_gb": 7.3,
    },
}

MARGIN = 2 << 30  # headroom for staging, filesystem overhead, logs


def disk_need(spec: dict, local: bool = False) -> int:
    """Extra free bytes needed at the tightest moment of the build.

    Two phases share the volume:
      - streaming build: the partial zip plus the one component still on disk
        (it is removed right after being appended);
      - splitting: the finished zip plus every part being written — parts are
        byte-for-byte copies of the zip, so this phase costs 2x the zip.

    A local build (``--use-local-models``) downloads nothing, so only the
    split phase applies. ``MARGIN`` covers staging + overhead.
    """
    est = int(spec["est_gb"] * 2 ** 30)
    component = 0 if local else int(spec["max_component_gb"] * 2 ** 30)
    return max(est + component, 2 * est) + MARGIN


def disk_precheck(spec: dict, local: bool):
    need = disk_need(spec, local)
    free = shutil.disk_usage(ROOT).free
    gib = 2 ** 30
    # GitHub-hosted standard runners ship only 14 GB of SSD, hence the hint.
    print(f"disk: need ~{need / gib:.1f} GiB (zip {spec['est_gb']} GiB + split), "
          f"free {free / gib:.1f} GiB")
    if free < need:
        raise SystemExit(
            f"磁盘不足：需要约 {need / gib:.1f} GiB（切分阶段 zip + 全部分卷），"
            f"可用 {free / gib:.1f} GiB。"
            "CI 上请先按需清理 runner 磁盘（workflow 的「按需释放磁盘」步骤），"
            "或改用本地 --use-local-models 构建。")


def fetch(mode: str):
    print(f"== download: {mode} ==", flush=True)
    subprocess.run([sys.executable, str(ROOT / "tools" / "hf_download.py"), mode],
                   check=True, cwd=ROOT)


def check_local(spec: dict):
    missing = [rel for rel in spec["required"] if not (MODELS / rel).exists()]
    if missing:
        raise SystemExit("--use-local-models 但模型文件缺失："
                         + ", ".join(f"models/{m}" for m in missing[:8]))


def add_tree(zf: zipfile.ZipFile, rel: str, seen: set, top_files_only=False) -> int:
    base = MODELS / rel
    if not base.exists():
        raise SystemExit(f"models/{rel} missing after download")
    paths = ([p for p in sorted(base.iterdir()) if p.is_file()] if top_files_only
             else [p for p in sorted(base.rglob("*")) if p.is_file()])
    count = 0
    for path in paths:
        if any(fnmatch.fnmatch(path.name, pat) for pat in bp.MODEL_EXCLUDE):
            continue
        arcname = (Path(PACKAGE_NAME) / "models" / rel /
                   (path.name if top_files_only else path.relative_to(base))).as_posix()
        if arcname in seen:
            continue
        seen.add(arcname)
        zf.write(path, arcname,
                 compress_type=zipfile.ZIP_STORED
                 if path.suffix.lower() in bp.STORE_SUFFIXES else zipfile.ZIP_DEFLATED)
        count += 1
    return count


def remove(rel: str):
    path = MODELS / rel
    if path.is_dir():
        shutil.rmtree(path, ignore_errors=True)
    elif path.exists():
        path.unlink()


def split_zip(zip_path: Path, out_dir: Path, part_size: int = PART_SIZE):
    """Split into <name>.part-aa/.part-ab/... plus one sha256 manifest.

    Returns (parts, manifest_path, zip_sha256). The manifest lists every part
    and, as its last line, the merged zip itself. When the zip fits in a
    single part no split happens: manifest covers just the zip.
    """
    if zip_path.stat().st_size <= part_size:
        digest = hashlib.sha256(zip_path.read_bytes()).hexdigest()
        manifest = out_dir / (zip_path.name + ".sha256")
        manifest.write_text(f"{digest}  {zip_path.name}\n", encoding="utf-8")
        return [], manifest, digest
    parts = []
    zip_hasher = hashlib.sha256()
    idx = 0
    with zip_path.open("rb") as src:
        while True:
            name = f"{zip_path.name}.part-{chr(97 + idx // 26)}{chr(97 + idx % 26)}"
            part_path = out_dir / name
            hasher = hashlib.sha256()
            written = 0
            with part_path.open("wb") as dst:
                while written < part_size:
                    chunk = src.read(min(8 << 20, part_size - written))
                    if not chunk:
                        break
                    dst.write(chunk)
                    hasher.update(chunk)
                    zip_hasher.update(chunk)
                    written += len(chunk)
            if written == 0:
                part_path.unlink()
                break
            parts.append((name, written, hasher.hexdigest()))
            print(f"  part {name} ({written / 2 ** 30:.2f} GiB)", flush=True)
            idx += 1
            if written < part_size:
                break
    manifest = out_dir / (zip_path.name + ".sha256")
    lines = [f"{h}  {n}" for n, _, h in parts]
    lines.append(f"{zip_hasher.hexdigest()}  {zip_path.name}")
    manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return parts, manifest, zip_hasher.hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--platform", choices=sorted(bp.PLATFORMS), required=True)
    ap.add_argument("--tier", choices=sorted({t for _, t in TIERS}), required=True)
    ap.add_argument("--use-local-models", action="store_true",
                    help="Pack from models/ without downloading (local verification); "
                         "never deletes model files")
    ap.add_argument("--keep-zip", action="store_true",
                    help="Keep the monolithic zip after splitting (default: delete)")
    ap.add_argument("--keep-stage", action="store_true")
    ap.add_argument("--out-dir", type=Path, default=None)
    args = ap.parse_args()

    key = (args.platform, args.tier)
    if key not in TIERS:
        valid = ", ".join(f"{p}/{t}" for p, t in sorted(TIERS))
        raise SystemExit(f"无此档位组合：{args.platform}/{args.tier}（可选：{valid}）")
    spec = TIERS[key]
    local = args.use_local_models

    if local:
        check_local(spec)
    disk_precheck(spec, local)
    bp.check_style_terms()

    out_dir = args.out_dir or ROOT / "oneclick-packages" / args.platform
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.date.today().strftime("%Y%m%d")
    label = bp.PLATFORMS[args.platform]["label"]
    zip_path = out_dir / f"{PACKAGE_NAME}-{label}-{args.tier}-{stamp}.zip"

    stage_root = Path(tempfile.mkdtemp(prefix="yue2-bundle-"))
    mode_desc = "local models" if local else "CI download"
    print(f"build: {args.platform}/{args.tier} ({mode_desc}) | staging: {stage_root}")
    seen: set = set()
    try:
        pkg = bp.stage_source(stage_root)
        bp.scan_forbidden(pkg)
        bp.self_check(pkg, args.platform)
        if zip_path.exists():
            zip_path.unlink()
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED,
                             allowZip64=True) as zf:
            for path in sorted(pkg.rglob("*")):
                if path.is_file():
                    arcname = path.relative_to(pkg.parent).as_posix()
                    seen.add(arcname)
                    zf.write(path, arcname)
            mlx_code_done = False
            for mode in spec["modes"]:
                if not local:
                    fetch(mode)
                owned = list(MODE_PATHS[mode])
                if mode.startswith("mlx") and not mlx_code_done:
                    owned.append(MLX_DIR)  # top-level code files only
                    mlx_code_done = True
                for rel in owned:
                    n = add_tree(zf, rel, seen, top_files_only=(rel == MLX_DIR))
                    print(f"  + models/{rel} ({n} files)", flush=True)
                    if not local:
                        if rel == MLX_DIR:
                            for f in (MODELS / rel).iterdir():
                                if f.is_file():
                                    f.unlink()
                        else:
                            remove(rel)
            if not local and (MODELS / MLX_DIR).exists():
                try:
                    (MODELS / MLX_DIR).rmdir()  # only when fully consumed
                except OSError:
                    pass
            missing = [rel for rel in spec["required"]
                       if f"{PACKAGE_NAME}/models/{rel}" not in seen]
            if missing:
                raise SystemExit(f"档位必需条目未进入 zip：{missing[:8]}")
            zf.writestr(f"{PACKAGE_NAME}/models/.bundle",
                        f"{args.platform}/{args.tier} {stamp}\n")
        size_gb = zip_path.stat().st_size / 2 ** 30
        print(f"zipped: {zip_path} ({size_gb:.2f} GiB, {len(seen)} files)")

        parts, manifest, zip_sha = split_zip(zip_path, out_dir)
        print(f"manifest: {manifest} (zip sha256={zip_sha})")
        if parts and not args.keep_zip:
            zip_path.unlink()
            print(f"removed monolithic zip; {len(parts)} parts ready for upload")
        elif parts:
            print(f"kept zip + {len(parts)} parts (--keep-zip)")
        return 0
    finally:
        if args.keep_stage:
            print(f"stage kept at {stage_root}")
        else:
            shutil.rmtree(stage_root, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
