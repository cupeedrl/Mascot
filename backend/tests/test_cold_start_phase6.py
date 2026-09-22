from fastapi.testclient import TestClient

from app.api.v1.routes import health


def test_liveness_health_is_public_and_does_not_touch_database(
    client: TestClient, monkeypatch
) -> None:
    def fail_if_called(_db) -> None:
        raise AssertionError("liveness health must not query the database")

    monkeypatch.setattr(health, "verify_database_connection", fail_if_called)

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_database_readiness_health_remains_public(client: TestClient) -> None:
    response = client.get("/api/v1/health/database")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "reachable"}


def test_auth_invalid_credentials_behavior_is_unchanged(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "unknown@example.com", "password": "WrongPassword123!"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid email or password"}


def test_configured_frontend_origin_can_call_readiness_health(
    client: TestClient,
) -> None:
    response = client.options(
        "/api/v1/health/database",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
