#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 1 ] || [ "$#" -gt 4 ]; then
  echo "Usage: bash test-sign-speech.sh /path/to/landmark.npy [output_path] [top_k] [voice_id]"
  echo 'Example: bash test-sign-speech.sh "KSL-Dataset/Pose Data/Batch 2/65/Extract/Landmarks/ME.npy" ./sign-me.wav 3 af_heart'
  exit 1
fi

LANDMARK_PATH="$1"
OUTPUT_PATH="${2:-./sign-speech-output.wav}"
TOP_K="${3:-3}"
VOICE_ID="${4:-}"
API_URL="${API_URL:-http://127.0.0.1:8000/api/v1/sign-to-text}"
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
PROJECT_ROOT="$(CDPATH= cd -- "${SCRIPT_DIR}/../.." && pwd)"
RESOLVED_LANDMARK_PATH="$LANDMARK_PATH"

if [ ! -f "$RESOLVED_LANDMARK_PATH" ] && [ -f "${PROJECT_ROOT}/${LANDMARK_PATH}" ]; then
  RESOLVED_LANDMARK_PATH="${PROJECT_ROOT}/${LANDMARK_PATH}"
fi

if [ ! -f "$RESOLVED_LANDMARK_PATH" ]; then
  echo "Landmark file not found: $LANDMARK_PATH"
  echo "Pass a real .npy landmark file from your cleaned dataset."
  echo 'Example: bash test-sign-speech.sh "KSL-Dataset/Pose Data/Batch 2/65/Extract/Landmarks/ME.npy" ./sign-me.wav 3'
  exit 1
fi

TMP_REQUEST="$(mktemp)"
TMP_RESPONSE="$(mktemp)"

cleanup() {
  rm -f "$TMP_REQUEST" "$TMP_RESPONSE"
}

trap cleanup EXIT

python3 - "$RESOLVED_LANDMARK_PATH" "$TOP_K" "$VOICE_ID" > "$TMP_REQUEST" <<'PY'
import json
import sys

landmark_path = sys.argv[1]
top_k = int(sys.argv[2])
voice_id = sys.argv[3].strip()

payload = {
    "landmark_path": landmark_path,
    "top_k": top_k,
    "include_speech": True,
    "output_format": "wav",
}
if voice_id:
    payload["voice_id"] = voice_id

print(json.dumps(payload))
PY

HTTP_STATUS="$(
  curl -sS \
    -o "$TMP_RESPONSE" \
    -w "%{http_code}" \
    -X POST "$API_URL" \
    -H "Content-Type: application/json" \
    --data @"$TMP_REQUEST"
)"

if [ "$HTTP_STATUS" != "200" ]; then
  cat "$TMP_RESPONSE"
  echo
  exit 1
fi

python3 - "$TMP_RESPONSE" "$OUTPUT_PATH" <<'PY'
import base64
import json
from pathlib import Path
import sys

response_path = Path(sys.argv[1])
output_path = Path(sys.argv[2])

body = json.loads(response_path.read_text())
speech = body.get("speech")
if not speech or not speech.get("audio_base64"):
    raise SystemExit("sign-to-text response did not include speech audio.")

audio_bytes = base64.b64decode(speech["audio_base64"])
output_path.write_bytes(audio_bytes)

summary = {
    "label": body.get("label"),
    "confidence": body.get("confidence"),
    "provider": body.get("provider"),
    "model_id": body.get("model_id"),
    "lesson_asset_id": body.get("lesson_asset_id"),
    "speech_provider": speech.get("provider"),
    "voice_id": speech.get("voice_id"),
    "output_format": speech.get("output_format"),
    "content_type": speech.get("content_type"),
    "audio_size_bytes": speech.get("audio_size_bytes"),
    "status": body.get("status"),
}

print(json.dumps(summary, indent=2))
print(f"Saved speech audio to {output_path}")

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
PY
