from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.models.user import User

EMAIL = "Learner@Example.com"
CANONICAL_EMAIL = "Learner@example.com"
PASSWORD = "StrongPassword123!"


def register(client: TestClient, email: str = EMAIL, password: str = PASSWORD):
    return client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password},
    )


def login(client: TestClient, email: str = EMAIL, password: str = PASSWORD):
    return client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )


def authorization_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_successful_registration_stores_argon2id_hash(
    client: TestClient,
    session_factory: sessionmaker[Session],
) -> None:
    response = register(client)

    assert response.status_code == 201
    payload = response.json()
    assert payload["email"] == CANONICAL_EMAIL
    assert payload["is_active"] is True
    assert "password_hash" not in payload
    assert "normalized_email" not in payload

    with session_factory() as db:
        stored_user = db.scalar(select(User))

    assert stored_user is not None
    assert stored_user.normalized_email == EMAIL.lower()
    assert stored_user.password_hash != PASSWORD
    assert stored_user.password_hash.startswith("$argon2id$")


def test_duplicate_registration_is_case_insensitive(client: TestClient) -> None:
    assert register(client).status_code == 201

    response = register(client, email="learner@example.com")

    assert response.status_code == 409
    assert response.json() == {
        "detail": "An account with this email already exists"
    }


def test_invalid_registration_input(client: TestClient) -> None:
    response = register(client, email="not-an-email", password="short")

    assert response.status_code == 422


def test_successful_login_returns_expiring_bearer_token(client: TestClient) -> None:
    register(client)

    response = login(client, email="learner@example.com")

    assert response.status_code == 200
    payload = response.json()
    assert payload["token_type"] == "bearer"
    assert payload["expires_in"] == 1800
    assert payload["access_token"]

    settings = get_settings()
    claims = jwt.decode(
        payload["access_token"],
        settings.jwt_secret_key.get_secret_value(),
        algorithms=[settings.jwt_algorithm],
        audience=settings.jwt_audience,
        issuer=settings.jwt_issuer,
    )
    assert claims["type"] == "access"
    assert datetime.fromtimestamp(claims["exp"], timezone.utc) > datetime.now(
        timezone.utc
    )


def test_incorrect_password_uses_generic_error(client: TestClient) -> None:
    register(client)

    response = login(client, password="WrongPassword123!")

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid email or password"}


def test_unknown_email_uses_same_generic_error(client: TestClient) -> None:
    response = login(client, email="unknown@example.com")

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid email or password"}


def test_me_without_token_is_rejected(client: TestClient) -> None:
    response = client.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_me_with_valid_token_returns_safe_user(client: TestClient) -> None:
    registration = register(client).json()
    token = login(client).json()["access_token"]

    response = client.get(
        "/api/v1/auth/me",
        headers=authorization_header(token),
    )

    assert response.status_code == 200
    assert response.json()["id"] == registration["id"]
    assert response.json()["email"] == CANONICAL_EMAIL
    assert "password_hash" not in response.json()
    assert "normalized_email" not in response.json()


def test_me_with_invalid_token_is_rejected(client: TestClient) -> None:
    response = client.get(
        "/api/v1/auth/me",
        headers=authorization_header("not-a-valid-jwt"),
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Could not validate credentials"}


def test_me_with_expired_token_is_rejected(client: TestClient) -> None:
    registration = register(client).json()
    settings = get_settings()
    now = datetime.now(timezone.utc)
    expired_token = jwt.encode(
        {
            "sub": registration["id"],
            "type": "access",
            "iat": now - timedelta(minutes=31),
            "exp": now - timedelta(minutes=1),
            "jti": "expired-token-test",
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
        },
        settings.jwt_secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )

    response = client.get(
        "/api/v1/auth/me",
        headers=authorization_header(expired_token),
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Could not validate credentials"}


def test_inactive_user_cannot_login_or_reuse_existing_token(
    client: TestClient,
    session_factory: sessionmaker[Session],
) -> None:
    register(client)
    token = login(client).json()["access_token"]

    with session_factory() as db:
        user = db.scalar(select(User))
        assert user is not None
        user.is_active = False
        db.commit()

    # 1. Disabled user with wrong password -> generic 401 (no account enumeration)
    wrong_pwd_resp = login(client, password="WrongPassword123!")
    assert wrong_pwd_resp.status_code == 401
    assert wrong_pwd_resp.json()["detail"] == "Invalid email or password"

    # 2. Disabled user with correct password -> 403 ACCOUNT_DISABLED
    disabled_resp = login(client)
    assert disabled_resp.status_code == 403
    assert disabled_resp.json()["detail"]["code"] == "ACCOUNT_DISABLED"
    assert "hạn chế" in disabled_resp.json()["detail"]["message"].lower()

    # 3. Inactive user with existing token -> 401 ACCOUNT_DISABLED
    response = client.get(
        "/api/v1/auth/me",
        headers=authorization_header(token),
    )
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "ACCOUNT_DISABLED"


def test_logout_requires_authentication_and_returns_success(client: TestClient) -> None:
    assert client.post("/api/v1/auth/logout").status_code == 401

    register(client)
    token = login(client).json()["access_token"]
    response = client.post(
        "/api/v1/auth/logout",
        headers=authorization_header(token),
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

    # Stateless V1 logout does not revoke an already issued access token.
    assert client.get(
        "/api/v1/auth/me",
        headers=authorization_header(token),
    ).status_code == 200
