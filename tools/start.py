#!/usr/bin/env python3
"""Start YuE2 Studio (used by start.command / start.bat).

If the environment or models are missing, runs tools/bootstrap.py first.
Then starts the web server and opens the browser. Works on any Python 3.6+
so old interpreters can still print a useful message.
"""
import os
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENV = ROOT / ".venv"
URL = "http://127.0.0.1:7860"


def venv_python():
    exe = "Scripts/python.exe" if os.name == "nt" else "bin/python"
    return VENV / exe


def models_ready():
    """A usable engine exists: torch core, or any MLX variant (Apple Silicon)."""
    model = ROOT / "models" / "YuE2-3B" / "model.safetensors"
    vae = ROOT / "models" / "YuE2-Vae" / "model.safetensors"
    mlx_dir = ROOT / "models" / "YuE2-3B-MLX"
    try:
        if model.exists() and model.stat().st_size > 7_000_000_000 and vae.exists():
            return True
        return mlx_dir.exists() and any(mlx_dir.glob("*/model.safetensors"))
    except OSError:
        return False


def wait_and_open(timeout=90):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", 7860), timeout=1):
                webbrowser.open(URL)
                return
        except OSError:
            time.sleep(0.5)


def main():
    py = venv_python()
    if not py.exists() or not models_ready():
        print("First run: setting up the environment and models (this may take a while)…")
        code = subprocess.call([sys.executable, str(ROOT / "tools" / "bootstrap.py"), "--yes"])
        if code != 0:
            return code
    py = venv_python()
    if not py.exists():
        print("Setup did not finish; run:  python tools/bootstrap.py")
        return 1
    print("YuE2 Studio  →  %s   (Ctrl+C to stop)" % URL)
    threading.Thread(target=wait_and_open, daemon=True).start()
    proc = subprocess.Popen([str(py), str(ROOT / "web" / "server.py")], cwd=str(ROOT))
    try:
        return proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        return 0


if __name__ == "__main__":
    sys.exit(main())
