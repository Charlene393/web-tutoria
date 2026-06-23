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
from app.integrations.kokoro_client import get_kokoro_pipeline

print("Preparing Kokoro model cache...")
pipeline = get_kokoro_pipeline()

print(f"Loading Kokoro voice: {settings.kokoro_voice}")
pipeline.load_voice(settings.kokoro_voice)

print("Running a tiny synthesis warmup...")
result = next(
    pipeline(
        "Hello",
        voice=settings.kokoro_voice,
        speed=settings.kokoro_speed,
        split_pattern=r"\n+",
    ),
    None,
)

if result is None or result[2] is None:
    raise SystemExit("Kokoro warmup failed to produce audio.")

print("Kokoro warmup complete.")
print("Future text-to-speech requests should be much faster.")
print("Cached files are typically stored under ~/Library/Caches/huggingface/hub")
PY
