from __future__ import annotations

from functools import lru_cache

from huggingface_hub.errors import LocalEntryNotFoundError

from ..core.config import settings


@lru_cache(maxsize=1)
def get_faster_whisper_model():
    try:
        from faster_whisper import WhisperModel
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "The faster-whisper package is not installed in this backend environment. "
            "Activate backend/api/.venv and run `pip install -r requirements-dev.txt`."
        ) from exc

    try:
        return WhisperModel(
            settings.faster_whisper_model_size,
            device=settings.faster_whisper_device,
            compute_type=settings.faster_whisper_compute_type,
        )
    except LocalEntryNotFoundError as exc:
        raise RuntimeError(
            "faster-whisper could not find the local model files yet. "
            "On the first run, connect to the internet and run `bash warmup-stt.sh` "
            "from backend/api so the model can download from Hugging Face."
        ) from exc
    except Exception as exc:
        raise RuntimeError(
            f"Failed to initialize faster-whisper: {exc}"
        ) from exc
