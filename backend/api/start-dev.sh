#!/bin/sh
set -eu

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
VENV_PYTHON="${SCRIPT_DIR}/.venv/bin/python"

if [ ! -x "$VENV_PYTHON" ]; then
  echo "Backend virtual environment not found."
  echo "Run these commands first:"
  echo "  cd backend/api"
  echo "  bash setup-venv.sh"
  exit 1
fi

PY_VERSION="$("$VENV_PYTHON" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
case "$PY_VERSION" in
  3.11|3.12)
    ;;
  *)
    echo "Backend .venv is using Python ${PY_VERSION}, but Kokoro requires Python 3.11 or 3.12."
    echo "Rebuild the backend virtual environment with:"
    echo "  cd backend/api"
    echo "  bash setup-venv.sh"
    exit 1
    ;;
esac

cd "$SCRIPT_DIR"
PORT_TO_USE="${PORT:-8000}"

if lsof -nP -iTCP:"${PORT_TO_USE}" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Port ${PORT_TO_USE} is already in use."
  echo "Run this to see the current listener:"
  echo "  lsof -nP -iTCP:${PORT_TO_USE} -sTCP:LISTEN"
  echo "Then stop it and retry:"
  echo "  kill <pid>"
  exit 1
fi

exec "$VENV_PYTHON" -m uvicorn app.main:app --reload --reload-dir app --host 127.0.0.1 --port "${PORT_TO_USE}"
