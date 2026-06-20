#!/bin/sh
set -eu

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
VENV_PYTHON="${SCRIPT_DIR}/.venv/bin/python"

if [ ! -x "$VENV_PYTHON" ]; then
  echo "Backend virtual environment not found."
  echo "Run these commands first:"
  echo "  cd backend/api"
  echo "  python3 -m venv .venv"
  echo "  source .venv/bin/activate"
  echo "  pip install -r requirements-dev.txt"
  exit 1
fi

cd "$SCRIPT_DIR"
exec "$VENV_PYTHON" -m uvicorn app.main:app --reload --reload-dir app --host 127.0.0.1 --port "${PORT:-8000}"
