#!/usr/bin/env python3
"""Smoke-check a built one-click package, then write a .sha256 sidecar.

    python packaging/smoke_package.py dist/yue2-studio-oneclick-20261012-macos.zip

Checks required entries, the slim red lines (no models / no user data) and
prints the SHA-256 used for distribution.
"""
from __future__ import annotations

import hashlib
import sys
import zipfile
from pathlib import Path

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


def main(paths: list[str]) -> int:
    if not paths:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    for arg in paths:
        path = Path(arg)
        with zipfile.ZipFile(path) as zf:
            names = zf.namelist()
        name_set = set(names)
        missing = [entry for entry in REQUIRED if entry not in name_set]
        if missing:
            raise SystemExit(f"{path.name}: missing entries: {missing}")
        forbidden = [n for n in names
                     if any(n == p.rstrip("/") or n.startswith(p) for p in FORBIDDEN_PREFIXES)]
        if forbidden:
            raise SystemExit(f"{path.name}: forbidden entries: {forbidden[:5]}")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        sidecar = path.with_name(path.name + ".sha256")
        sidecar.write_text(f"{digest}  {path.name}\n", encoding="utf-8")
        print(f"{path.name}: OK ({len(names)} entries) sha256={digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
