#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 1 ] || [ "$#" -gt 4 ]; then
  echo "Usage: bash test-photo-explain.sh /path/to/image [object_name] [include_speech=true|false] [output_path]"
  echo 'Example: bash test-photo-explain.sh "/Users/charlenembugua/Downloads/car.jpg" car true ./photo-explain.wav'
  exit 1
fi

IMAGE_PATH="$1"
OBJECT_NAME="${2:-}"
INCLUDE_SPEECH="${3:-false}"
OUTPUT_PATH="${4:-./photo-explain-output.wav}"
API_URL="${API_URL:-http://127.0.0.1:8000/api/v1/photo-explain-upload}"
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
PROJECT_ROOT="$(CDPATH= cd -- "${SCRIPT_DIR}/../.." && pwd)"
RESOLVED_IMAGE_PATH="$IMAGE_PATH"

if [ ! -f "$RESOLVED_IMAGE_PATH" ] && [ -f "${PROJECT_ROOT}/${IMAGE_PATH}" ]; then
  RESOLVED_IMAGE_PATH="${PROJECT_ROOT}/${IMAGE_PATH}"
fi

if [ ! -f "$RESOLVED_IMAGE_PATH" ]; then
  echo "Image file not found: $IMAGE_PATH"
  exit 1
fi

TMP_RESPONSE="$(mktemp)"

cleanup() {
  rm -f "$TMP_RESPONSE"
}

trap cleanup EXIT

CURL_ARGS=(
  -sS
  -o "$TMP_RESPONSE"
  -w "%{http_code}"
  -X POST "$API_URL"
  -F "image=@${RESOLVED_IMAGE_PATH}"
  -F "include_ksl=true"
  -F "include_speech=${INCLUDE_SPEECH}"
)

if [ -n "$OBJECT_NAME" ]; then
  CURL_ARGS+=(-F "object_name=${OBJECT_NAME}")
fi

HTTP_STATUS="$(curl "${CURL_ARGS[@]}")"

if [ "$HTTP_STATUS" != "200" ]; then
  cat "$TMP_RESPONSE"
  echo
  exit 1
fi

python3 - "$TMP_RESPONSE" "$OUTPUT_PATH" "$INCLUDE_SPEECH" <<'PY'
import base64
import json
from pathlib import Path
import sys

response_path = Path(sys.argv[1])
output_path = Path(sys.argv[2])
include_speech = sys.argv[3].strip().lower() == "true"

body = json.loads(response_path.read_text())
summary = {
    "object_name": body.get("object_name"),
    "normalized_object_name": body.get("normalized_object_name"),
    "suggested_sign": body.get("suggested_sign"),
    "provider": body.get("provider"),
    "source_kind": body.get("source_kind"),
    "status": body.get("status"),
}
print(json.dumps(summary, indent=2))
print(json.dumps({"explanation": body.get("explanation")}, indent=2))

speech = body.get("speech")
if include_speech:
  if not speech or not speech.get("audio_base64"):
    raise SystemExit("photo-explain response did not include speech audio.")
  audio_bytes = base64.b64decode(speech["audio_base64"])
  output_path.write_bytes(audio_bytes)
  print(f"Saved speech audio to {output_path}")
PY
