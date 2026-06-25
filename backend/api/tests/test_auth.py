from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_register_login_and_me_flow() -> None:
    email = f"student-{uuid4().hex[:10]}@example.com"

    register_response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "StrongPass123",
            "full_name": "Test Student",
        },
    )
    assert register_response.status_code == 201
    register_payload = register_response.json()
    assert register_payload["user"]["email"] == email
    assert register_payload["token_type"] == "bearer"
    assert register_payload["status"] == "ok"

    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": "StrongPass123",
        },
    )
    assert login_response.status_code == 200
    login_payload = login_response.json()
    assert login_payload["user"]["email"] == email
    assert login_payload["access_token"]

    me_response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {login_payload['access_token']}"},
    )
    assert me_response.status_code == 200
    me_payload = me_response.json()
    assert me_payload["email"] == email
    assert me_payload["full_name"] == "Test Student"


def test_login_rejects_invalid_password() -> None:
    email = f"student-{uuid4().hex[:10]}@example.com"

    client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "StrongPass123",
            "full_name": "Another Student",
        },
    )

    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": "wrong-password",
        },
    )
    assert response.status_code == 401
