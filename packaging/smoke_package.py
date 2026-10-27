#!/usr/bin/env python3
"""Smoke-check a built platform one-click package, then write its .sha256 sidecar.

    python packaging/smoke_package.py oneclick-packages/macos/yue2-studio-oneclick-20261012-macos.zip
    python packaging/smoke_package.py --platform macos path/to/package.zip

The platform is inferred from the file name (`*-macos.zip` / `*-win-x64.zip`);
`--platform` overrides it. Checks required entries, that the platform's own
launcher is present and the other platform's launcher is absent, that the macOS
launcher keeps its executable bit, and the slim red lines (no models / user data).
"""
from __future__ import annotations

import argparse
import hashlib
import sys
import zipfile
from pathlib import Path

ROOT_NAME = "yue2-studio-oneclick"
LAUNCHERS = {"macos": "start.command", "win-x64": "start.bat"}
OTHER_LAUNCHERS = {"macos": "start.bat", "win-x64": "start.command"}
PLATFORMS = sorted(LAUNCHERS)
REQUIRED = [
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
EXEC_BITS = 0o111


def platform_from_name(name: str) -> str | None:
    for platform in PLATFORMS:
        if name.endswith(f"-{platform}.zip"):
            return platform
    return None


def check(path: Path, platform: str | None = None):
    platform = platform or platform_from_name(path.name)
    if platform is None:
        raise SystemExit(f"{path.name}: cannot infer platform "
                         f"(expected *-macos.zip / *-win-x64.zip); pass --platform")
    launcher = f"{ROOT_NAME}/{LAUNCHERS[platform]}"
    stray = f"{ROOT_NAME}/{OTHER_LAUNCHERS[platform]}"
    with zipfile.ZipFile(path) as zf:
        infos = {info.filename: info for info in zf.infolist()}
    names = set(infos)
    missing = [entry for entry in REQUIRED if entry not in names]
    if launcher not in names:
        missing.append(launcher)
    if missing:
        raise SystemExit(f"{path.name}: missing entries: {missing}")
    if stray in names:
        raise SystemExit(f"{path.name}: forbidden launcher {stray} "
                         f"(this is a {platform} package)")
    if platform == "macos":
        mode = infos[launcher].external_attr >> 16
        if not mode & EXEC_BITS:
            raise SystemExit(f"{path.name}: {LAUNCHERS[platform]} lost its executable bit "
                             f"(mode {oct(mode)})")
    forbidden = [n for n in names
                 if any(n == p.rstrip("/") or n.startswith(p) for p in FORBIDDEN_PREFIXES)]
    if forbidden:
        raise SystemExit(f"{path.name}: forbidden entries: {forbidden[:5]}")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    sidecar = path.with_name(path.name + ".sha256")
    sidecar.write_text(f"{digest}  {path.name}\n", encoding="utf-8")
    print(f"{path.name}: OK ({platform}, {len(names)} entries) sha256={digest}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*", help="built one-click zips")
    ap.add_argument("--platform", choices=PLATFORMS, default=None,
                    help="override the platform inferred from the file name")
    args = ap.parse_args(argv)
    if not args.paths:
        ap.print_help()
        return 2
    for arg in args.paths:
        check(Path(arg), args.platform)
    return 0


if __name__ == "__main__":
    sys.exit(main())
