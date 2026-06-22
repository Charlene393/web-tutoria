import csv
from pathlib import Path

import numpy as np
from starlette.testclient import TestClient

from app.main import app
from app.schemas.requests import SignToTextRequest
from app.schemas.responses import TextToKslResponse, TextToSpeechResponse
from app.services import sign_recognizer, sign_to_text_service
from app.services.sign_to_text_service import recognize_sign

client = TestClient(app)


def test_sign_to_text_recognizes_landmark_path_with_dataset_artifact(tmp_path, monkeypatch) -> None:
    hello_path, _thanks_path = _configure_test_recognizer(tmp_path, monkeypatch)

    response = recognize_sign(SignToTextRequest(landmark_path=str(hello_path), top_k=2))

    assert response.label == "HELLO"
    assert response.text == "HELLO"
    assert response.provider == "dataset_knn"
    assert response.model_id == "dataset-sign-knn-v1"
    assert response.source_kind == "landmark_path"
    assert response.dataset_backed is True
    assert response.top_matches[0].label == "HELLO"
    assert response.status == "ok"


def test_sign_to_text_can_include_speech(tmp_path, monkeypatch) -> None:
    hello_path, _thanks_path = _configure_test_recognizer(tmp_path, monkeypatch)

    def fake_synthesize(request):
        assert request.text == "HELLO"
        assert request.include_ksl is False
        assert request.voice_id == "bf_emma"
        assert request.output_format == "wav"

        return TextToSpeechResponse(
            text="HELLO",
            audio_base64="ZmFrZS13YXY=",
            audio_size_bytes=8,
            content_type="audio/wav",
            file_extension="wav",
            provider="kokoro",
            model_id="Kokoro-82M",
            voice_id="bf_emma",
            output_format="wav_24000",
            text_to_ksl=None,
            status="ok",
        )

    monkeypatch.setattr(sign_to_text_service, "synthesize_speech", fake_synthesize)

    response = recognize_sign(
        SignToTextRequest(
            landmark_path=str(hello_path),
            top_k=2,
            include_speech=True,
            voice_id="bf_emma",
            output_format="wav",
        )
    )

    assert response.label == "HELLO"
    assert response.speech is not None
    assert response.speech.provider == "kokoro"
    assert response.speech.voice_id == "bf_emma"
    assert response.speech.audio_base64 == "ZmFrZS13YXY="
    assert response.status == "ok"


def test_sign_to_text_upload_accepts_uploaded_landmark_file(tmp_path, monkeypatch) -> None:
    hello_path, _thanks_path = _configure_test_recognizer(tmp_path, monkeypatch)

    response = client.post(
        "/api/v1/sign-to-text-upload",
        files={
            "sign_file": (
                "HELLO.npy",
                hello_path.read_bytes(),
                "application/octet-stream",
            )
        },
        data={
            "top_k": "2",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["label"] == "HELLO"
    assert body["source_kind"] == "uploaded_landmark_file"
    assert body["source_upload_filename"] == "HELLO.npy"
    assert body["extracted_frame_count"] == 6
    assert body["top_matches"][0]["label"] == "HELLO"


def test_sign_to_text_upload_accepts_video_and_can_include_speech(tmp_path, monkeypatch) -> None:
    _hello_path, _thanks_path = _configure_test_recognizer(tmp_path, monkeypatch)

    def fake_extract(video_bytes: bytes, *, filename: str | None = None):
        assert video_bytes == b"fake-video-bytes"
        assert filename == "hello.mp4"
        return _build_sequence(hand_offset=1.2)

    def fake_synthesize(request):
        assert request.text == "HELLO"
        return TextToSpeechResponse(
            text="HELLO",
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

    monkeypatch.setattr(
        sign_to_text_service,
        "extract_landmark_sequence_from_video_bytes",
        fake_extract,
    )
    monkeypatch.setattr(sign_to_text_service, "synthesize_speech", fake_synthesize)

    response = client.post(
        "/api/v1/sign-to-text-upload",
        files={
            "sign_file": (
                "hello.mp4",
                b"fake-video-bytes",
                "video/mp4",
            )
        },
        data={
            "top_k": "2",
            "include_speech": "true",
            "output_format": "wav",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["label"] == "HELLO"
    assert body["source_kind"] == "uploaded_video"
    assert body["source_upload_filename"] == "hello.mp4"
    assert body["extracted_frame_count"] == 6
    assert body["speech"]["provider"] == "kokoro"


def test_sign_sequence_to_text_combines_multiple_signs(tmp_path, monkeypatch) -> None:
    hello_path, thanks_path = _configure_test_recognizer(tmp_path, monkeypatch)

    def fake_map_text_to_ksl(request):
        assert request.text == "HELLO THANKS"
        return TextToKslResponse(
            original_text="HELLO THANKS",
            normalized_text="hello thanks",
            gloss=["HELLO", "THANKS"],
            matched_terms=["hello", "thanks"],
            unmatched_terms=[],
            supported=True,
            dataset_backed=True,
            dataset_label_counts={"HELLO": 1, "THANKS": 1},
            lesson_assets=[],
            lesson_asset_id="dataset-sequence:hello__thanks",
            catalog_backed=True,
            catalog_name="test_catalog",
            catalog_generated_at="2026-06-22T00:00:00+00:00",
            status="ok",
        )

    monkeypatch.setattr(sign_to_text_service, "map_text_to_ksl", fake_map_text_to_ksl)

    response = client.post(
        "/api/v1/sign-sequence-to-text",
        json={
            "items": [
                {"landmark_path": str(hello_path)},
                {"landmark_path": str(thanks_path)},
            ],
            "top_k": 2,
            "include_ksl": True,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["text"] == "HELLO THANKS"
    assert body["normalized_text"] == "hello thanks"
    assert body["sign_count"] == 2
    assert [item["label"] for item in body["items"]] == ["HELLO", "THANKS"]
    assert body["provider"] == "dataset_knn"
    assert body["model_id"] == "dataset-sign-sequence-v1"
    assert body["text_to_ksl"]["lesson_asset_id"] == "dataset-sequence:hello__thanks"
    assert body["status"] == "ok"


def test_sign_sequence_to_text_can_include_speech(tmp_path, monkeypatch) -> None:
    hello_path, thanks_path = _configure_test_recognizer(tmp_path, monkeypatch)

    def fake_synthesize(request):
        assert request.text == "HELLO THANKS"
        assert request.include_ksl is False
        return TextToSpeechResponse(
            text="HELLO THANKS",
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

    monkeypatch.setattr(sign_to_text_service, "synthesize_speech", fake_synthesize)

    response = client.post(
        "/api/v1/sign-sequence-to-text",
        json={
            "items": [
                {"landmark_path": str(hello_path)},
                {"landmark_path": str(thanks_path)},
            ],
            "top_k": 2,
            "include_speech": True,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["text"] == "HELLO THANKS"
    assert body["speech"]["provider"] == "kokoro"
    assert body["speech"]["audio_base64"] == "ZmFrZS13YXY="


def test_sign_to_text_route_returns_400_when_no_landmark_input() -> None:
    response = client.post("/api/v1/sign-to-text", json={})

    assert response.status_code == 400
    assert response.json()["detail"] == "Provide landmark_path or lesson_asset_id for sign-to-text recognition."


def test_sign_to_text_upload_returns_400_for_unsupported_file_type() -> None:
    response = client.post(
        "/api/v1/sign-to-text-upload",
        files={
            "sign_file": (
                "notes.txt",
                b"hello",
                "text/plain",
            )
        },
    )

    assert response.status_code == 400
    assert "Unsupported uploaded sign file" in response.json()["detail"]


def test_sign_sequence_to_text_returns_400_when_empty() -> None:
    response = client.post(
        "/api/v1/sign-sequence-to-text",
        json={"items": []},
    )

    assert response.status_code == 400
    assert "Provide at least one sign item" in response.json()["detail"]


def _configure_test_recognizer(tmp_path: Path, monkeypatch) -> tuple[Path, Path]:
    sign_recognizer.clear_sign_recognizer_cache()
    manifest_path = tmp_path / "manifest.csv"
    artifact_path = tmp_path / "recognizer.npz"
    label_set_path = tmp_path / "labels.json"

    hello_path = tmp_path / "HELLO.npy"
    thanks_path = tmp_path / "THANKS.npy"
    _write_sequence(hello_path, hand_offset=1.2)
    _write_sequence(thanks_path, hand_offset=-1.2)

    label_set_path.write_text(
        '{"label_set_name":"test_labels","labels":["HELLO","THANKS"]}',
        encoding="utf-8",
    )

    with manifest_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["label", "landmark_path"])
        writer.writeheader()
        writer.writerow({"label": "HELLO", "landmark_path": str(hello_path)})
        writer.writerow({"label": "THANKS", "landmark_path": str(thanks_path)})

    monkeypatch.setattr(sign_recognizer.settings, "sign_recognizer_manifest_path", str(manifest_path))
    monkeypatch.setattr(sign_recognizer.settings, "sign_recognizer_artifact_path", str(artifact_path))
    monkeypatch.setattr(sign_recognizer.settings, "sign_recognizer_label_set_path", str(label_set_path))
    monkeypatch.setattr(sign_recognizer.settings, "sign_recognizer_min_samples_per_label", 1)
    monkeypatch.setattr(sign_recognizer.settings, "sign_recognizer_target_frames", 12)

    return hello_path, thanks_path


def _write_sequence(path: Path, *, hand_offset: float) -> None:
    np.save(path, _build_sequence(hand_offset=hand_offset))


def _build_sequence(*, hand_offset: float) -> np.ndarray:
    frames = []
    for step in range(6):
        pose = [(0.0, 0.0, 0.0)] * 33
        pose[11] = (-1.0, 0.0, 0.0)
        pose[12] = (1.0, 0.0, 0.0)
        pose[23] = (-0.6, -1.5, 0.0)
        pose[24] = (0.6, -1.5, 0.0)
        right_hand = [(hand_offset + step * 0.05, 0.6, 0.0)] * 21
        frames.append(
            {
                "pose": pose,
                "left_hand": [],
                "right_hand": right_hand,
                "face": [],
            }
        )

    return np.asarray(frames, dtype=object)
