#!/usr/bin/env bash
set -euo pipefail

TEXT="${1:-}"
OUTPUT_PATH="${2:-./tts-output.wav}"
INCLUDE_KSL="${3:-false}"
API_URL="${API_URL:-http://127.0.0.1:8000/api/v1/text-to-speech}"

if [ -z "$TEXT" ]; then
  echo "Usage: bash test-tts.sh \"Text to speak\" [output_path] [include_ksl=true|false]"
  echo "Example: bash test-tts.sh \"I want food\" ./tts-output.wav true"
  exit 1
fi

TMP_REQUEST="$(mktemp)"
TMP_RESPONSE="$(mktemp)"

cleanup() {
  rm -f "$TMP_REQUEST" "$TMP_RESPONSE"
}

trap cleanup EXIT

python3 - "$TEXT" "$INCLUDE_KSL" > "$TMP_REQUEST" <<'PY'
import json
import sys

text = sys.argv[1]
include_ksl = sys.argv[2].strip().lower() == "true"

print(json.dumps({"text": text, "include_ksl": include_ksl}))
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
audio_bytes = base64.b64decode(body["audio_base64"])
output_path.write_bytes(audio_bytes)

summary = {
    "provider": body.get("provider"),
    "model_id": body.get("model_id"),
    "voice_id": body.get("voice_id"),
    "output_format": body.get("output_format"),
    "content_type": body.get("content_type"),
    "audio_size_bytes": body.get("audio_size_bytes"),
    "status": body.get("status"),
}

print(json.dumps(summary, indent=2))
print(f"Saved audio to {output_path}")

text_to_ksl = body.get("text_to_ksl")
if text_to_ksl:
    print(
        json.dumps(
            {
                "gloss": text_to_ksl.get("gloss"),
                "lesson_asset_id": text_to_ksl.get("lesson_asset_id"),
            },
            indent=2,
        )
    )
PY
