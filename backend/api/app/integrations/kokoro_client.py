from __future__ import annotations

from functools import lru_cache

from ..core.config import settings


@lru_cache(maxsize=1)
def get_kokoro_pipeline():
    try:
        from kokoro import KPipeline
    except (ModuleNotFoundError, ImportError) as exc:
        raise RuntimeError(
            "The Kokoro package is missing or incompatible in this backend environment. "
            "Activate backend/api/.venv and run `pip install -r requirements-dev.txt`."
        ) from exc

    try:
        return KPipeline(lang_code=settings.kokoro_lang_code)
    except Exception as exc:
        raise RuntimeError(
            "Failed to initialize Kokoro. If you are on macOS, install `espeak-ng` "
            "with `brew install espeak-ng`, then restart the backend."
        ) from exc
