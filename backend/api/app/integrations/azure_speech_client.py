from __future__ import annotations

from html import escape

import httpx

from ..core.config import settings


def _azure_tts_endpoint() -> str:
    if not settings.azure_speech_region:
        raise RuntimeError(
            "AZURE_SPEECH_REGION is not set. Add it to backend/api/.env before using text-to-speech."
        )

    return (
        f"https://{settings.azure_speech_region}.tts.speech.microsoft.com/"
        "cognitiveservices/v1"
    )


def _build_ssml(text: str, voice_name: str) -> str:
    voice_parts = voice_name.split("-")
    locale = "-".join(voice_parts[:2]) if len(voice_parts) >= 2 else "en-US"
    return (
        f"<speak version='1.0' xml:lang='{escape(locale, quote=True)}'>"
        f"<voice name='{escape(voice_name, quote=True)}'>"
        f"{escape(text)}"
        "</voice>"
        "</speak>"
    )


def synthesize_text_with_azure_speech(
    text: str,
    *,
    voice_name: str,
    output_format: str,
) -> bytes:
    if not settings.azure_speech_key:
        raise RuntimeError(
            "AZURE_SPEECH_KEY is not set. Add it to backend/api/.env before using text-to-speech."
        )

    headers = {
        "Ocp-Apim-Subscription-Key": settings.azure_speech_key,
        "Content-Type": "application/ssml+xml",
        "X-Microsoft-OutputFormat": output_format,
        "User-Agent": settings.app_name,
    }

    ssml = _build_ssml(text, voice_name)

    try:
        response = httpx.post(
            _azure_tts_endpoint(),
            headers=headers,
            content=ssml.encode("utf-8"),
            timeout=60.0,
        )
    except httpx.HTTPError as exc:
        raise RuntimeError(f"Azure Speech synthesis request failed: {exc}") from exc

    if response.status_code >= 400:
        detail = response.text.strip() or "<empty response body>"
        raise RuntimeError(
            f"Azure Speech synthesis failed with status {response.status_code}: {detail}"
        )

    if not response.content:
        raise RuntimeError("Azure Speech returned empty audio.")

    return response.content
