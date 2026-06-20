from elevenlabs.client import ElevenLabs

from ..core.config import settings


def get_elevenlabs_client() -> ElevenLabs:
    if not settings.elevenlabs_api_key:
        raise RuntimeError(
            "ELEVENLABS_API_KEY is not set. Add it to backend/api/.env before using speech features."
        )

    return ElevenLabs(api_key=settings.elevenlabs_api_key)
