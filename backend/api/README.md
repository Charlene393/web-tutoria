# API Backend

This service is the orchestration layer for the KSL learning system.

Its job is to:

- receive requests from the frontend
- validate inputs and outputs
- call speech, sign, and photo pipelines
- return stable API responses
- keep model-specific code out of route handlers

## FastAPI setup

Recommended: run from inside `backend/api`.

If you want the safest first-time setup, copy and paste this whole block:

```bash
cd backend/api
bash setup-venv.sh
cp .env.example .env
bash start-dev.sh
```

That is the main supported local dev flow for this backend.

Important: because Kokoro is used for local text-to-speech, this backend currently needs Python `3.11` or `3.12`. Python `3.13` will not install the Kokoro stack correctly.

Then open:

- `http://127.0.0.1:8000/docs`
- `http://127.0.0.1:8000/api/v1/health`

## Folder structure

```text
backend/api/
  app/
    api/
      routes/         FastAPI endpoints grouped by feature
      router.py       main API router
    core/             settings, config, shared backend setup
    integrations/     wrappers for external APIs and model providers
    pipelines/        higher-level speech/sign/photo orchestration
    schemas/          request and response models
    services/         business logic called by route handlers
    main.py           FastAPI app entrypoint
  tests/              API and service tests
  .env.example
  pyproject.toml
  README.md
  setup-venv.sh
```

## What each backend folder should contain

### `app/api/routes`

Keep only HTTP concerns here:

- request parsing
- response models
- calling a service function
- returning status codes

Avoid putting model-loading or large business logic in route files.

### `app/core`

Put backend-wide setup here:

- environment settings
- CORS settings
- constants
- logging setup later

### `app/schemas`

Use this for Pydantic models:

- request bodies
- response bodies
- shared DTOs between routes and services

### `app/services`

This is the most important working folder early on.

Put feature logic here:

- `speech_service.py`
- `text_to_ksl_service.py`
- `sign_to_text_service.py`
- `photo_explain_service.py`

These services should coordinate the flow for a single feature.

### `app/integrations`

Use this for external tools or providers:

- speech-to-text provider client
- text-to-speech provider client
- vision model client
- storage client

This keeps third-party code isolated.

### `app/pipelines`

Use this when one feature needs multiple steps.

Example:

- speech upload -> transcription -> glossary mapping -> lesson selection

Not every project needs this folder on day one, but your product likely will.

### `tests`

Start small:

- route tests
- schema tests
- service tests

You do not need heavy model tests first. Begin with API contract tests.

## Recommended endpoints

- `GET /api/v1/health`
- `POST /api/v1/text-to-speech`
- `POST /api/v1/speech-to-text`
- `POST /api/v1/text-to-ksl`
- `POST /api/v1/sign-to-text`
- `POST /api/v1/photo-explain`

## Speech providers in this backend

For the current backend setup:

- `Kokoro` handles text-to-speech locally with no billing
- `faster-whisper` handles speech-to-text locally with no billing

### Install

These packages are now expected in `requirements-dev.txt`:

- `kokoro`
- `misaki`
- `numpy`
- `soundfile`
- `faster-whisper`
- `python-multipart`

`python-multipart` is needed for FastAPI file upload endpoints.

On macOS, Kokoro may also need:

```bash
brew install espeak-ng
```

This repo pins a Kokoro version that is meant to install cleanly in the current backend setup, but only on Python `3.11` or `3.12`. If you previously created `.venv` with Python `3.13`, rebuild it with `bash setup-venv.sh`.

### Configure

Add these values to `backend/api/.env`:

```env
FASTER_WHISPER_MODEL_SIZE=small
FASTER_WHISPER_DEVICE=cpu
FASTER_WHISPER_COMPUTE_TYPE=int8
FASTER_WHISPER_LANGUAGE=en
FASTER_WHISPER_BEAM_SIZE=5
FASTER_WHISPER_VAD_FILTER=true
KOKORO_VOICE=af_heart
KOKORO_LANG_CODE=a
KOKORO_MODEL_ID=Kokoro-82M
KOKORO_SAMPLE_RATE=24000
KOKORO_SPEED=1.0
```

Recommended starting choices:

- `af_heart` for Kokoro voice
- `small` for the faster-whisper model size

Important for the first STT run:

- `faster-whisper` downloads its model files from Hugging Face the first time
- run `bash warmup-stt.sh` once while you are connected to the internet
- after that, speech-to-text works from the cached local model

### Backend files involved

- `app/core/config.py` for env loading
- `app/integrations/faster_whisper_client.py` for local speech-to-text loading
- `app/integrations/kokoro_client.py` for Kokoro pipeline loading
- `app/services/speech_service.py` for TTS and STT orchestration
- `app/services/sign_features.py` for landmark feature extraction
- `app/services/sign_recognizer.py` for the dataset-backed sign index
- `app/services/sign_to_text_service.py` for sign recognition orchestration

### Recommended first use

Do not wire heavy model logic into `text-to-ksl` first.

Instead:

1. keep `text-to-ksl` as plain text logic
2. use Kokoro in `text-to-speech`
3. use faster-whisper in `speech-to-text`

### Text-to-speech test flow

Install backend dependencies and the macOS speech helper first:

```bash
cd backend/api
bash setup-venv.sh
brew install espeak-ng
```

Set your Kokoro configuration in `backend/api/.env`:

```env
KOKORO_VOICE=af_heart
KOKORO_LANG_CODE=a
```

Start the backend:

```bash
bash start-dev.sh
```

On the very first Kokoro run, the backend downloads the model weights from Hugging Face. That download is large, so the first request can take a while. If you want to do that step ahead of time, run:

```bash
bash warmup-kokoro.sh
```

Then test with `curl`:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/text-to-speech \
  -H "Content-Type: application/json" \
  -d '{
    "text": "I want food",
    "include_ksl": true
  }'
```

Or use the helper script from `backend/api`:

```bash
bash test-tts.sh "I want food" ./tts-output.wav true
```

What success looks like:

- `audio_base64` is present
- `content_type` is `audio/wav`
- `voice_id` and `model_id` reflect your Kokoro config
- `text_to_ksl.gloss` is present when `include_ksl=true`
- the helper script saves a playable audio file locally

This endpoint returns JSON for backend-first testing. Later, if you want, we can add a streaming or file-download version for the frontend player.

### Speech-to-text test flow

Speech-to-text is now local with faster-whisper, so this part does not need any API key.

Reinstall dependencies first so the backend has both `faster-whisper` and `python-multipart`:

```bash
cd backend/api
bash setup-venv.sh
```

Set your local speech configuration in `backend/api/.env`:

```env
FASTER_WHISPER_MODEL_SIZE=small
FASTER_WHISPER_DEVICE=cpu
FASTER_WHISPER_COMPUTE_TYPE=int8
FASTER_WHISPER_LANGUAGE=en
```

Start the backend:

```bash
bash start-dev.sh
```

On the very first faster-whisper run, the backend downloads the transcription model from Hugging Face. If you want to do that step ahead of time, run:

```bash
bash warmup-stt.sh
```

Then test with a real audio file:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/speech-to-text \
  -F "audio=@/absolute/path/to/sample.wav" \
  -F "include_ksl=true"
```

Or use the helper script from `backend/api`:

```bash
bash test-speech.sh "/Users/charlenembugua/Downloads/sample.wav" true
```

What success looks like:

- `transcript` contains the spoken text
- `provider` is `faster_whisper`
- `model_id` reflects your local model size such as `small`
- `text_to_ksl.gloss` is present when the transcript matches supported KSL terms
- `text_to_ksl.lesson_assets` comes from the cleaned lesson catalog

### Sign-to-text MVP flow

This backend now supports a first sign-to-text MVP using `.npy` landmark files from your cleaned KSL dataset.

What it does today:

- loads a landmark sequence from `landmark_path`
- builds or loads a local recognizer artifact from the cleaned manifest
- restricts runtime recognition to the bundled `app/data/ksl_sign_v1_labels.json` starter vocabulary
- keeps only labels with at least `5` cleaned samples by default
- matches the sequence against cleaned dataset samples
- returns the predicted label, confidence, and top candidate labels

What it does not do yet:

- webcam capture
- raw video parsing
- live browser inference

Build the recognizer artifact ahead of time if you want:

```bash
backend/api/.venv/bin/python backend/scripts/train_sign_classifier.py
```

The default build uses:

- `app/data/ksl_sign_v1_labels.json` as the curated `v1` label set
- `SIGN_RECOGNIZER_MIN_SAMPLES_PER_LABEL=5` as the minimum cleaned support threshold

Then test the endpoint with a real dataset landmark file:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/sign-to-text \
  -H "Content-Type: application/json" \
  -d '{
    "landmark_path": "KSL-Dataset/Pose Data/Batch 2/65/Extract/Landmarks/ME.npy",
    "top_k": 3
  }'
```

What success looks like:

- `label` is predicted from the cleaned dataset
- `provider` is `dataset_knn`
- `model_id` is `dataset-sign-knn-v1`
- `matched_landmark_path` points to the closest cleaned sample
- `top_matches` returns candidate labels for debugging

You can also test it in the interactive docs at:

- `http://127.0.0.1:8000/docs`

If you want transcription only, without KSL mapping:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/speech-to-text \
  -F "audio=@/absolute/path/to/sample.wav" \
  -F "include_ksl=false"
```

## Suggested first backend work order

1. Keep `health` working at all times.
2. Finish `text-to-ksl` first because it is the simplest core flow.
3. Add `sign-to-text` after the dataset manifest and model interface are ready.
4. Add `speech-to-text` once audio upload shape is decided.
5. Add `photo-explain` after the lesson library can return supported signs.

## Dataset cleanup workflow

Before training or broadening the vocabulary, review the pose dataset safely from the repo root:

```bash
backend/api/.venv/bin/python backend/scripts/generate_ksl_cleanup_reports.py
backend/api/.venv/bin/python backend/scripts/build_cleanup_decisions_template.py
backend/api/.venv/bin/python backend/scripts/prefill_cleanup_decisions.py
backend/api/.venv/bin/python backend/scripts/apply_cleanup_decisions_to_manifest.py
backend/api/.venv/bin/python backend/scripts/build_ksl_lesson_catalog.py
```

This creates:

- `backend/reports/ksl_cleanup/review_candidates.csv`
- `backend/reports/ksl_cleanup/suspicious_labels.csv`
- `backend/reports/ksl_cleanup/cleanup_decisions.csv`
- `backend/reports/ksl_cleanup/cleaned/manifest.csv`
- `backend/api/app/data/ksl_lesson_catalog.json`

Use `cleanup_decisions.csv` as the manual review sheet. Fill in:

- `selected_action`
- `target_label`
- `notes`

The template is backend-safe:

- it does not change the raw `.npy` files
- it does not change the stickman `.mp4` files
- it refuses to overwrite an existing decision sheet unless you pass `--force`
- the apply step only writes derived cleaned CSV and JSON outputs

For `text-to-ksl`, the backend now uses `ksl_lesson_catalog.json` as the lesson asset source of truth instead of scanning the raw dataset folders directly.

## How to add a new feature cleanly

For a new endpoint such as `text-to-ksl`:

1. Add request and response models in `app/schemas`.
2. Add or update the business function in `app/services`.
3. Keep the route thin in `app/api/routes`.
4. Add tests in `tests`.

That pattern will keep the backend easy to grow.

## Fix for reload and import issues

If you keep seeing reload loops or temporary import errors while using `--reload`, the usual cause is that the local `.venv` is inside `backend/api` and Uvicorn is watching it too.

Use the provided start script instead:

```bash
bash start-dev.sh
```

That script:

- uses the backend-local `.venv`
- runs Uvicorn from the correct folder
- watches only `app/`
- avoids reload noise from `.venv`

## Commands to avoid

From inside `backend/api`, do not run:

```bash
uvicorn backend.api.app.main:app --reload
```

That import path is for running from the repo root, not from `backend/api`.

Also avoid starting Uvicorn before dependency installation finishes, because you can hit temporary import errors such as:

- `ModuleNotFoundError: No module named 'pydantic_settings'`

## Quick recovery

If startup gets messy, run this exact sequence:

```bash
cd backend/api
source .venv/bin/activate
pip install -r requirements-dev.txt
bash start-dev.sh
```
