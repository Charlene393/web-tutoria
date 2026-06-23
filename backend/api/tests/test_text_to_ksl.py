import json
from pathlib import Path

from starlette.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_lesson_catalog_file_exists_and_excludes_dropped_label() -> None:
    catalog_path = Path(__file__).resolve().parents[1] / "app" / "data" / "ksl_lesson_catalog.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))

    assert catalog["catalog_name"] == "ksl_cleaned_lesson_catalog"
    assert catalog["total_entries"] > 0
    labels = {entry["label"] for entry in catalog["entries"]}
    assert ".mp4" not in labels
    assert "ME" in labels


def test_text_to_ksl_phrase_match_uses_dataset_backed_gloss() -> None:
    response = client.post("/api/v1/text-to-ksl", json={"text": "I want food"})

    assert response.status_code == 200
    body = response.json()
    assert body["gloss"] == ["ME", "WANT", "FOOD"]
    assert body["matched_terms"] == ["i want food"]
    assert body["unmatched_terms"] == []
    assert body["supported"] is True
    assert body["dataset_backed"] is True
    assert body["dataset_label_counts"]["ME"] > 0
    assert body["dataset_label_counts"]["WANT"] > 0
    assert body["dataset_label_counts"]["FOOD"] > 0
    assert body["lesson_asset_id"] == "dataset-sequence:me__want__food"
    assert [asset["label"] for asset in body["lesson_assets"]] == ["ME", "WANT", "FOOD"]
    assert body["lesson_assets"][0]["source"] == "cleaned_lesson_catalog"
    assert body["lesson_assets"][0]["frame_count"] > 0
    assert isinstance(body["lesson_assets"][0]["sample_flags"], list)
    assert body["lesson_assets"][0]["quality_score"] is not None
    assert body["lesson_assets"][0]["landmark_path"].endswith("/ME.npy")
    assert body["lesson_assets"][0]["stickman_video_path"].endswith("/ME.mp4")
    assert body["lesson_assets"][0]["stickman_video_url"] == "/api/v1/lesson-assets/lesson-sign%3Ame/stickman-video"
    assert body["catalog_backed"] is True
    assert body["catalog_name"] == "ksl_cleaned_lesson_catalog"
    assert body["catalog_generated_at"]
    assert body["status"] == "ok"


def test_lesson_asset_stickman_video_endpoint_serves_mp4() -> None:
    response = client.get("/api/v1/lesson-assets/lesson-sign:me/stickman-video")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("video/mp4")
    assert len(response.content) > 0


def test_text_to_ksl_alias_uses_cleaned_catalog_asset() -> None:
    response = client.post("/api/v1/text-to-ksl", json={"text": "hello"})

    assert response.status_code == 200
    body = response.json()
    assert body["gloss"] == ["GREETING"]
    assert body["lesson_assets"][0]["label"] == "GREETING"
    assert body["lesson_assets"][0]["source"] == "cleaned_lesson_catalog"
    assert body["catalog_backed"] is True
    assert body["status"] == "ok"


def test_text_to_ksl_ignores_function_words() -> None:
    response = client.post("/api/v1/text-to-ksl", json={"text": "Go to school"})

    assert response.status_code == 200
    body = response.json()
    assert body["gloss"] == ["GO", "SCHOOL"]
    assert body["unmatched_terms"] == []
    assert body["supported"] is True
    assert body["lesson_asset_id"] == "dataset-sequence:go__school"


def test_text_to_ksl_returns_partial_for_unknown_terms() -> None:
    response = client.post("/api/v1/text-to-ksl", json={"text": "Please help me saturn"})

    assert response.status_code == 200
    body = response.json()
    assert body["gloss"] == ["PLEASE", "HELP", "ME"]
    assert body["unmatched_terms"] == ["saturn"]
    assert body["supported"] is False
    assert [asset["label"] for asset in body["lesson_assets"]] == ["PLEASE", "HELP", "ME"]
    assert body["status"] == "partial"


def test_text_to_ksl_returns_unsupported_when_no_dataset_terms_match() -> None:
    response = client.post("/api/v1/text-to-ksl", json={"text": "quantum computer"})

    assert response.status_code == 200
    body = response.json()
    assert body["gloss"] == []
    assert body["matched_terms"] == []
    assert body["unmatched_terms"] == ["quantum", "computer"]
    assert body["supported"] is False
    assert body["dataset_backed"] is False
    assert body["lesson_assets"] == []
    assert body["lesson_asset_id"] is None
    assert body["status"] == "unsupported"
