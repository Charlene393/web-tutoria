from starlette.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_api_v1_index_without_slash_redirects_to_slash_route() -> None:
    response = client.get("/api/v1")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "Web Tutoria API"
    assert body["api_prefix"] == "/api/v1"
    assert body["health"] == "/api/v1/health"
    assert "POST /api/v1/text-to-ksl" in body["available_endpoints"]
    assert body["status"] == "ok"


def test_api_v1_index_with_slash_returns_service_metadata() -> None:
    response = client.get("/api/v1/")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "Web Tutoria API"
    assert body["status"] == "ok"
