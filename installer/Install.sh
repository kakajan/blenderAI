#!/usr/bin/env bash
# BlenderAI Installer — macOS / Linux
set -euo pipefail
cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3.11+ is required."
  exit 1
fi

# Ensure tkinter is available (needed by customtkinter)
if ! python3 -c "import tkinter" >/dev/null 2>&1; then
  echo "Warning: tkinter not found. GUI may fail; CLI fallback is available."
  echo "  Debian/Ubuntu: sudo apt install python3-tk"
  echo "  Fedora:        sudo dnf install python3-tkinter"
  echo "  macOS:         usually bundled with python.org installer / brew python-tk"
fi

python3 -m pip install -q -r requirements.txt
exec python3 install.py "$@"
