# Backend Demo Checklist

Use this file when you want to:

- clone the project and get the backend running
- verify the backend is healthy
- test each stable backend flow in the right order
- know what is ready and what is still environment-limited

For approved sample payloads after you finish the checks here, use [DEMO_RESPONSES.md](/Users/charlenembugua/Documents/projects/web-tutoria/backend/api/DEMO_RESPONSES.md).

This checklist assumes you are working from the repo root:

```bash
/Users/charlenembugua/Documents/projects/web-tutoria
```

## 1. Prerequisites

Install these first:

- Python `3.12`
- Git
- Homebrew on macOS

For Kokoro on macOS, also install:

```bash
brew install python@3.12 espeak-ng
```

Why Python `3.12`:

- this backend uses Kokoro for local text-to-speech
- Kokoro is not reliable in this repo with Python `3.13`

## 2. First-time setup

Run this from the repo root:

```bash
cd backend/api
bash setup-venv.sh
cp .env.example .env
```

What this does:

- creates `backend/api/.venv`
- installs backend dependencies
- gives you a local `.env` file

## 3. Optional sign-video extras

Only do this if you want to experiment with uploaded sign videos.

```bash
cd backend/api
source .venv/bin/activate
pip install -r requirements-sign-video.txt
bash download-sign-video-model.sh
```

Important:

- `.npy` landmark uploads are the stable path
- raw sign-video extraction on macOS is still environment-limited
- for backend demo purposes, treat `.npy` uploads as the reliable sign input flow

## 4. Warm up local models

Run this before the first real demo so model downloads happen once:

```bash
cd backend/api
bash warmup-kokoro.sh
bash warmup-stt.sh
```

What to expect:

- Kokoro downloads and caches its voice/model assets
- faster-whisper downloads and caches its speech-to-text model
- later requests become much faster

## 5. Start the backend

Run:

```bash
cd backend/api
bash start-dev.sh
```

Expected result:

- FastAPI starts on `http://127.0.0.1:8000`
- Swagger docs are available at `http://127.0.0.1:8000/docs`

If port `8000` is already in use:

```bash
lsof -nP -iTCP:8000 -sTCP:LISTEN
kill <pid>
```

Then run `bash start-dev.sh` again.

## 6. Health check

In a new terminal:

```bash
cd backend/api
curl http://127.0.0.1:8000/api/v1/health
```

You want to see:

- app name and version
- `status` showing the backend is healthy
- readiness details for lesson catalog, sign recognizer, Kokoro, and faster-whisper

If this fails, do not continue to the rest of the demo yet.

## 7. Stable demo order

Run the backend demo in this order:

1. `health`
2. `text-to-ksl`
3. `text-to-speech`
4. `speech-to-text`
5. `sign-to-text`
6. `sign-to-text-upload`
7. `sign-sequence-to-text`
8. `sign-sequence-to-text-upload`
9. `photo-explain`
10. `photo-explain-upload`

That order makes debugging easier because each later feature depends on pieces from earlier ones.

## 8. Demo commands

All commands below assume the API server is already running.

### A. Text to KSL

```bash
curl -X POST http://127.0.0.1:8000/api/v1/text-to-ksl \
  -H "Content-Type: application/json" \
  -d '{
    "text": "I want food and water"
  }'
```

You should see:

- `gloss` like `["ME", "WANT", "FOOD", "WATER"]`
- `lesson_assets`
- `lesson_asset_id`
- `status: "ok"`

### B. Text to speech

```bash
cd backend/api
bash test-tts.sh "I want food" ./tts-output.wav true
```

You should see:

- provider `kokoro`
- an output summary
- `Saved audio to tts-output.wav`
- a `gloss` block if `include_ksl=true`

### C. Speech to text

Use a real audio file on your machine.

```bash
cd backend/api
bash test-speech.sh "/absolute/path/to/real-audio-file.m4a" true
```

You should see:

- a transcript
- provider information
- `text_to_ksl` if `include_ksl=true`

Important:

- do not use a placeholder path
- do not use a fake or corrupted audio file

### D. Sign to text from dataset landmark path

```bash
curl -X POST http://127.0.0.1:8000/api/v1/sign-to-text \
  -H "Content-Type: application/json" \
  -d '{
    "landmark_path": "KSL-Dataset/Pose Data/Batch 2/65/Extract/Landmarks/ME.npy",
    "top_k": 3
  }'
```

You should see:

- `label`
- `confidence`
- `top_matches`
- `lesson_asset_id`
- `status: "ok"`

### E. Sign to text plus speech

```bash
cd backend/api
bash test-sign-speech.sh "KSL-Dataset/Pose Data/Batch 2/65/Extract/Landmarks/ME.npy" ./sign-me.wav 3
```

You should see:

- sign recognition summary
- generated speech summary
- `Saved speech audio to ./sign-me.wav`

### F. Sign to text upload using `.npy`

```bash
cd backend/api
bash test-sign-upload.sh "KSL-Dataset/Pose Data/Batch 2/65/Extract/Landmarks/ME.npy" true ./sign-upload.wav 3
```

You should see:

- recognized label
- top match labels
- speech audio saved if `true`

This is the recommended upload demo for now.

### G. Sign sequence to text from JSON

```bash
curl -X POST http://127.0.0.1:8000/api/v1/sign-sequence-to-text \
  -H "Content-Type: application/json" \
  -d '{
    "landmark_paths": [
      "KSL-Dataset/Pose Data/Batch 2/65/Extract/Landmarks/ME.npy",
      "KSL-Dataset/Pose Data/Batch 2/76/Extract/Landmarks/WANT.npy",
      "KSL-Dataset/Pose Data/Batch 2/162/Extract/Landmarks/FOOD.npy"
    ],
    "include_ksl": true,
    "top_k": 3
  }'
```

You should see:

- `text` like `ME WANT FOOD`
- `items` for each sign
- `sign_count`
- optional `text_to_ksl`

### H. Sign sequence to text upload using multiple `.npy` files

```bash
cd backend/api
bash test-sign-sequence-upload.sh true ./sequence.wav \
  "KSL-Dataset/Pose Data/Batch 2/65/Extract/Landmarks/ME.npy" \
  "KSL-Dataset/Pose Data/Batch 2/76/Extract/Landmarks/WANT.npy" \
  "KSL-Dataset/Pose Data/Batch 2/162/Extract/Landmarks/FOOD.npy"
```

You should see:

- combined `text`
- recognized `labels`
- saved speech audio

### I. Photo explain from JSON

```bash
curl -X POST http://127.0.0.1:8000/api/v1/photo-explain \
  -H "Content-Type: application/json" \
  -d '{
    "object_name": "car",
    "include_ksl": true
  }'
```

You should see:

- `object_name`
- `explanation`
- `suggested_sign`
- optional `text_to_ksl`

### J. Photo explain upload

Use a real image file on your machine.

```bash
cd backend/api
bash test-photo-explain.sh "/absolute/path/to/car.jpg" car true ./photo-explain.wav
```

You should see:

- object summary
- explanation text
- saved speech audio if `true`

## 9. What is stable right now

These are the backend flows you can treat as ready for integration testing:

- `GET /api/v1/health`
- `POST /api/v1/text-to-ksl`
- `POST /api/v1/text-to-speech`
- `POST /api/v1/speech-to-text`
- `POST /api/v1/sign-to-text`
- `POST /api/v1/sign-to-text-upload` using `.npy`
- `POST /api/v1/sign-sequence-to-text`
- `POST /api/v1/sign-sequence-to-text-upload` using `.npy`
- `POST /api/v1/photo-explain`
- `POST /api/v1/photo-explain-upload`

## 10. What is still limited

These parts are not the best thing to build your frontend around yet:

- raw uploaded sign-video extraction on macOS
- continuous sentence segmentation from one long sign video
- fully automatic visual recognition for photo explain

For now, build around:

- text
- audio
- cleaned dataset-backed `.npy` sign inputs
- lesson asset playback

## 11. If something fails

Check these first:

### Problem: `bash start-dev.sh` fails

Likely causes:

- `.venv` was not created
- Python `3.13` was used earlier
- port `8000` is already occupied

Fix:

```bash
cd backend/api
rm -rf .venv
bash setup-venv.sh
bash start-dev.sh
```

### Problem: speech-to-text is slow or fails on first run

Fix:

```bash
cd backend/api
bash warmup-stt.sh
```

### Problem: text-to-speech is slow on first run

Fix:

```bash
cd backend/api
bash warmup-kokoro.sh
```

### Problem: `curl: (26) Failed to open/read local data from file/application`

Cause:

- your file path is not real

Fix:

- replace the placeholder path with an actual file on your machine
- confirm it exists with `ls -lh "/absolute/path/to/file"`

### Problem: uploaded sign video fails

Cause:

- macOS MediaPipe runtime limitations or missing optional sign-video setup

Fix:

- switch to `.npy` landmark uploads for now
- treat raw video extraction as optional, not required for the current backend milestone

## 12. Recommended next step after this checklist

Once every stable command above is working on your machine, the next good backend step is:

- freeze the API contracts
- save one sample request and one sample response for each stable endpoint
- then move to frontend integration with confidence

That contract reference now lives in [DEMO_RESPONSES.md](/Users/charlenembugua/Documents/projects/web-tutoria/backend/api/DEMO_RESPONSES.md).
