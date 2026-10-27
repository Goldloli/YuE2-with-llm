#!/usr/bin/env python3
"""Smoke-check built one-click packages, then write/verify sha256 sidecars.

Slim package (existing behavior):
    python packaging/smoke_package.py dist/yue2-studio-oneclick-20261012-macos.zip

Model bundle entry checks (zip listing only, no extraction):
    python packaging/smoke_package.py --bundle win-x64 standard dist/<name>.zip

Split-part verification (sizes, naming, per-part and merged sha256):
    python packaging/smoke_package.py --parts dist/<name>.zip.sha256
"""
from __future__ import annotations

import argparse
import hashlib
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

ROOT_NAME = "yue2-studio-oneclick"
REQUIRED = [
    f"{ROOT_NAME}/start.command",
    f"{ROOT_NAME}/start.bat",
    f"{ROOT_NAME}/使用说明.md",
    f"{ROOT_NAME}/tools/start.py",
    f"{ROOT_NAME}/tools/bootstrap.py",
    f"{ROOT_NAME}/tools/hf_download.py",
    f"{ROOT_NAME}/web/server.py",
    f"{ROOT_NAME}/web/static/index.html",
    f"{ROOT_NAME}/docs/style-terms.md",
    f"{ROOT_NAME}/pyproject.toml",
]
FORBIDDEN_PREFIXES = [
    f"{ROOT_NAME}/models/",
    f"{ROOT_NAME}/web/data/",
    f"{ROOT_NAME}/outputs/",
    f"{ROOT_NAME}/.git/",
    f"{ROOT_NAME}/.venv",
]
# Red lines that also apply inside model bundles (models/ itself allowed there).
BUNDLE_FORBIDDEN_PREFIXES = [p for p in FORBIDDEN_PREFIXES if not p.startswith(f"{ROOT_NAME}/models/")]


def sha256_stream(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 22), b""):
            hasher.update(block)
    return hasher.hexdigest()


def check_slim(path: Path):
    with zipfile.ZipFile(path) as zf:
        name_set = set(zf.namelist())
    missing = [entry for entry in REQUIRED if entry not in name_set]
    if missing:
        raise SystemExit(f"{path.name}: missing entries: {missing}")
    forbidden = [n for n in name_set
                 if any(n == p.rstrip("/") or n.startswith(p) for p in FORBIDDEN_PREFIXES)]
    if forbidden:
        raise SystemExit(f"{path.name}: forbidden entries: {forbidden[:5]}")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    sidecar = path.with_name(path.name + ".sha256")
    sidecar.write_text(f"{digest}  {path.name}\n", encoding="utf-8")
    print(f"{path.name}: OK ({len(name_set)} entries) sha256={digest}")


def check_bundle(zip_path: Path, platform: str, tier: str):
    import build_model_bundle as bb

    key = (platform, tier)
    if key not in bb.TIERS:
        raise SystemExit(f"unknown tier: {platform}/{tier}")
    spec = bb.TIERS[key]
    models_prefix = f"{ROOT_NAME}/models/"
    forbidden = BUNDLE_FORBIDDEN_PREFIXES + [models_prefix + p for p in spec["forbidden"]]

    with zipfile.ZipFile(zip_path) as zf:
        infos = {i.filename: i for i in zf.infolist()}

    missing = [e for e in REQUIRED if e not in infos]
    absent = [models_prefix + rel for rel in spec["required"] if models_prefix + rel not in infos]
    if missing or absent:
        raise SystemExit(f"{zip_path.name}: missing entries: {missing + absent}")

    bad_size, bad_compress = [], []
    for rel, size in spec["required"].items():
        info = infos[models_prefix + rel]
        if size is not None and info.file_size != size:
            bad_size.append(f"{rel} ({info.file_size} != {size})")
        if info.filename.lower().endswith(tuple(bb.bp.STORE_SUFFIXES)) \
                and info.compress_type != zipfile.ZIP_STORED:
            bad_compress.append(rel)
    if bad_size or bad_compress:
        raise SystemExit(f"{zip_path.name}: size mismatches {bad_size[:4]} "
                         f"non-STORED weights {bad_compress[:4]}")

    hits = [n for n in infos
            if any(n == p.rstrip("/") or n.startswith(p) for p in forbidden)]
    if hits:
        raise SystemExit(f"{zip_path.name}: forbidden entries: {hits[:5]}")
    print(f"{zip_path.name}: bundle {platform}/{tier} OK "
          f"({len(infos)} entries, {len(spec['required'])} required model files verified)")


def check_parts(manifest_path: Path):
    import build_model_bundle as bb

    entries = []
    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            entries.append(line.split("  ", 1))
    if not entries:
        raise SystemExit(f"{manifest_path}: empty manifest")

    zip_hash, zip_name = entries[-1]
    part_entries = entries[:-1]
    if not part_entries:
        print(f"{manifest_path.name}: no parts (zip small enough); verifying zip only")
        zip_path = manifest_path.parent / zip_name
        if sha256_stream(zip_path) != zip_hash:
            raise SystemExit(f"{zip_name}: sha256 mismatch")
        print(f"{zip_name}: OK sha256={zip_hash}")
        return

    # naming: <zip>.part-aa/.part-ab/... consecutive from aa
    merged = hashlib.sha256()
    for idx, (digest, name) in enumerate(part_entries):
        want = f"{zip_name}.part-{chr(97 + idx // 26)}{chr(97 + idx % 26)}"
        if name != want:
            raise SystemExit(f"part naming gap: expected {want}, manifest has {name}")
        part = manifest_path.parent / name
        if not part.exists():
            raise SystemExit(f"missing part: {name}")
        size = part.stat().st_size
        if size > bb.PART_SIZE:
            raise SystemExit(f"{name}: {size} bytes exceeds part limit {bb.PART_SIZE}")
        got = sha256_stream(part)
        if got != digest:
            raise SystemExit(f"{name}: sha256 mismatch ({got} != {digest})")
        with part.open("rb") as handle:
            for block in iter(lambda: handle.read(1 << 22), b""):
                merged.update(block)
        print(f"  {name}: OK ({size / 2 ** 30:.2f} GiB)")
    if merged.hexdigest() != zip_hash:
        raise SystemExit("merged parts sha256 does not match the zip line")
    print(f"{manifest_path.name}: {len(part_entries)} parts OK, "
          f"merged sha256={zip_hash}")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*", help="slim zips, or the bundle zip / manifest")
    ap.add_argument("--bundle", nargs=2, metavar=("PLATFORM", "TIER"),
                    help="entry-level bundle checks for the zip in paths")
    ap.add_argument("--parts", action="store_true",
                    help="verify split parts listed in the manifest given in paths")
    args = ap.parse_args(argv)
    if not args.paths:
        ap.print_help()
        return 2
    if args.bundle and args.parts:
        raise SystemExit("--bundle and --parts are mutually exclusive")

    platform, tier = args.bundle if args.bundle else (None, None)
    for arg in args.paths:
        path = Path(arg)
        if args.parts:
            check_parts(path)
        elif args.bundle:
            check_bundle(path, platform, tier)
        else:
            check_slim(path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
