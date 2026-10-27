#!/bin/bash
# YuE2 Studio launcher (macOS). Double-click this file to start.
#
# The self-contained package ships its own Python runtime and dependencies, so
# no install step and no network access are needed (models are downloaded later
# from the in-app Models page).
cd "$(dirname "$0")" || exit 1

if [ -x "runtime/bin/python3" ] && [ -d "envs/web" ]; then
  exec "runtime/bin/python3" tools/start.py --bundled "$@"
fi

# Development checkout / slim package: reuse a venv or the system Python.
if [ -x ".venv/bin/python" ]; then
  exec .venv/bin/python tools/start.py "$@"
fi

for candidate in python3.13 python3.12 python3.11 python3.10 \
                 /opt/homebrew/bin/python3 /usr/local/bin/python3 python3; do
  if command -v "$candidate" >/dev/null 2>&1; then
    if "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
      exec "$candidate" tools/start.py "$@"
    fi
  fi
done

echo "Python 3.10+ was not found."
echo "macOS:  brew install python@3.12"
echo "Linux:  sudo apt install python3.12 python3.12-venv"
read -r -p "Press Enter to close." _
