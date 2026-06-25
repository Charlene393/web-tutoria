#!/bin/sh
set -eu

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
VENV_DIR="${SCRIPT_DIR}/.venv"

if command -v python3.12 >/dev/null 2>&1; then
  PYTHON_BIN="$(command -v python3.12)"
elif [ -x /opt/homebrew/bin/python3.12 ]; then
  PYTHON_BIN="/opt/homebrew/bin/python3.12"
else
  echo "Python 3.12 was not found."
  echo "Install it with:"
  echo "  brew install python@3.12"
  echo
  echo "Then re-run:"
  echo "  cd backend/api"
  echo "  bash setup-venv.sh"
  exit 1
fi

echo "Using Python at: ${PYTHON_BIN}"

rm -rf "$VENV_DIR"
"$PYTHON_BIN" -m venv "$VENV_DIR"

# shellcheck disable=SC1090
. "${VENV_DIR}/bin/activate"
python -m pip install --upgrade pip
pip install -r "${SCRIPT_DIR}/requirements-dev.txt"
if [ -f "${SCRIPT_DIR}/requirements-sign-video.txt" ]; then
  pip install -r "${SCRIPT_DIR}/requirements-sign-video.txt"
fi

echo
echo "Backend virtual environment is ready."
echo "Next:"
echo "  source ${VENV_DIR}/bin/activate"
echo "  brew install espeak-ng"
echo "  bash start-dev.sh"
