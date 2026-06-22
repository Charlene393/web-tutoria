import pytest

from app.integrations import mediapipe_sign_client


def test_resolve_holistic_landmarker_model_path_uses_override(tmp_path, monkeypatch) -> None:
    model_path = tmp_path / "holistic_landmarker.task"
    model_path.write_bytes(b"fake-model")

    monkeypatch.setattr(
        mediapipe_sign_client.settings,
        "sign_video_mediapipe_model_path",
        str(model_path),
    )

    resolved = mediapipe_sign_client._resolve_holistic_landmarker_model_path()

    assert resolved == model_path


def test_resolve_holistic_landmarker_model_path_raises_helpful_error_when_missing(
    tmp_path, monkeypatch
) -> None:
    missing_path = tmp_path / "missing.task"

    monkeypatch.setattr(
        mediapipe_sign_client.settings,
        "sign_video_mediapipe_model_path",
        str(missing_path),
    )

    with pytest.raises(RuntimeError) as exc_info:
        mediapipe_sign_client._resolve_holistic_landmarker_model_path()

    message = str(exc_info.value)
    assert "Holistic Landmarker model file is missing" in message
    assert "SIGN_VIDEO_MEDIAPIPE_MODEL_PATH" in message
    assert "curl -L" in message
