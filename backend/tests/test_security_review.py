from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import jwt
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.services.ai_exercise import _provider_context
from tests.test_auth import PASSWORD, authorization_header, register


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/auth/me",
        "/api/v1/languages",
        "/api/v1/catalog/languages",
        "/api/v1/learning-tracks",
        "/api/v1/catalog/learning-tracks",
        "/api/v1/vocabulary-sets",
        "/api/v1/vocabularies",
        "/api/v1/vocabularies/due-for-review",
        "/api/v1/exercises",
        "/api/v1/exercise-attempts",
        "/api/v1/dashboard",
    ],
)
def test_all_private_read_routes_reject_missing_jwt(
    client: TestClient, path: str
) -> None:
    response = client.get(path)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize(
    ("claim_changes", "signing_secret"),
    [
        ({"type": "refresh"}, None),
        ({"iss": "wrong-issuer"}, None),
        ({"aud": "wrong-audience"}, None),
        ({"jti": None}, None),
        ({}, "wrong-signing-secret-that-is-long-enough"),
    ],
)
def test_invalid_jwt_claims_and_signatures_are_rejected(
    client: TestClient,
    claim_changes: dict[str, object],
    signing_secret: str | None,
) -> None:
    user_id = register(client).json()["id"]
    settings = get_settings()
    now = datetime.now(UTC)
    claims: dict[str, object] = {
        "sub": user_id,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=5),
        "jti": str(uuid.uuid4()),
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
    }
    claims.update(claim_changes)
    if claims.get("jti") is None:
        claims.pop("jti")
    token = jwt.encode(
        claims,
        signing_secret or settings.jwt_secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )

    response = client.get(
        "/api/v1/auth/me",
        headers=authorization_header(token),
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Could not validate credentials"}


def test_auth_requests_reject_unexpected_ownership_fields(client: TestClient) -> None:
    registration = client.post(
        "/api/v1/auth/register",
        json={
            "email": "unexpected-field@example.com",
            "password": PASSWORD,
            "user_id": str(uuid.uuid4()),
        },
    )
    login = client.post(
        "/api/v1/auth/login",
        json={
            "email": "unknown@example.com",
            "password": PASSWORD,
            "user_id": str(uuid.uuid4()),
        },
    )
    assert registration.status_code == 422
    assert login.status_code == 422


def test_api_security_headers_and_no_store_are_present(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"


def test_cors_allows_configured_origin_and_rejects_untrusted_origin(
    client: TestClient,
) -> None:
    preflight_headers = {
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "authorization,content-type",
    }
    allowed = client.options(
        "/api/v1/auth/login",
        headers={"Origin": "http://localhost:5173", **preflight_headers},
    )
    untrusted = client.options(
        "/api/v1/auth/login",
        headers={"Origin": "https://untrusted.example", **preflight_headers},
    )
    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert untrusted.status_code == 400
    assert "access-control-allow-origin" not in untrusted.headers


def test_wildcard_cors_configuration_is_rejected() -> None:
    with pytest.raises(ValidationError, match="Wildcard CORS origins"):
        Settings(
            _env_file=None,
            database_url="postgresql+psycopg://test:test@localhost/test",
            jwt_secret_key="test-only-jwt-secret-key-that-is-long-enough",
            cors_origins=["*"],
        )


def test_ai_exercise_context_is_bounded_and_contains_no_user_metadata() -> None:
    vocabulary = SimpleNamespace(
        id=uuid.uuid4(),
        word="bounded",
        part_of_speech="adjective",
        meaning="m" * 1500,
        example_sentences=["a" * 500, "b" * 500, "c" * 500],
    )

    context = _provider_context([vocabulary])[0]

    assert set(context) == {
        "id",
        "word",
        "part_of_speech",
        "meaning",
        "example_sentences",
    }
    assert len(context["meaning"]) == 1000
    assert [len(item) for item in context["example_sentences"]] == [300]
