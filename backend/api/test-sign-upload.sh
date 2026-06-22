#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 1 ] || [ "$#" -gt 4 ]; then
  echo "Usage: bash test-sign-upload.sh /path/to/sign-file [include_speech=true|false] [output_path] [top_k]"
  echo 'Example: bash test-sign-upload.sh "KSL-Dataset/Pose Data/Batch 2/65/Extract/Landmarks/ME.npy" true ./sign-upload.wav 3'
  echo 'Example: bash test-sign-upload.sh "/Users/charlenembugua/Downloads/sign-video.mp4" false'
  exit 1
fi

SIGN_PATH="$1"
INCLUDE_SPEECH="${2:-false}"
OUTPUT_PATH="${3:-./sign-upload-output.wav}"
TOP_K="${4:-3}"
API_URL="${API_URL:-http://127.0.0.1:8000/api/v1/sign-to-text-upload}"
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
PROJECT_ROOT="$(CDPATH= cd -- "${SCRIPT_DIR}/../.." && pwd)"
RESOLVED_SIGN_PATH="$SIGN_PATH"

if [ ! -f "$RESOLVED_SIGN_PATH" ] && [ -f "${PROJECT_ROOT}/${SIGN_PATH}" ]; then
  RESOLVED_SIGN_PATH="${PROJECT_ROOT}/${SIGN_PATH}"
fi

if [ ! -f "$RESOLVED_SIGN_PATH" ]; then
  echo "Sign file not found: $SIGN_PATH"
  echo "Pass a real .npy landmark file or a video file such as .mp4 or .mov."
  exit 1
fi

TMP_RESPONSE="$(mktemp)"

cleanup() {
  rm -f "$TMP_RESPONSE"
}

trap cleanup EXIT

HTTP_STATUS="$(
  curl -sS \
    -o "$TMP_RESPONSE" \
    -w "%{http_code}" \
    -X POST "$API_URL" \
    -F "sign_file=@${RESOLVED_SIGN_PATH}" \
    -F "include_speech=${INCLUDE_SPEECH}" \
    -F "top_k=${TOP_K}"
)"

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
    "label": body.get("label"),
    "confidence": body.get("confidence"),
    "provider": body.get("provider"),
    "model_id": body.get("model_id"),
    "source_kind": body.get("source_kind"),
    "source_upload_filename": body.get("source_upload_filename"),
    "matched_landmark_path": body.get("matched_landmark_path"),
    "lesson_asset_id": body.get("lesson_asset_id"),
    "extracted_frame_count": body.get("extracted_frame_count"),
    "status": body.get("status"),
}
print(json.dumps(summary, indent=2))

top_matches = body.get("top_matches") or []
if top_matches:
    print(
        json.dumps(
            {
                "top_match_labels": [match.get("label") for match in top_matches],
            },
            indent=2,
        )
    )

speech = body.get("speech")
if include_speech:
    if not speech or not speech.get("audio_base64"):
        raise SystemExit("sign-to-text upload response did not include speech audio.")

    audio_bytes = base64.b64decode(speech["audio_base64"])
    output_path.write_bytes(audio_bytes)
    print(f"Saved speech audio to {output_path}")
PY
