#!/usr/bin/env bash

set -euo pipefail

if [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then
  echo "Usage: bash test-speech.sh /path/to/audio-file [include_ksl=true|false]"
  echo 'Example: bash test-speech.sh "/Users/charlenembugua/Downloads/sample.wav" true'
  exit 1
fi

AUDIO_PATH="$1"
INCLUDE_KSL="${2:-true}"
API_URL="${API_URL:-http://127.0.0.1:8000/api/v1/speech-to-text}"

if [ ! -f "$AUDIO_PATH" ]; then
  echo "Audio file not found: $AUDIO_PATH"
  echo "Replace the placeholder path with a real file on your machine."
  echo 'Example: bash test-speech.sh "/Users/charlenembugua/Downloads/sample.wav" true'
  exit 1
fi

if command -v afinfo >/dev/null 2>&1; then
  AUDIO_BYTES="$(afinfo "$AUDIO_PATH" 2>/dev/null | awk '/audio bytes:/ {print $3; exit}')"
  if [ -n "${AUDIO_BYTES:-}" ] && [ "$AUDIO_BYTES" = "0" ]; then
    echo "Audio file appears invalid or empty: $AUDIO_PATH"
    echo "macOS reports audio bytes: 0, so speech APIs will reject it."
    echo "Record a real voice clip first, then retry."
    exit 1
  fi
fi

curl -X POST "$API_URL" \
  -F "audio=@${AUDIO_PATH}" \
  -F "include_ksl=${INCLUDE_KSL}"

echo
