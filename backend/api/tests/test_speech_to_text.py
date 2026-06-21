from starlette.testclient import TestClient

from app.main import app
from app.services import speech_service

client = TestClient(app)


class FakeTranscriptionResult:
    def __init__(self, text: str, confidence: float = 0.98, language_code: str = "en") -> None:
        self.text = text
        self.confidence = confidence
        self.language_code = language_code


def test_speech_to_text_returns_transcript_and_ksl_mapping(monkeypatch) -> None:
    def fake_transcribe(request):
        assert request.filename == "sample.wav"
        assert request.include_ksl is True
        assert request.audio_bytes == b"fake-audio"
        return FakeTranscriptionResult(text="I want food")

    monkeypatch.setattr(speech_service, "_transcribe_with_elevenlabs", fake_transcribe)

    response = client.post(
        "/api/v1/speech-to-text",
        files={"audio": ("sample.wav", b"fake-audio", "audio/wav")},
        data={"include_ksl": "true"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["transcript"] == "I want food"
    assert body["provider"] == "elevenlabs"
    assert body["model_id"] == "scribe_v2"
    assert body["detected_language"] == "en"
    assert body["text_to_ksl"]["gloss"] == ["ME", "WANT", "FOOD"]
    assert body["text_to_ksl"]["catalog_backed"] is True
    assert body["text_to_ksl"]["lesson_assets"][0]["source"] == "cleaned_lesson_catalog"
    assert body["status"] == "ok"


def test_speech_to_text_can_skip_ksl_mapping(monkeypatch) -> None:
    monkeypatch.setattr(
        speech_service,
        "_transcribe_with_elevenlabs",
        lambda request: FakeTranscriptionResult(text="Hello"),
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
        raise RuntimeError("ELEVENLABS_API_KEY is not set.")

    monkeypatch.setattr(speech_service, "_transcribe_with_elevenlabs", fake_transcribe)

    response = client.post(
        "/api/v1/speech-to-text",
        files={"audio": ("sample.wav", b"fake-audio", "audio/wav")},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "ELEVENLABS_API_KEY is not set."


def test_speech_to_text_returns_400_for_empty_upload(monkeypatch) -> None:
    response = client.post(
        "/api/v1/speech-to-text",
        files={"audio": ("empty.wav", b"", "audio/wav")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Uploaded audio file is empty."
