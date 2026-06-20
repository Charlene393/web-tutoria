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

- Whisper wrapper
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

## Suggested first backend work order

1. Keep `health` working at all times.
2. Finish `text-to-ksl` first because it is the simplest core flow.
3. Add `sign-to-text` after the dataset manifest and model interface are ready.
4. Add `speech-to-text` once audio upload shape is decided.
5. Add `photo-explain` after the lesson library can return supported signs.

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
