#!/bin/zsh

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_PYTHON="$REPO_DIR/.venv/bin/python"

pause_on_error() {
  echo
  echo "$1"
  read "?Press Return to close..."
  exit 1
}

command -v python3 >/dev/null 2>&1 || pause_on_error "python3 is required but was not found on this Mac."

cd "$REPO_DIR"

if [[ ! -x "$VENV_PYTHON" ]]; then
  python3 -m venv .venv || pause_on_error "Failed to create the local Python environment."
fi

if ! "$VENV_PYTHON" -c "import numpy, matplotlib, ezdxf, tkinter" >/dev/null 2>&1; then
  "$VENV_PYTHON" -m pip install --upgrade pip || pause_on_error "Failed to upgrade pip."
  "$VENV_PYTHON" -m pip install -r requirements.txt || pause_on_error "Failed to install Cycloidal Drive dependencies."
fi

if [[ "${CYCLOIDAL_DRY_RUN:-0}" == "1" ]]; then
  echo "Cycloidal Drive launcher is ready."
  exit 0
fi

"$VENV_PYTHON" main_menu.py || pause_on_error "Cycloidal Drive failed to start."
