#!/usr/bin/env python3
"""True smoke test for a self-contained one-click package.

Unpacks the built zip into a temporary directory, verifies the bundled runtime
can import the app's dependencies *without any network*, then boots the web
server with the bundled interpreter and polls `/api/state` until it answers.

    python packaging/smoke_bundle.py oneclick-packages/macos/yue2-studio-oneclick-20261012-macos.zip

This is what proves "double-click and the page opens": no system Python, no pip,
no external packages. It runs on macOS and Windows CI (run it with the CI
runner's own Python; the package's runtime is what gets exercised).
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path

PACKAGE_ROOT = "yue2-studio-oneclick"
LAUNCHERS = {"macos": "start.command", "win-x64": "start.bat"}
RUNTIME_PYTHONS = {"macos": "runtime/bin/python3", "win-x64": "runtime/python.exe"}
PORT_TIMEOUT_SECONDS = 120
IMPORT_CHECK = ("import torch, transformers, fastapi, uvicorn, soundfile, numpy; "
                "import yue2; print(torch.__version__)")


def platform_from_name(name: str) -> str | None:
    for platform in LAUNCHERS:
        if name.endswith(f"-{platform}.zip"):
            return platform
    return None


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def payload_env(root: Path, platform: str) -> dict:
    env = dict(os.environ)
    paths = [str(root / "envs" / "web"), str(root / "src")]
    if env.get("PYTHONPATH"):
        paths.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(paths)
    env["PYTHONNOUSERSITE"] = "1"
    env["PYTHONUTF8"] = "1"
    return env


def wait_for_state(port: int, timeout: float = PORT_TIMEOUT_SECONDS) -> dict:
    deadline = time.time() + timeout
    url = f"http://127.0.0.1:{port}/api/state"
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                return json.loads(response.read().decode("utf-8"))
        except (OSError, ValueError):
            time.sleep(0.5)
    raise SystemExit(f"server did not answer {url} within {timeout:.0f}s")


def run(zip_path: Path, platform: str | None = None):
    platform = platform or platform_from_name(zip_path.name)
    if platform is None:
        raise SystemExit(f"{zip_path.name}: cannot infer platform from the file name")
    with tempfile.TemporaryDirectory(prefix="yue2-bundle-smoke-") as work:
        with zipfile.ZipFile(zip_path) as archive:
            archive.extractall(work)
            # Python's extractall drops Unix permission bits; restore them so the
            # bundled interpreter is executable (Finder/unzip keep them already).
            for info in archive.infolist():
                mode = (info.external_attr >> 16) & 0o777
                target = Path(work) / info.filename
                if mode and target.is_file():
                    target.chmod(mode)
        root = Path(work) / PACKAGE_ROOT
        interpreter = root / RUNTIME_PYTHONS[platform]
        if not interpreter.is_file():
            raise SystemExit(f"{zip_path.name}: bundled interpreter missing ({interpreter})")
        env = payload_env(root, platform)
        print(f"  bundled python: {interpreter}")
        check = subprocess.run([str(interpreter), "-c", IMPORT_CHECK],
                               cwd=str(root), env=env, capture_output=True, text=True)
        if check.returncode != 0:
            detail = (check.stderr or check.stdout).strip()[-2000:]
            raise SystemExit(f"{zip_path.name}: bundled imports failed: {detail}")
        print(f"  imports ok (torch {check.stdout.strip()})")
        port = free_port()
        server = subprocess.Popen(
            [str(interpreter), "-m", "uvicorn", "web.server:app",
             "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning"],
            cwd=str(root), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace")
        try:
            state = wait_for_state(port)
            if "core_installed" not in state:
                raise SystemExit(f"{zip_path.name}: /api/state missing core_installed")
            print(f"  server ok (port {port}, core_installed={state['core_installed']})")
        finally:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
    print(f"{zip_path.name}: bundle smoke OK")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*", help="self-contained one-click zips")
    ap.add_argument("--platform", choices=sorted(LAUNCHERS), default=None,
                    help="override the platform inferred from the file name")
    args = ap.parse_args(argv)
    if not args.paths:
        ap.print_help()
        return 2
    for arg in args.paths:
        run(Path(arg), args.platform)
    return 0


if __name__ == "__main__":
    sys.exit(main())
