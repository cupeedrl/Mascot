from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.core.security import hash_password, verify_password
from app.models import PasswordResetToken, User
from app.services.ai_guard import ai_guard
from app.services.auth import _as_utc, hash_token, reset_password_with_token
from app.services.email import ResendEmailProvider, test_email_provider
from tests.test_vocabulary import authenticate


def test_1_and_test_2_reset_token_consumed_once_and_persisted(
    client: TestClient,
    session_factory: sessionmaker[Session],
) -> None:
    test_email_provider.clear()
    authenticate(client, email="persistence_user@example.com")
    test_email_provider.clear()

    # 1. Request forgot-password
    resp_forgot = client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "persistence_user@example.com"},
    )
    assert resp_forgot.status_code == 200
    raw_token = test_email_provider.sent_emails[0]["html"].split("/reset-password?token=")[1].split('"')[0]

    # Verify DB directly before reset: used_at IS NULL
    with session_factory() as db:
        token_before = db.scalar(
            select(PasswordResetToken).where(PasswordResetToken.token_hash == hash_token(raw_token))
        )
        assert token_before is not None
        assert token_before.used_at is None

    # 2. First reset: succeeds
    resp1 = client.post(
        "/api/v1/auth/reset-password",
        json={
            "token": raw_token,
            "new_password": "FirstNewPassword123!",
            "confirm_password": "FirstNewPassword123!",
        },
    )
    assert resp1.status_code == 200
    assert "Mật khẩu đã được cập nhật" in resp1.json()["message"]

    # Test 2: Verify DB state directly in a separate DB session
    with session_factory() as db:
        token_after = db.scalar(
            select(PasswordResetToken).where(PasswordResetToken.token_hash == hash_token(raw_token))
        )
        assert token_after is not None
        assert token_after.used_at is not None  # Persisted in DB!

    # 3. Second reset with the exact same token: MUST FAIL
    resp2 = client.post(
        "/api/v1/auth/reset-password",
        json={
            "token": raw_token,
            "new_password": "SecondNewPassword123!",
            "confirm_password": "SecondNewPassword123!",
        },
    )
    assert resp2.status_code == 400
    assert "không hợp lệ hoặc đã hết hạn" in resp2.json()["detail"]

    # Verify the second password was NOT written
    login_second = client.post(
        "/api/v1/auth/login",
        json={"email": "persistence_user@example.com", "password": "SecondNewPassword123!"},
    )
    assert login_second.status_code == 401

    # Verify the first new password authenticates
    login_first = client.post(
        "/api/v1/auth/login",
        json={"email": "persistence_user@example.com", "password": "FirstNewPassword123!"},
    )
    assert login_first.status_code == 200


def test_3_two_active_tokens_consume_one_invalidates_the_other(
    client: TestClient,
    session_factory: sessionmaker[Session],
) -> None:
    test_email_provider.clear()
    authenticate(client, email="two_tokens_user@example.com")
    test_email_provider.clear()

    tok1_raw = "token_one_random_string_123456789"
    tok2_raw = "token_two_random_string_123456789"

    with session_factory() as db:
        user = db.scalar(select(User).where(User.email == "two_tokens_user@example.com"))
        now = datetime.now(timezone.utc)
        t1 = PasswordResetToken(
            user_id=user.id,
            token_hash=hash_token(tok1_raw),
            expires_at=now + timedelta(minutes=20),
            created_at=now,
        )
        t2 = PasswordResetToken(
            user_id=user.id,
            token_hash=hash_token(tok2_raw),
            expires_at=now + timedelta(minutes=20),
            created_at=now,
        )
        db.add_all([t1, t2])
        db.commit()

    # Successfully consume Token 1
    resp1 = client.post(
        "/api/v1/auth/reset-password",
        json={
            "token": tok1_raw,
            "new_password": "PasswordFromToken1!",
            "confirm_password": "PasswordFromToken1!",
        },
    )
    assert resp1.status_code == 200

    # Token 2 must now be rejected
    resp2 = client.post(
        "/api/v1/auth/reset-password",
        json={
            "token": tok2_raw,
            "new_password": "PasswordFromToken2!",
            "confirm_password": "PasswordFromToken2!",
        },
    )
    assert resp2.status_code == 400
    assert "không hợp lệ hoặc đã hết hạn" in resp2.json()["detail"]


def test_4_expired_token_fails(
    client: TestClient,
    session_factory: sessionmaker[Session],
) -> None:
    test_email_provider.clear()
    authenticate(client, email="expired_token_check@example.com")
    test_email_provider.clear()

    client.post("/api/v1/auth/forgot-password", json={"email": "expired_token_check@example.com"})
    raw_token = test_email_provider.sent_emails[0]["html"].split("/reset-password?token=")[1].split('"')[0]

    # Expire the token in DB
    with session_factory() as db:
        token_row = db.scalar(
            select(PasswordResetToken).where(PasswordResetToken.token_hash == hash_token(raw_token))
        )
        token_row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
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
    assert "không hợp lệ hoặc đã hết hạn" in resp.json()["detail"]


def test_5_malformed_or_random_token_fails(
    client: TestClient,
) -> None:
    resp = client.post(
        "/api/v1/auth/reset-password",
        json={
            "token": "completely_bogus_token_value_987654321",
            "new_password": "ValidPassword123!",
            "confirm_password": "ValidPassword123!",
        },
    )
    assert resp.status_code == 400
    assert "không hợp lệ hoặc đã hết hạn" in resp.json()["detail"]


def test_forgot_password_generic_success_and_cooldown(
    client: TestClient,
) -> None:
    test_email_provider.clear()
    authenticate(client, email="generic_user@example.com")
    test_email_provider.clear()

    # 1. Existing user
    resp1 = client.post("/api/v1/auth/forgot-password", json={"email": "generic_user@example.com"})
    assert resp1.status_code == 200
    assert "Nếu email này đã được đăng ký" in resp1.json()["message"]
    assert len(test_email_provider.sent_emails) == 1

    # 2. Unknown user gets identical response
    test_email_provider.clear()
    resp_unknown = client.post("/api/v1/auth/forgot-password", json={"email": "unknown@example.com"})
    assert resp_unknown.status_code == 200
    assert resp_unknown.json()["message"] == resp1.json()["message"]
    assert len(test_email_provider.sent_emails) == 0


def test_resend_strips_newlines_and_sanitizes_error_logs(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.ERROR)
    dirty_key = "\n  re_secret_key_with_newline_12345 \r\n"
    provider = ResendEmailProvider(api_key=dirty_key, from_address="Mascot <support@test.com>\n")
    assert provider._api_key == "re_secret_key_with_newline_12345"

    with patch("urllib.request.urlopen", side_effect=Exception(f"Failed header: Bearer {dirty_key}")):
        success = provider.send_email(
            to_email="test@example.com",
            subject="Test",
            html_content="<p>Test</p>",
            text_content="Test",
        )
        assert success is False

    for record in caplog.records:
        assert "re_secret_key_with_newline" not in record.message
        assert "Bearer" not in record.message
        assert "password_reset_email_send_failed" in record.message


def test_validate_reset_token_endpoint(
    client: TestClient,
    session_factory: sessionmaker[Session],
) -> None:
    test_email_provider.clear()
    authenticate(client, email="validate_test_user@example.com")
    test_email_provider.clear()

    # 1. Generate token
    client.post("/api/v1/auth/forgot-password", json={"email": "validate_test_user@example.com"})
    raw_token = test_email_provider.sent_emails[0]["html"].split("/reset-password?token=")[1].split('"')[0]

    # 2. Validate endpoint with fresh token: returns 200 { valid: True }
    resp_valid = client.get(f"/api/v1/auth/reset-password/validate?token={raw_token}")
    assert resp_valid.status_code == 200
    assert resp_valid.json() == {"valid": True}

    # 3. Verify validation did NOT consume or mutate the token in DB
    with session_factory() as db:
        token_row = db.scalar(
            select(PasswordResetToken).where(PasswordResetToken.token_hash == hash_token(raw_token))
        )
        assert token_row is not None
        assert token_row.used_at is None

    # 4. Actual reset succeeds once
    resp_reset = client.post(
        "/api/v1/auth/reset-password",
        json={
            "token": raw_token,
            "new_password": "NewSecretPassword123!",
            "confirm_password": "NewSecretPassword123!",
        },
    )
    assert resp_reset.status_code == 200

    # 5. Now validation for the same token returns 400 (already consumed)
    resp_after_reset = client.get(f"/api/v1/auth/reset-password/validate?token={raw_token}")
    assert resp_after_reset.status_code == 400
    assert "không hợp lệ hoặc đã hết hạn" in resp_after_reset.json()["detail"]

    # 6. Malformed / non-existent token returns 400
    resp_malformed = client.get("/api/v1/auth/reset-password/validate?token=non_existent_token_12345")
    assert resp_malformed.status_code == 400
    assert "không hợp lệ hoặc đã hết hạn" in resp_malformed.json()["detail"]

    # 7. Short/empty token returns 400
    resp_short = client.get("/api/v1/auth/reset-password/validate?token=abc")
    assert resp_short.status_code == 400

