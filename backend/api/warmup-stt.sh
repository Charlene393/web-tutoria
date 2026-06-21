#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
VENV_PYTHON="${SCRIPT_DIR}/.venv/bin/python"

if [ ! -x "$VENV_PYTHON" ]; then
  echo "Backend virtual environment not found."
  echo "Run these commands first:"
  echo "  cd backend/api"
  echo "  bash setup-venv.sh"
  exit 1
fi

cd "$SCRIPT_DIR"
exec "$VENV_PYTHON" - <<'PY'
from app.core.config import settings
from app.integrations.faster_whisper_client import get_faster_whisper_model

print("Preparing faster-whisper model cache...")
model = get_faster_whisper_model()
print(f"Loaded faster-whisper model: {settings.faster_whisper_model_size}")
print(f"Device: {settings.faster_whisper_device}")
print(f"Compute type: {settings.faster_whisper_compute_type}")
print("Future speech-to-text requests should be faster after this first load.")
PY
