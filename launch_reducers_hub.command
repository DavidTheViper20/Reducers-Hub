#!/bin/zsh

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
CYCLOIDAL_DIR="$ROOT_DIR/Cycloidal Drive Demo Hub"
VENV_PYTHON="$CYCLOIDAL_DIR/.venv/bin/python"

pause_on_error() {
  echo
  echo "$1"
  read "?Press Return to close..."
  exit 1
}

command -v python3 >/dev/null 2>&1 || pause_on_error "python3 is required but was not found on this Mac."

if [[ "${CYCLOIDAL_DRY_RUN:-0}" == "1" ]]; then
  echo "Reducers Hub launcher is ready."
  exit 0
fi

if [[ ! -x "$VENV_PYTHON" ]]; then
  python3 -m venv "$CYCLOIDAL_DIR/.venv" || pause_on_error "Failed to create the local Python environment."
fi

if ! "$VENV_PYTHON" -c "import numpy, matplotlib, ezdxf, tkinter" >/dev/null 2>&1; then
  "$VENV_PYTHON" -m pip install --upgrade pip || pause_on_error "Failed to upgrade pip."
  "$VENV_PYTHON" -m pip install -r "$CYCLOIDAL_DIR/requirements.txt" || pause_on_error "Failed to install Reducers Hub dependencies."
fi

cd "$ROOT_DIR"
"$VENV_PYTHON" reducers_hub.py || pause_on_error "Reducers Hub failed to start."
