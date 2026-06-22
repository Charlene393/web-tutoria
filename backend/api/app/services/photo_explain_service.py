from __future__ import annotations

import re
from pathlib import Path

from ..schemas.requests import (
    PhotoExplainRequest,
    PhotoExplainUploadRequest,
    TextToKslRequest,
    TextToSpeechRequest,
)
from ..schemas.responses import PhotoExplainResponse, TextToSpeechResponse
from .speech_service import synthesize_speech
from .text_to_ksl_service import map_text_to_ksl

_OBJECT_EXPLANATIONS = {
    "ALSO": "This means something is added too. You use it when you want to include another idea.",
    "BOOK": "A book is something we read to learn stories, facts, and school work.",
    "BOY": "A boy is a male child.",
    "CAR": "A car is a road vehicle people use to travel from one place to another.",
    "CHURCH": "A church is a place where people gather for Christian worship and prayer.",
    "FOOD": "Food is what people eat to get energy and stay healthy.",
    "GIRL": "A girl is a female child.",
    "SCHOOL": "A school is a place where students go to learn.",
    "WANT": "Want means you would like to have or do something.",
    "WATER": "Water is the liquid people drink and use every day.",
}


def explain_photo(request: PhotoExplainRequest) -> PhotoExplainResponse:
    object_name = _resolve_object_name(
        explicit_object_name=request.object_name,
        prompt=request.prompt,
        filename=None,
    )
    return _build_photo_response(
        object_name=object_name,
        prompt=request.prompt,
        include_ksl=request.include_ksl,
        include_speech=request.include_speech,
        voice_id=request.voice_id,
        output_format=request.output_format,
        session_id=request.session_id,
        source_kind="json_request",
        source_image_filename=None,
    )


def explain_uploaded_photo(request: PhotoExplainUploadRequest) -> PhotoExplainResponse:
    if not request.image_bytes:
        raise ValueError("Uploaded image file is empty.")

    object_name = _resolve_object_name(
        explicit_object_name=request.object_name,
        prompt=request.prompt,
        filename=request.filename,
    )
    return _build_photo_response(
        object_name=object_name,
        prompt=request.prompt,
        include_ksl=request.include_ksl,
        include_speech=request.include_speech,
        voice_id=request.voice_id,
        output_format=request.output_format,
        session_id=request.session_id,
        source_kind="uploaded_image",
        source_image_filename=request.filename,
    )


def _build_photo_response(
    *,
    object_name: str,
    prompt: str | None,
    include_ksl: bool,
    include_speech: bool,
    voice_id: str | None,
    output_format: str | None,
    session_id: str | None,
    source_kind: str,
    source_image_filename: str | None,
) -> PhotoExplainResponse:
    normalized_object_name = _normalize_phrase(object_name)
    text_to_ksl = (
        map_text_to_ksl(TextToKslRequest(text=object_name))
        if include_ksl
        else None
    )
    suggested_sign = text_to_ksl.gloss[0] if text_to_ksl and text_to_ksl.gloss else None
    explanation = _build_explanation(
        object_name=object_name,
        prompt=prompt,
        suggested_sign=suggested_sign,
    )
    speech = _maybe_synthesize_explanation_speech(
        explanation,
        include_speech=include_speech,
        voice_id=voice_id,
        output_format=output_format,
        session_id=session_id,
    )

    if text_to_ksl is None or text_to_ksl.status == "ok":
        status = "ok"
    else:
        status = "partial"

    return PhotoExplainResponse(
        object_name=object_name,
        normalized_object_name=normalized_object_name,
        explanation=explanation,
        suggested_sign=suggested_sign,
        provider="filename_or_prompt_v1",
        source_kind=source_kind,
        source_image_filename=source_image_filename,
        text_to_ksl=text_to_ksl,
        speech=speech,
        status=status,
    )


def _resolve_object_name(
    *,
    explicit_object_name: str | None,
    prompt: str | None,
    filename: str | None,
) -> str:
    if explicit_object_name and explicit_object_name.strip():
        return explicit_object_name.strip()

    filename_candidate = _candidate_from_filename(filename)
    if filename_candidate:
        return filename_candidate

    prompt_candidate = _candidate_from_prompt(prompt)
    if prompt_candidate:
        return prompt_candidate

    raise ValueError(
        "Unable to infer the object name. Pass `object_name`, or upload an image with a useful "
        "filename such as `car.jpg` or `church.png`."
    )


def _candidate_from_filename(filename: str | None) -> str | None:
    if not filename:
        return None

    stem = Path(filename).stem
    cleaned = re.sub(r"[_\-]+", " ", stem)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or None


def _candidate_from_prompt(prompt: str | None) -> str | None:
    if not prompt or not prompt.strip():
        return None

    normalized = _normalize_phrase(prompt)
    if not normalized:
        return None

    return normalized


def _build_explanation(
    *,
    object_name: str,
    prompt: str | None,
    suggested_sign: str | None,
) -> str:
    normalized_object_name = _normalize_phrase(object_name)
    lookup_key = normalized_object_name.upper()
    base_explanation = _OBJECT_EXPLANATIONS.get(lookup_key)
    if base_explanation is None:
        display_name = object_name.strip()
        base_explanation = (
            f"This looks like {display_name}. "
            f"It is something a student can learn to name, describe, and sign."
        )

    if suggested_sign:
        return f"{base_explanation} The matching KSL lesson sign is {suggested_sign}."

    if prompt and prompt.strip():
        return f"{base_explanation} We may need more KSL glossary coverage for this item."

    return base_explanation


def _maybe_synthesize_explanation_speech(
    text: str,
    *,
    include_speech: bool,
    voice_id: str | None,
    output_format: str | None,
    session_id: str | None,
) -> TextToSpeechResponse | None:
    if not include_speech:
        return None

    return synthesize_speech(
        TextToSpeechRequest(
            text=text,
            voice_id=voice_id,
            output_format=output_format,
            include_ksl=False,
            session_id=session_id,
        )
    )


def _normalize_phrase(value: str) -> str:
    normalized = value.lower()
    normalized = re.sub(r"[^a-z0-9'\s]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized
