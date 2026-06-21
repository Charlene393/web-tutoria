from starlette.testclient import TestClient

from app.main import app
from app.services import speech_service

client = TestClient(app)


def test_speech_to_text_returns_transcript_and_ksl_mapping(monkeypatch) -> None:
    def fake_transcribe(request):
        assert request.filename == "sample.wav"
        assert request.include_ksl is True
        assert request.audio_bytes == b"fake-audio"
        return speech_service.LocalTranscriptionResult(
            transcript="I want food",
            detected_language="en",
        )

    monkeypatch.setattr(speech_service, "_transcribe_with_faster_whisper", fake_transcribe)

    response = client.post(
        "/api/v1/speech-to-text",
        files={"audio": ("sample.wav", b"fake-audio", "audio/wav")},
        data={"include_ksl": "true"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["transcript"] == "I want food"
    assert body["provider"] == "faster_whisper"
    assert body["model_id"] == "small"
    assert body["detected_language"] == "en"
    assert body["text_to_ksl"]["gloss"] == ["ME", "WANT", "FOOD"]
    assert body["text_to_ksl"]["catalog_backed"] is True
    assert body["text_to_ksl"]["lesson_assets"][0]["source"] == "cleaned_lesson_catalog"
    assert body["status"] == "ok"


def test_speech_to_text_can_skip_ksl_mapping(monkeypatch) -> None:
    monkeypatch.setattr(
        speech_service,
        "_transcribe_with_faster_whisper",
        lambda request: speech_service.LocalTranscriptionResult(transcript="Hello"),
    )

    response = client.post(
        "/api/v1/speech-to-text",
        files={"audio": ("hello.wav", b"fake-audio", "audio/wav")},
        data={"include_ksl": "false"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["transcript"] == "Hello"
    assert body["text_to_ksl"] is None
    assert body["status"] == "ok"


def test_speech_to_text_returns_503_when_provider_fails(monkeypatch) -> None:
    def fake_transcribe(_request):
        raise RuntimeError("faster-whisper model download failed.")

    monkeypatch.setattr(speech_service, "_transcribe_with_faster_whisper", fake_transcribe)

    response = client.post(
        "/api/v1/speech-to-text",
        files={"audio": ("sample.wav", b"fake-audio", "audio/wav")},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "faster-whisper model download failed."


def test_speech_to_text_returns_400_for_empty_upload(monkeypatch) -> None:
    response = client.post(
        "/api/v1/speech-to-text",
        files={"audio": ("empty.wav", b"", "audio/wav")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Uploaded audio file is empty."
