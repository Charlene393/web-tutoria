from starlette.testclient import TestClient

from app.main import app
from app.schemas.responses import TextToKslResponse, TextToSpeechResponse
from app.services import photo_explain_service

client = TestClient(app)


def test_photo_explain_json_uses_object_name_and_returns_ksl(monkeypatch) -> None:
    def fake_map_text_to_ksl(request):
        assert request.text == "car"
        return TextToKslResponse(
            original_text="car",
            normalized_text="car",
            gloss=["CAR"],
            matched_terms=["car"],
            unmatched_terms=[],
            supported=True,
            dataset_backed=True,
            dataset_label_counts={"CAR": 5},
            lesson_assets=[],
            lesson_asset_id="dataset-sequence:car",
            catalog_backed=True,
            catalog_name="test_catalog",
            catalog_generated_at="2026-06-22T00:00:00+00:00",
            status="ok",
        )

    monkeypatch.setattr(photo_explain_service, "map_text_to_ksl", fake_map_text_to_ksl)

    response = client.post(
        "/api/v1/photo-explain",
        json={
            "object_name": "car",
            "include_ksl": True,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["object_name"] == "car"
    assert body["normalized_object_name"] == "car"
    assert body["suggested_sign"] == "CAR"
    assert body["provider"] == "filename_or_prompt_v1"
    assert body["source_kind"] == "json_request"
    assert body["text_to_ksl"]["gloss"] == ["CAR"]
    assert body["status"] == "ok"


def test_photo_explain_upload_uses_filename_when_object_name_missing(monkeypatch) -> None:
    def fake_map_text_to_ksl(request):
        assert request.text == "church"
        return TextToKslResponse(
            original_text="church",
            normalized_text="church",
            gloss=["CHURCH"],
            matched_terms=["church"],
            unmatched_terms=[],
            supported=True,
            dataset_backed=True,
            dataset_label_counts={"CHURCH": 2},
            lesson_assets=[],
            lesson_asset_id="dataset-sequence:church",
            catalog_backed=True,
            catalog_name="test_catalog",
            catalog_generated_at="2026-06-22T00:00:00+00:00",
            status="ok",
        )

    def fake_synthesize(request):
        assert "CHURCH" in request.text
        return TextToSpeechResponse(
            text=request.text,
            audio_base64="ZmFrZS13YXY=",
            audio_size_bytes=8,
            content_type="audio/wav",
            file_extension="wav",
            provider="kokoro",
            model_id="Kokoro-82M",
            voice_id="af_heart",
            output_format="wav_24000",
            text_to_ksl=None,
            status="ok",
        )

    monkeypatch.setattr(photo_explain_service, "map_text_to_ksl", fake_map_text_to_ksl)
    monkeypatch.setattr(photo_explain_service, "synthesize_speech", fake_synthesize)

    response = client.post(
        "/api/v1/photo-explain-upload",
        files={
            "image": ("church.png", b"fake-image-bytes", "image/png"),
        },
        data={
            "include_speech": "true",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["object_name"] == "church"
    assert body["source_kind"] == "uploaded_image"
    assert body["source_image_filename"] == "church.png"
    assert body["suggested_sign"] == "CHURCH"
    assert body["speech"]["provider"] == "kokoro"


def test_photo_explain_upload_returns_400_when_object_cannot_be_inferred() -> None:
    response = client.post(
        "/api/v1/photo-explain-upload",
        files={
            "image": ("___---.png", b"fake-image-bytes", "image/png"),
        },
        data={
            "prompt": "",
        },
    )

    assert response.status_code == 400
    assert "Unable to infer the object name" in response.json()["detail"]
