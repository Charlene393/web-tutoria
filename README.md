# Web Tutoria

Web Tutoria is an AI learning system for Kenyan Sign Language (KSL).

The project is being built around three core flows:

- speech -> text -> KSL lesson or sign playback
- text -> speech + KSL lesson playback
- signer video or webcam -> text -> speech
- photo upload -> explanation -> matching KSL lesson

## Project structure

```text
backend/
  api/                 FastAPI backend
  scripts/             dataset cleanup and analysis scripts
frontend/
  web/                 frontend app shell
KSL-Dataset/
  Pose Data/           local pose and landmark dataset
```

## Prerequisites

Install these before setup:

- Python `3.11` or `3.12`
- Git

Frontend tooling can be added later when the web app is bootstrapped.

## Clone and setup

If you only want the backend running, use this full copy-paste flow:

```bash
git clone <your-repo-url>
cd web-tutoria
cd backend/api
bash setup-venv.sh
cp .env.example .env
bash start-dev.sh
```

Use that flow exactly if you are setting the project up for the first time.

### 1. Clone the repository

```bash
git clone <your-repo-url>
cd web-tutoria
```

### 2. Create and activate the backend virtual environment

```bash
cd backend/api
bash setup-venv.sh
```

### 3. Install backend dependencies

This is handled by `setup-venv.sh`.

### 4. Create backend environment variables

```bash
cp .env.example .env
```

### 5. Start the FastAPI backend

Run this from `backend/api`:

```bash
bash start-dev.sh
```

This is the recommended startup command because it:

- uses `backend/api/.venv`
- runs from the correct backend folder
- reloads only when files in `app/` change
- avoids watching `.venv`

Then open:

- `http://127.0.0.1:8000/docs`
- `http://127.0.0.1:8000/api/v1/health`

## Backend folder guide

The FastAPI backend lives in `backend/api`.

```text
backend/api/
  app/
    api/
      routes/         endpoint files
      router.py       combines the route modules
    core/             settings and shared config
    schemas/          Pydantic request and response models
    services/         feature business logic
    integrations/     third-party provider wrappers
    pipelines/        multi-step orchestration flows
    main.py           FastAPI entrypoint
  tests/              backend tests
  .env.example
  pyproject.toml
  setup-venv.sh
```

## Dataset note

The pose dataset is expected at:

```text
KSL-Dataset/Pose Data/
```

If someone clones the repo and the dataset is not present, they need to copy it into that folder before running dataset analysis or model training.

You can inspect the dataset with:

```bash
backend/api/.venv/bin/python backend/scripts/generate_ksl_cleanup_reports.py
backend/api/.venv/bin/python backend/scripts/build_cleanup_decisions_template.py
backend/api/.venv/bin/python backend/scripts/prefill_cleanup_decisions.py
backend/api/.venv/bin/python backend/scripts/apply_cleanup_decisions_to_manifest.py
backend/api/.venv/bin/python backend/scripts/build_ksl_lesson_catalog.py
```

That workflow creates review files in:

```text
backend/reports/ksl_cleanup/
```

Use `cleanup_decisions.csv` as the manual sheet for `keep`, `rename`, `merge`, or `drop` decisions before changing anything in the raw dataset.
After that, use `backend/api/app/data/ksl_lesson_catalog.json` as the backend lesson source of truth.

## Current dataset snapshot

From the current local dataset audit:

- `2` batches
- `40` signer folders
- `727` unique labels
- `1495` landmark samples
- median samples per label: `1`
- labels with only `1` sample: `472`
- labels with fewer than `3` samples: `598`

This means the current dataset is better suited to a curated vocabulary tutor first, rather than a broad sentence-level KSL translation model.

## Common commands

Start backend from inside the backend folder:

```bash
cd backend/api
source .venv/bin/activate
bash start-dev.sh
```

Reinstall backend dependencies:

```bash
cd backend/api
source .venv/bin/activate
pip install -r requirements-dev.txt
```

Run the dataset audit:

```bash
backend/api/.venv/bin/python backend/scripts/generate_ksl_cleanup_reports.py
backend/api/.venv/bin/python backend/scripts/build_cleanup_decisions_template.py
backend/api/.venv/bin/python backend/scripts/prefill_cleanup_decisions.py
backend/api/.venv/bin/python backend/scripts/apply_cleanup_decisions_to_manifest.py
backend/api/.venv/bin/python backend/scripts/build_ksl_lesson_catalog.py
```

Test speech-to-text with faster-whisper after installing the backend dependencies:

```bash
bash warmup-stt.sh
curl -X POST http://127.0.0.1:8000/api/v1/speech-to-text \
  -F "audio=@/absolute/path/to/sample.wav" \
  -F "include_ksl=true"
```

Test text-to-speech with Kokoro after installing the backend dependencies:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/text-to-speech \
  -H "Content-Type: application/json" \
  -d '{
    "text": "I want food",
    "include_ksl": true
  }'
```

The current backend is split like this:

- `text-to-speech` is local and free with Kokoro
- `speech-to-text` is local with faster-whisper
- `sign-to-text` is dataset-backed from cleaned `.npy` landmarks
- `sign-sequence-to-text` combines multiple recognized signs into one sequence
- `sign-to-text-upload` accepts uploaded `.npy` landmarks and optional sign videos
- `sign-to-text` can now optionally synthesize recognized signs back to speech

The current sign recognizer is intentionally narrowed to a bundled `v1` sign list in `backend/api/app/data/ksl_sign_v1_labels.json` and only keeps labels with at least `5` cleaned samples by default.

On the first speech-to-text run, `faster-whisper` downloads its model from Hugging Face. Run `bash warmup-stt.sh` once while you are online so later requests can use the local cache.

If a previous `pip install -r requirements-dev.txt` failed during the Kokoro setup, pull the latest backend changes and run the install again before testing TTS.

If you previously created `.venv` with Python `3.13`, rebuild it from `backend/api` with:

```bash
bash setup-venv.sh
```

Test sign-to-text against a cleaned landmark file:

```bash
backend/api/.venv/bin/python backend/scripts/train_sign_classifier.py
curl -X POST http://127.0.0.1:8000/api/v1/sign-to-text \
  -H "Content-Type: application/json" \
  -d '{
    "landmark_path": "KSL-Dataset/Pose Data/Batch 2/65/Extract/Landmarks/ME.npy",
    "top_k": 3,
    "include_speech": true
  }'
```

To save the returned sign speech audio directly to a local WAV file:

```bash
cd backend/api
bash test-sign-speech.sh "KSL-Dataset/Pose Data/Batch 2/65/Extract/Landmarks/ME.npy" ./sign-me.wav 3
```

To test the new upload endpoint with the same landmark file:

```bash
cd backend/api
bash test-sign-upload.sh "KSL-Dataset/Pose Data/Batch 2/65/Extract/Landmarks/ME.npy" false
```

To test multiple signs as a single backend sequence:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/sign-sequence-to-text \
  -H "Content-Type: application/json" \
  -d '{
    "items": [
      {"landmark_path": "KSL-Dataset/Pose Data/Batch 2/65/Extract/Landmarks/ME.npy"},
      {"landmark_path": "KSL-Dataset/Pose Data/Batch 2/76/Extract/Landmarks/WANT.npy"},
      {"landmark_path": "KSL-Dataset/Pose Data/Batch 2/162/Extract/Landmarks/FOOD.npy"}
    ],
    "include_ksl": true,
    "include_speech": true
  }'
```

If you want real uploaded sign video recognition too, install the optional backend extras from `backend/api`:

```bash
pip install -r requirements-sign-video.txt
bash download-sign-video-model.sh
```

On macOS, keep `.npy` landmark upload as the stable local path for now. Raw MediaPipe video extraction is more reliable in Linux-based environments.

## Troubleshooting

### `ModuleNotFoundError: No module named 'app'`

This happens when you run the wrong import path for your current working directory.

From `backend/api`, do not run:

```bash
uvicorn backend.api.app.main:app --reload
```

Use this instead:

```bash
bash start-dev.sh
```

### `ModuleNotFoundError: No module named 'backend'`

This happens when you are inside `backend/api` but you try to run:

```bash
uvicorn backend.api.app.main:app --reload
```

From inside `backend/api`, use:

```bash
bash start-dev.sh
```

### `ModuleNotFoundError: No module named 'pydantic_settings'`

This usually means one of these:

- the backend `.venv` is not activated
- dependencies were installed into a different Python environment
- Uvicorn was started while packages were still installing

Fix it with:

```bash
cd backend/api
source .venv/bin/activate
pip install -r requirements-dev.txt
bash start-dev.sh
```

### Docs page does not load

Check that:

- the virtual environment is activated
- backend dependencies were installed with `pip install -r requirements-dev.txt`
- you copied `.env.example` to `.env` inside `backend/api`

### Uvicorn keeps reloading over and over

This usually happens if your local `.venv` is inside the watched folder and you start Uvicorn manually with a broad reload target.

Use:

```bash
bash start-dev.sh
```
