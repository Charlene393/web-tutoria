from __future__ import annotations

import base64
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from ..core.config import settings
from ..integrations.faster_whisper_client import get_faster_whisper_model
from ..integrations.kokoro_client import get_kokoro_pipeline
from ..schemas.requests import (
    SpeechToTextRequest,
    TextToKslRequest,
    TextToSpeechRequest,
)
from ..schemas.responses import SpeechToTextResponse, TextToSpeechResponse
from .text_to_ksl_service import map_text_to_ksl

_AUDIO_FORMAT_METADATA = {
    "wav": ("audio/wav", "wav"),
}


@dataclass
class LocalTranscriptionResult:
    transcript: str
    detected_language: str | None = None
    language_probability: float | None = None


def _pick_value(result: Any, *names: str) -> Any:
    for name in names:
        if isinstance(result, dict) and name in result:
            return result[name]
        value = getattr(result, name, None)
        if value is not None:
            return value
    return None


def _audio_metadata_for_output_format(output_format: str) -> tuple[str, str]:
    prefix = output_format.split("_", 1)[0].lower()
    return _AUDIO_FORMAT_METADATA.get(
        prefix,
        ("application/octet-stream", prefix or "bin"),
    )


def _resolve_kokoro_voice(request: TextToSpeechRequest) -> str:
    voice_id = request.voice_id or settings.kokoro_voice
    if voice_id:
        return voice_id

    raise RuntimeError(
        "KOKORO_VOICE is not set. Add it to backend/api/.env or pass "
        "`voice_id` in the text-to-speech request body."
    )


def _normalize_kokoro_output_format(output_format: str | None) -> str:
    normalized = (output_format or "wav_24000").strip().lower()
    if normalized in {"wav", "wav_24000"}:
        return "wav_24000"
    raise ValueError(
        "Kokoro currently supports only WAV output in this backend. "
        "Use `wav` or omit `output_format`."
    )


def _get_kokoro_audio_dependencies() -> tuple[Any, Any]:
    try:
        import numpy as np
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "The numpy package is not installed in this backend environment. "
            "Activate backend/api/.venv and run `pip install -r requirements-dev.txt`."
        ) from exc

    try:
        import soundfile as sf
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "The soundfile package is not installed in this backend environment. "
            "Activate backend/api/.venv and run `pip install -r requirements-dev.txt`."
        ) from exc

    return np, sf


def _combine_audio_chunks(audio_chunks: list[Any], sample_rate: int, np: Any) -> Any:
    if len(audio_chunks) == 1:
        return audio_chunks[0]

    silence = np.zeros(int(sample_rate * 0.15), dtype=np.float32)
    combined: list[Any] = []

    for index, chunk in enumerate(audio_chunks):
        combined.append(chunk.astype(np.float32, copy=False))
        if index < len(audio_chunks) - 1:
            combined.append(silence)

    return np.concatenate(combined)


def _synthesize_with_kokoro(
    request: TextToSpeechRequest,
    *,
    voice_id: str,
    speed: float,
) -> bytes:
    np, sf = _get_kokoro_audio_dependencies()
    pipeline = get_kokoro_pipeline()
    segments: list[Any] = []
    try:
        generator = pipeline(
            request.text.strip(),
            voice=voice_id,
            speed=speed,
            split_pattern=r"\n+",
        )
        for _graphemes, _phonemes, audio in generator:
            if audio is not None and len(audio) > 0:
                segments.append(np.asarray(audio, dtype=np.float32))
    except Exception as exc:
        raise RuntimeError(
            f"Kokoro synthesis failed for voice {voice_id}: {exc}"
        ) from exc

    if not segments:
        return b""

    merged_audio = _combine_audio_chunks(segments, settings.kokoro_sample_rate, np)
    buffer = BytesIO()
    sf.write(buffer, merged_audio, settings.kokoro_sample_rate, format="WAV")
    return buffer.getvalue()


def _transcribe_with_faster_whisper(request: SpeechToTextRequest) -> LocalTranscriptionResult:
    model = get_faster_whisper_model()
    suffix = Path(request.filename or "audio.wav").suffix or ".wav"
    temp_path: str | None = None
    try:
        with NamedTemporaryFile(suffix=suffix, delete=False) as temp_file:
            temp_file.write(request.audio_bytes)
            temp_path = temp_file.name

        transcribe_kwargs: dict[str, Any] = {
            "beam_size": settings.faster_whisper_beam_size,
            "vad_filter": settings.faster_whisper_vad_filter,
        }
        if settings.faster_whisper_language:
            transcribe_kwargs["language"] = settings.faster_whisper_language

        segments, info = model.transcribe(temp_path, **transcribe_kwargs)
        segments = list(segments)
        transcript = " ".join(
            segment.text.strip()
            for segment in segments
            if getattr(segment, "text", "").strip()
        ).strip()

        return LocalTranscriptionResult(
            transcript=transcript,
            detected_language=getattr(info, "language", None),
            language_probability=getattr(info, "language_probability", None),
        )
    except Exception as exc:
        filename = Path(request.filename or "audio.wav").name
        raise RuntimeError(
            f"faster-whisper transcription failed for {filename}: {exc}"
        ) from exc
    finally:
        if temp_path is not None:
            Path(temp_path).unlink(missing_ok=True)


def synthesize_speech(request: TextToSpeechRequest) -> TextToSpeechResponse:
    text = request.text.strip()
    if not text:
        raise ValueError("Text for synthesis cannot be empty.")

    voice_id = _resolve_kokoro_voice(request)
    output_format = _normalize_kokoro_output_format(request.output_format)
    audio_bytes = _synthesize_with_kokoro(
        request,
        voice_id=voice_id,
        speed=settings.kokoro_speed,
    )

    if not audio_bytes:
        raise RuntimeError("Kokoro returned empty audio.")

    content_type, file_extension = _audio_metadata_for_output_format(output_format)
    text_to_ksl = (
        map_text_to_ksl(TextToKslRequest(text=text))
        if request.include_ksl
        else None
    )

    if text_to_ksl is None or text_to_ksl.status == "ok":
        status = "ok"
    else:
        status = "partial"

    return TextToSpeechResponse(
        text=text,
        audio_base64=base64.b64encode(audio_bytes).decode("utf-8"),
        audio_size_bytes=len(audio_bytes),
        content_type=content_type,
        file_extension=file_extension,
        provider="kokoro",
        model_id=settings.kokoro_model_id,
        voice_id=voice_id,
        output_format=output_format,
        text_to_ksl=text_to_ksl,
        status=status,
    )


def transcribe_speech(request: SpeechToTextRequest) -> SpeechToTextResponse:
    if not request.audio_bytes:
        raise ValueError("Uploaded audio file is empty.")

    result = _transcribe_with_faster_whisper(request)

    transcript = _pick_value(result, "transcript", "text")
    if not transcript or not str(transcript).strip():
        raise RuntimeError("faster-whisper returned an empty transcript.")

    detected_language = _pick_value(
        result,
        "language_code",
        "language",
        "detected_language",
    )
    text_to_ksl = (
        map_text_to_ksl(TextToKslRequest(text=str(transcript)))
        if request.include_ksl
        else None
    )

    if text_to_ksl is None or text_to_ksl.status == "ok":
        status = "ok"
    else:
        status = "partial"

    return SpeechToTextResponse(
        transcript=str(transcript),
        confidence=None,
        provider="faster_whisper",
        model_id=settings.faster_whisper_model_size,
        detected_language=str(detected_language) if detected_language is not None else None,
        text_to_ksl=text_to_ksl,
        status=status,
    )
