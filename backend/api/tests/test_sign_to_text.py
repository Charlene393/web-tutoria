import csv
from pathlib import Path

import numpy as np
from starlette.testclient import TestClient

from app.main import app
from app.services import sign_recognizer
from app.services.sign_to_text_service import recognize_sign
from app.schemas.requests import SignToTextRequest

client = TestClient(app)


def test_sign_to_text_recognizes_landmark_path_with_dataset_artifact(tmp_path, monkeypatch) -> None:
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

    response = recognize_sign(SignToTextRequest(landmark_path=str(hello_path), top_k=2))

    assert response.label == "HELLO"
    assert response.text == "HELLO"
    assert response.provider == "dataset_knn"
    assert response.model_id == "dataset-sign-knn-v1"
    assert response.dataset_backed is True
    assert response.top_matches[0].label == "HELLO"
    assert response.status == "ok"


def test_sign_to_text_route_returns_400_when_no_landmark_input() -> None:
    response = client.post("/api/v1/sign-to-text", json={})

    assert response.status_code == 400
    assert response.json()["detail"] == "Provide landmark_path or lesson_asset_id for sign-to-text recognition."


def _write_sequence(path: Path, *, hand_offset: float) -> None:
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

    np.save(path, np.asarray(frames, dtype=object))
