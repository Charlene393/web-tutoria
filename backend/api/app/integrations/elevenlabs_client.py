from ..core.config import settings


def get_elevenlabs_client():
    if not settings.elevenlabs_api_key:
        raise RuntimeError(
            "ELEVENLABS_API_KEY is not set. Add it to backend/api/.env before using speech features."
        )

    try:
        from elevenlabs.client import ElevenLabs
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "The elevenlabs package is not installed in this backend environment. "
            "Activate backend/api/.venv and run `pip install -r requirements-dev.txt`."
        ) from exc

    return ElevenLabs(api_key=settings.elevenlabs_api_key)
