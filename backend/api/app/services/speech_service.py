from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any

from elevenlabs.core.api_error import ApiError

from ..core.config import settings
from ..integrations.elevenlabs_client import get_elevenlabs_client
from ..schemas.requests import SpeechToTextRequest, TextToKslRequest
from ..schemas.responses import SpeechToTextResponse
from .text_to_ksl_service import map_text_to_ksl


def _pick_value(result: Any, *names: str) -> Any:
    for name in names:
        if isinstance(result, dict) and name in result:
            return result[name]
        value = getattr(result, name, None)
        if value is not None:
            return value
    return None


def _transcribe_with_elevenlabs(request: SpeechToTextRequest) -> Any:
    client = get_elevenlabs_client()
    speech_to_text = getattr(client, "speech_to_text", None)
    convert = getattr(speech_to_text, "convert", None)

    if convert is None:
        raise RuntimeError(
            "Installed ElevenLabs client does not expose speech_to_text.convert. "
            "Upgrade dependencies with `pip install -r requirements-dev.txt`."
        )

    audio_stream = BytesIO(request.audio_bytes)
    audio_stream.name = request.filename or "audio.wav"

    try:
        return convert(
            file=audio_stream,
            model_id=settings.elevenlabs_stt_model_id,
            file_format="other",
        )
    except ApiError as exc:
        detail = exc.body if isinstance(exc.body, str) else repr(exc.body)
        raise RuntimeError(
            f"ElevenLabs transcription failed with status {exc.status_code}: {detail}"
        ) from exc
    except Exception as exc:
        filename = Path(request.filename or "audio.wav").name
        raise RuntimeError(
            f"ElevenLabs transcription failed for {filename}: {exc}"
        ) from exc


def transcribe_speech(request: SpeechToTextRequest) -> SpeechToTextResponse:
    if not request.audio_bytes:
        raise ValueError("Uploaded audio file is empty.")

    result = _transcribe_with_elevenlabs(request)

    transcript = _pick_value(result, "text", "transcript")
    if not transcript or not str(transcript).strip():
        raise RuntimeError("ElevenLabs returned an empty transcript.")

    confidence = _pick_value(result, "confidence")
    detected_language = _pick_value(result, "language_code", "language", "detected_language")
    text_to_ksl = map_text_to_ksl(TextToKslRequest(text=str(transcript))) if request.include_ksl else None

    if text_to_ksl is None or text_to_ksl.status == "ok":
        status = "ok"
    else:
        status = "partial"

    return SpeechToTextResponse(
        transcript=str(transcript),
        confidence=float(confidence) if confidence is not None else None,
        provider="elevenlabs",
        model_id=settings.elevenlabs_stt_model_id,
        detected_language=str(detected_language) if detected_language is not None else None,
        text_to_ksl=text_to_ksl,
        status=status,
    )
