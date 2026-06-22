#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 3 ]; then
  echo "Usage: bash test-sign-sequence-upload.sh include_speech(true|false) output_path sign1.npy sign2.npy [sign3.npy ...]"
  echo 'Example: bash test-sign-sequence-upload.sh true ./sequence.wav "KSL-Dataset/Pose Data/Batch 2/65/Extract/Landmarks/ME.npy" "KSL-Dataset/Pose Data/Batch 2/76/Extract/Landmarks/WANT.npy"'
  exit 1
fi

INCLUDE_SPEECH="$1"
OUTPUT_PATH="$2"
shift 2

API_URL="${API_URL:-http://127.0.0.1:8000/api/v1/sign-sequence-to-text-upload}"
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
PROJECT_ROOT="$(CDPATH= cd -- "${SCRIPT_DIR}/../.." && pwd)"

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
  -F "include_speech=${INCLUDE_SPEECH}"
  -F "include_ksl=true"
)

for SIGN_PATH in "$@"; do
  RESOLVED_SIGN_PATH="$SIGN_PATH"
  if [ ! -f "$RESOLVED_SIGN_PATH" ] && [ -f "${PROJECT_ROOT}/${SIGN_PATH}" ]; then
    RESOLVED_SIGN_PATH="${PROJECT_ROOT}/${SIGN_PATH}"
  fi

  if [ ! -f "$RESOLVED_SIGN_PATH" ]; then
    echo "Sign file not found: $SIGN_PATH"
    exit 1
  fi

  CURL_ARGS+=(-F "sign_files=@${RESOLVED_SIGN_PATH}")
done

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
    "text": body.get("text"),
    "normalized_text": body.get("normalized_text"),
    "sign_count": body.get("sign_count"),
    "provider": body.get("provider"),
    "model_id": body.get("model_id"),
    "status": body.get("status"),
}
print(json.dumps(summary, indent=2))
print(
    json.dumps(
        {
            "labels": [item.get("label") for item in body.get("items", [])],
        },
        indent=2,
    )
)

speech = body.get("speech")
if include_speech:
  if not speech or not speech.get("audio_base64"):
    raise SystemExit("sign-sequence-to-text response did not include speech audio.")
  audio_bytes = base64.b64decode(speech["audio_base64"])
  output_path.write_bytes(audio_bytes)
  print(f"Saved speech audio to {output_path}")
PY
