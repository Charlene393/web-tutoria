from starlette.testclient import TestClient

from app.main import app
from app.services import health_service

client = TestClient(app)


def test_health_reports_backend_readiness(tmp_path, monkeypatch) -> None:
    lesson_catalog = tmp_path / "ksl_lesson_catalog.json"
    manifest = tmp_path / "manifest.csv"
    artifact = tmp_path / "recognizer.npz"
    label_set = tmp_path / "labels.json"
    video_model = tmp_path / "holistic_landmarker.task"

    for path in [lesson_catalog, manifest, artifact, label_set, video_model]:
        path.write_text("ready", encoding="utf-8")

    monkeypatch.setattr(health_service, "_lesson_catalog_path", lambda: lesson_catalog)
    monkeypatch.setattr(health_service, "default_manifest_path", lambda: manifest)
    monkeypatch.setattr(health_service, "default_artifact_path", lambda: artifact)
    monkeypatch.setattr(health_service, "default_label_set_path", lambda: label_set)
    monkeypatch.setattr(health_service, "_resolve_sign_video_model_path", lambda: video_model)
    monkeypatch.setattr(health_service, "_module_available", lambda _name: True)
    monkeypatch.setattr(health_service, "get_kokoro_pipeline", lambda: object())
    monkeypatch.setattr(health_service, "get_faster_whisper_model", lambda: object())

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["app_name"] == "Web Tutoria API"
    assert body["checks"]["lesson_catalog"]["ready"] is True
    assert body["checks"]["sign_recognizer_artifact"]["ready"] is True
    assert body["checks"]["kokoro"]["ready"] is True
    assert body["checks"]["faster_whisper"]["ready"] is True


def test_health_returns_partial_when_required_runtime_is_not_ready(tmp_path, monkeypatch) -> None:
    lesson_catalog = tmp_path / "ksl_lesson_catalog.json"
    manifest = tmp_path / "manifest.csv"
    label_set = tmp_path / "labels.json"

    for path in [lesson_catalog, manifest, label_set]:
        path.write_text("ready", encoding="utf-8")

    monkeypatch.setattr(health_service, "_lesson_catalog_path", lambda: lesson_catalog)
    monkeypatch.setattr(health_service, "default_manifest_path", lambda: manifest)
    monkeypatch.setattr(health_service, "default_artifact_path", lambda: tmp_path / "missing.npz")
    monkeypatch.setattr(health_service, "default_label_set_path", lambda: label_set)
    monkeypatch.setattr(health_service, "_resolve_sign_video_model_path", lambda: tmp_path / "missing.task")
    monkeypatch.setattr(health_service, "_module_available", lambda _name: True)
    monkeypatch.setattr(health_service, "get_faster_whisper_model", lambda: object())

    def fail_kokoro():
        raise RuntimeError("Kokoro failed to initialize.")

    monkeypatch.setattr(health_service, "get_kokoro_pipeline", fail_kokoro)

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "partial"
    assert body["checks"]["kokoro"]["ready"] is False
    assert body["checks"]["kokoro"]["required"] is True
    assert "Kokoro failed to initialize" in body["checks"]["kokoro"]["detail"]
    assert body["checks"]["sign_recognizer_artifact"]["required"] is False
