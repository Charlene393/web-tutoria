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
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements-dev.txt
cp .env.example .env
bash start-dev.sh
```

That is the main supported local dev flow for this backend.

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
- `POST /api/v1/speech-to-text`
- `POST /api/v1/text-to-ksl`
- `POST /api/v1/sign-to-text`
- `POST /api/v1/photo-explain`

## If you are using ElevenLabs for speech

For this project, ElevenLabs is a good fit for:

- text to speech output for lessons and responses
- speech to text transcription for uploaded or recorded audio

### Install

These packages are now expected in `requirements-dev.txt`:

- `elevenlabs`
- `python-multipart`

`python-multipart` is needed for FastAPI file upload endpoints.

### Configure

Add these values to `backend/api/.env`:

```env
ELEVENLABS_API_KEY=your_api_key_here
ELEVENLABS_TTS_VOICE_ID=your_voice_id_here
ELEVENLABS_TTS_MODEL_ID=eleven_flash_v2_5
ELEVENLABS_STT_MODEL_ID=scribe_v2
```

Recommended starting choices:

- `eleven_flash_v2_5` for low-latency TTS
- `scribe_v2` for transcription

### Backend files involved

- `app/core/config.py` for env loading
- `app/integrations/elevenlabs_client.py` for client creation
- `app/services/speech_service.py` for TTS and STT orchestration

### Recommended first use

Do not wire ElevenLabs into `text-to-ksl` first.

Instead:

1. keep `text-to-ksl` as plain text logic
2. use ElevenLabs in `speech-to-text`
3. later use ElevenLabs in `text-to-speech` output after KSL mapping

### Speech-to-text test flow

Reinstall dependencies first so the backend has both `elevenlabs` and `python-multipart`:

```bash
cd backend/api
source .venv/bin/activate
pip install -r requirements-dev.txt
```

Set your key in `backend/api/.env`:

```env
ELEVENLABS_API_KEY=your_real_api_key
ELEVENLABS_STT_MODEL_ID=scribe_v2
```

Start the backend:

```bash
bash start-dev.sh
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
- `provider` is `elevenlabs`
- `model_id` is `scribe_v2`
- `text_to_ksl.gloss` is present when the transcript matches supported KSL terms
- `text_to_ksl.lesson_assets` comes from the cleaned lesson catalog

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
