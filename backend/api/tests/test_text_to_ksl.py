from starlette.testclient import TestClient

from app.main import app

client = TestClient(app)


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
    assert body["lesson_assets"][0]["landmark_path"].endswith("/ME.npy")
    assert body["lesson_assets"][0]["stickman_video_path"].endswith("/ME.mp4")
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
