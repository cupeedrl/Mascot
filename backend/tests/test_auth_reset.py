from __future__ import annotations

import time
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.core.security import hash_password, verify_password
from app.models import PasswordResetToken, User
from app.services.ai_guard import ai_guard
from app.services.auth import _as_utc, hash_token
from app.services.email import test_email_provider
from tests.test_vocabulary import authenticate


def test_forgot_password_generic_success_for_existing_and_unknown_email(
    client: TestClient,
    session_factory: sessionmaker[Session],
) -> None:
    test_email_provider.clear()
    settings = get_settings()

    # Register an active user
    headers = authenticate(client, email="alice_reset@example.com")
    test_email_provider.clear()

    # 1. Existing email
    resp_existing = client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "alice_reset@example.com"},
    )
    assert resp_existing.status_code == 200
    data_existing = resp_existing.json()
    assert "Nếu email này đã được đăng ký" in data_existing["message"]

    # Verify email was sent and contains reset token
    assert len(test_email_provider.sent_emails) == 1
    sent = test_email_provider.sent_emails[0]
    assert sent["to"] == "alice_reset@example.com"
    assert "Đặt lại mật khẩu" in sent["subject"]
    assert "/reset-password?token=" in sent["html"]

    # Verify token in DB is hashed, NOT plaintext
    raw_token = sent["html"].split("/reset-password?token=")[1].split('"')[0]
    with session_factory() as db:
        user = db.scalar(select(User).where(User.email == "alice_reset@example.com"))
        token_row = db.scalar(
            select(PasswordResetToken).where(PasswordResetToken.user_id == user.id)
        )
        assert token_row is not None
        assert token_row.token_hash == hash_token(raw_token)
        assert token_row.token_hash != raw_token  # Not plaintext!
        assert token_row.used_at is None
        assert _as_utc(token_row.expires_at) > datetime.now(timezone.utc)

    # 2. Unknown email (returns identical generic success)
    test_email_provider.clear()
    resp_unknown = client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "nonexistent_person_999@example.com"},
    )
    assert resp_unknown.status_code == 200
    assert resp_unknown.json()["message"] == data_existing["message"]
    # No email sent for unknown user
    assert len(test_email_provider.sent_emails) == 0


def test_reset_password_success_and_login_flow(
    client: TestClient,
    session_factory: sessionmaker[Session],
) -> None:
    test_email_provider.clear()
    authenticate(client, email="bob_reset@example.com")
    test_email_provider.clear()

    # Request reset
    client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "bob_reset@example.com"},
    )
    assert len(test_email_provider.sent_emails) == 1
    raw_token = test_email_provider.sent_emails[0]["html"].split("/reset-password?token=")[1].split('"')[0]

    # Reset password with valid token
    new_password = "BrandNewStrongPassword2026!"
    reset_resp = client.post(
        "/api/v1/auth/reset-password",
        json={
            "token": raw_token,
            "new_password": new_password,
            "confirm_password": new_password,
        },
    )
    assert reset_resp.status_code == 200
    assert "Mật khẩu đã được cập nhật" in reset_resp.json()["message"]

    # Verify token is marked used
    with session_factory() as db:
        token_row = db.scalar(
            select(PasswordResetToken).where(PasswordResetToken.token_hash == hash_token(raw_token))
        )
        assert token_row.used_at is not None

    # Old password no longer works
    login_old = client.post(
        "/api/v1/auth/login",
        json={"email": "bob_reset@example.com", "password": "StrongPassword123!"},
    )
    assert login_old.status_code == 401

    # New password works
    login_new = client.post(
        "/api/v1/auth/login",
        json={"email": "bob_reset@example.com", "password": new_password},
    )
    assert login_new.status_code == 200
    assert "access_token" in login_new.json()


def test_reset_password_rejects_used_token(
    client: TestClient,
    session_factory: sessionmaker[Session],
) -> None:
    test_email_provider.clear()
    authenticate(client, email="used_token_user@example.com")
    test_email_provider.clear()

    client.post("/api/v1/auth/forgot-password", json={"email": "used_token_user@example.com"})
    raw_token = test_email_provider.sent_emails[0]["html"].split("/reset-password?token=")[1].split('"')[0]

    # First reset succeeds
    resp1 = client.post(
        "/api/v1/auth/reset-password",
        json={
            "token": raw_token,
            "new_password": "ValidPassword123!",
            "confirm_password": "ValidPassword123!",
        },
    )
    assert resp1.status_code == 200

    # Second reset with same token fails
    resp2 = client.post(
        "/api/v1/auth/reset-password",
        json={
            "token": raw_token,
            "new_password": "AnotherValidPassword123!",
            "confirm_password": "AnotherValidPassword123!",
        },
    )
    assert resp2.status_code == 400
    assert "đã được sử dụng" in resp2.json()["detail"]


def test_reset_password_rejects_expired_token(
    client: TestClient,
    session_factory: sessionmaker[Session],
) -> None:
    test_email_provider.clear()
    authenticate(client, email="expired_token_user@example.com")
    test_email_provider.clear()

    client.post("/api/v1/auth/forgot-password", json={"email": "expired_token_user@example.com"})
    raw_token = test_email_provider.sent_emails[0]["html"].split("/reset-password?token=")[1].split('"')[0]

    # Manually expire the token in DB
    with session_factory() as db:
        token_row = db.scalar(
            select(PasswordResetToken).where(PasswordResetToken.token_hash == hash_token(raw_token))
        )
        token_row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=5)
        db.commit()

    resp = client.post(
        "/api/v1/auth/reset-password",
        json={
            "token": raw_token,
            "new_password": "ValidPassword123!",
            "confirm_password": "ValidPassword123!",
        },
    )
    assert resp.status_code == 400
    assert "hết hạn" in resp.json()["detail"]


def test_reset_password_rejects_mismatched_or_short_password(
    client: TestClient,
) -> None:
    # 1. Short password (<12 chars)
    resp_short = client.post(
        "/api/v1/auth/reset-password",
        json={
            "token": "valid_looking_token_1234567890",
            "new_password": "Short1!",
            "confirm_password": "Short1!",
        },
    )
    assert resp_short.status_code == 422

    # 2. Password mismatch
    resp_mismatch = client.post(
        "/api/v1/auth/reset-password",
        json={
            "token": "valid_looking_token_1234567890",
            "new_password": "ValidPassword123!",
            "confirm_password": "DifferentPassword123!",
        },
    )
    assert resp_mismatch.status_code == 422
    assert "không khớp" in resp_mismatch.json()["detail"]


def test_forgot_password_rate_limit_cooldown(
    client: TestClient,
) -> None:
    test_email_provider.clear()
    authenticate(client, email="cooldown_email@example.com")
    test_email_provider.clear()

    # 1st request sends email
    resp1 = client.post("/api/v1/auth/forgot-password", json={"email": "cooldown_email@example.com"})
    assert resp1.status_code == 200
    assert len(test_email_provider.sent_emails) == 1

    # 2nd request within 60s is throttled (no 2nd email), but returns same generic success
    resp2 = client.post("/api/v1/auth/forgot-password", json={"email": "cooldown_email@example.com"})
    assert resp2.status_code == 200
    assert resp2.json() == resp1.json()
    assert len(test_email_provider.sent_emails) == 1  # Still 1
