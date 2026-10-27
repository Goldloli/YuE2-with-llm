#!/usr/bin/env python3
"""Start YuE2 Studio (used by start.command / start.bat).

Self-contained one-click packages ship a portable Python runtime and every
dependency (`runtime/` + `envs/web`, plus `envs/mlx` on macOS). In that layout
`--bundled` starts the web server directly: no bootstrap, no pip, no network.
A source checkout / slim package keeps the legacy path (prepare `.venv` via
`tools/bootstrap.py`, then start the server).

Model weights are never downloaded here — the app opens on the Models page,
where the user downloads the core model and picks a channel (domestic mirror /
direct Hugging Face).
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
DEFAULT_PORT = 9086
PORT = DEFAULT_PORT
URL = f"http://127.0.0.1:{PORT}"
BUNDLED_RUNTIME = ROOT / "runtime" / ("python.exe" if os.name == "nt" else "bin/python3")
BUNDLED_WEB_ENV = ROOT / "envs" / "web"


def _valid_port(raw):
    try:
        port = int(raw)
    except (TypeError, ValueError):
        return None
    return port if 1 <= port <= 65535 else None


def resolve_port(argv=None):
    """Resolve the local port: ``--port`` > ``YUE2_PORT`` > :data:`DEFAULT_PORT`."""
    argv = list(sys.argv[1:] if argv is None else argv)
    cli = None
    for index, value in enumerate(argv):
        if value == "--port" and index + 1 < len(argv):
            cli = argv[index + 1]
        elif value.startswith("--port="):
            cli = value.split("=", 1)[1]
    for source, raw in (("--port", cli), ("YUE2_PORT", os.environ.get("YUE2_PORT"))):
        if raw in (None, ""):
            continue
        port = _valid_port(raw)
        if port is None:
            print(f"[warn] invalid {source}={raw!r}; using default port {DEFAULT_PORT}",
                  file=sys.stderr)
            return DEFAULT_PORT
        return port
    return DEFAULT_PORT


def set_port(port):
    """Use *port* for probing, the printed URL, the browser and the server child."""
    global PORT, URL
    PORT = port
    URL = f"http://127.0.0.1:{port}"
    return port


def venv_python():
    exe = "Scripts/python.exe" if os.name == "nt" else "bin/python"
    return VENV / exe


def bundled_ready():
    """Portable runtime + preinstalled dependencies are present."""
    return BUNDLED_RUNTIME.exists() and BUNDLED_WEB_ENV.is_dir()


def env_ready():
    """The developer venv exists and dependency installation finished."""
    return venv_python().exists() and (VENV / ".deps-installed").exists()


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


def setup_environment():
    """Create the venv, install dependencies (dev/slim packages only)."""
    print("First run: setting up the environment (this may take a while)…")
    return subprocess.call([sys.executable, str(ROOT / "tools" / "bootstrap.py"),
                            "--yes", "--skip-models"])


def server_env():
    env = dict(os.environ)
    if bundled_ready():
        paths = [str(BUNDLED_WEB_ENV), str(ROOT / "src")]
        if env.get("PYTHONPATH"):
            paths.append(env["PYTHONPATH"])
        env["PYTHONPATH"] = os.pathsep.join(paths)
    return env


def wait_and_open(timeout=90):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", PORT), timeout=1):
                webbrowser.open(URL)
                return
        except OSError:
            time.sleep(0.5)


def server_process_env(base=None):
    """Child-process env carrying the resolved port for ``web/server.py``."""
    env = dict(os.environ if base is None else base)
    env["YUE2_PORT"] = str(PORT)
    return env


def run_server(python, env=None):
    proc = subprocess.Popen([str(python), str(ROOT / "web" / "server.py")],
                            cwd=str(ROOT), env=server_process_env(env))
    try:
        return proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        return 0


def hint_missing_models():
    if models_ready():
        return
    print("No models yet: after launch, open the “Models” page and download the core model")
    print("(the download channel is switchable there: domestic mirror / direct Hugging Face).")


def start_bundled():
    print("YuE2 Studio (self-contained)  →  %s   (Ctrl+C to stop)" % URL)
    hint_missing_models()
    threading.Thread(target=wait_and_open, daemon=True).start()
    return run_server(BUNDLED_RUNTIME, env=server_env())


def start_from_source():
    if not env_ready():
        code = setup_environment()
        if code != 0:
            return code
    py = venv_python()
    if not py.exists():
        print("Setup did not finish; run:  python tools/bootstrap.py")
        return 1
    hint_missing_models()
    print("YuE2 Studio  →  %s   (Ctrl+C to stop)" % URL)
    threading.Thread(target=wait_and_open, daemon=True).start()
    return run_server(py)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    set_port(resolve_port(argv))
    flags = {value for value in argv if value in ("--bundled", "--legacy")}
    if "--bundled" in flags or (bundled_ready() and "--legacy" not in flags):
        if bundled_ready():
            return start_bundled()
        print("Bundled runtime is missing; falling back to the development setup.")
    return start_from_source()


if __name__ == "__main__":
    sys.exit(main())
