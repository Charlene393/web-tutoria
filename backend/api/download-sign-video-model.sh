#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
MODEL_PATH="${1:-${SCRIPT_DIR}/app/data/holistic_landmarker.task}"
MODEL_DIR="$(dirname "$MODEL_PATH")"
MODEL_URL="https://storage.googleapis.com/mediapipe-models/holistic_landmarker/holistic_landmarker/float16/latest/holistic_landmarker.task"

mkdir -p "$MODEL_DIR"

curl -L "$MODEL_URL" -o "$MODEL_PATH"

echo "Saved MediaPipe holistic model to: $MODEL_PATH"
