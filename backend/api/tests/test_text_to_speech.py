import base64

from starlette.testclient import TestClient

from app.main import app
from app.services import speech_service

client = TestClient(app)


def test_text_to_speech_returns_audio_and_ksl_mapping(monkeypatch) -> None:
    monkeypatch.setattr(speech_service.settings, "kokoro_voice", "af_heart")

    def fake_synthesize(request, *, voice_id, speed):
        assert request.text == "I want food"
        assert request.include_ksl is True
        assert voice_id == "af_heart"
        assert speed == 1.0
        return b"fake-wav-bytes"

    monkeypatch.setattr(speech_service, "_synthesize_with_kokoro", fake_synthesize)

    response = client.post(
        "/api/v1/text-to-speech",
        json={"text": "I want food", "include_ksl": True},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["text"] == "I want food"
    assert base64.b64decode(body["audio_base64"]) == b"fake-wav-bytes"
    assert body["audio_size_bytes"] == len(b"fake-wav-bytes")
    assert body["content_type"] == "audio/wav"
    assert body["file_extension"] == "wav"
    assert body["provider"] == "kokoro"
    assert body["model_id"] == "Kokoro-82M"
    assert body["voice_id"] == "af_heart"
    assert body["output_format"] == "wav_24000"
    assert body["text_to_ksl"]["gloss"] == ["ME", "WANT", "FOOD"]
    assert body["text_to_ksl"]["catalog_backed"] is True
    assert body["status"] == "ok"


def test_text_to_speech_supports_custom_voice_and_output_format(monkeypatch) -> None:
    monkeypatch.setattr(speech_service.settings, "kokoro_voice", "af_heart")

    def fake_synthesize(_request, *, voice_id, speed):
        assert voice_id == "bf_emma"
        assert speed == 1.0
        return b"RIFF-fake-wav"

    monkeypatch.setattr(speech_service, "_synthesize_with_kokoro", fake_synthesize)

    response = client.post(
        "/api/v1/text-to-speech",
        json={
            "text": "Hello learner",
            "voice_id": "bf_emma",
            "output_format": "wav",
            "include_ksl": False,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["voice_id"] == "bf_emma"
    assert body["output_format"] == "wav_24000"
    assert body["content_type"] == "audio/wav"
    assert body["file_extension"] == "wav"
    assert body["text_to_ksl"] is None
    assert body["status"] == "ok"


def test_text_to_speech_returns_503_when_voice_is_missing(monkeypatch) -> None:
    monkeypatch.setattr(speech_service.settings, "kokoro_voice", "")

    response = client.post(
        "/api/v1/text-to-speech",
        json={"text": "Hello learner"},
    )

    assert response.status_code == 503
    assert "KOKORO_VOICE is not set" in response.json()["detail"]


def test_text_to_speech_returns_503_when_provider_fails(monkeypatch) -> None:
    monkeypatch.setattr(speech_service.settings, "kokoro_voice", "af_heart")

    def fake_synthesize(_request, *, voice_id, speed):
        raise RuntimeError("Kokoro synthesis failed for voice af_heart: provider down")

    monkeypatch.setattr(speech_service, "_synthesize_with_kokoro", fake_synthesize)

    response = client.post(
        "/api/v1/text-to-speech",
        json={"text": "Hello learner"},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "Kokoro synthesis failed for voice af_heart: provider down"


def test_text_to_speech_returns_400_for_invalid_output_format() -> None:
    response = client.post(
        "/api/v1/text-to-speech",
        json={"text": "Hello learner", "output_format": "mp3"},
    )

    assert response.status_code == 400
    assert "Kokoro currently supports only WAV output" in response.json()["detail"]


def test_text_to_speech_returns_400_for_empty_text() -> None:
    response = client.post(
        "/api/v1/text-to-speech",
        json={"text": "   "},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Text for synthesis cannot be empty."
