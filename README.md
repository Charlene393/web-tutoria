# Web Tutoria

Web Tutoria is an AI learning system for Kenyan Sign Language (KSL).

The project is being built around three core flows:

- speech -> text -> KSL lesson or sign playback
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

- Python `3.11+`
- Git

Frontend tooling can be added later when the web app is bootstrapped.

## Clone and setup

If you only want the backend running, use this full copy-paste flow:

```bash
git clone <your-repo-url>
cd web-tutoria
cd backend/api
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements-dev.txt
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
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
```

### 3. Install backend dependencies

```bash
pip install -r requirements-dev.txt
```

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
```

That workflow creates review files in:

```text
backend/reports/ksl_cleanup/
```

Use `cleanup_decisions.csv` as the manual sheet for `keep`, `rename`, `merge`, or `drop` decisions before changing anything in the raw dataset.

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
```

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
