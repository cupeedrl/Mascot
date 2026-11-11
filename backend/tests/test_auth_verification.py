"""Sign-up with username, display name and a 6-digit email confirmation code."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.models import EmailVerificationCode, User
from app.services.ai_guard import ai_guard
from app.services.email import test_email_provider

PASSWORD = "StrongPassword123!"
BASE = "/api/v1/auth"


@pytest.fixture(autouse=True)
def verification_on(monkeypatch):
    monkeypatch.setattr(get_settings(), "require_email_verification", True)
    test_email_provider.clear()
    for email in ("lan.nguyen@example.com", "nobody@example.com"):
        ai_guard.reset_user(uuid.uuid5(uuid.NAMESPACE_DNS, f"verify:{email}"))
    yield
    test_email_provider.clear()


def sign_up(client: TestClient, **overrides):
    payload = {
        "email": "Lan.Nguyen@Example.com",
        "password": PASSWORD,
        "display_name": "  Nguyễn   Thị Lan ",
        "username": "Lan.Nguyen",
        **overrides,
    }
    return client.post(f"{BASE}/register", json=payload)


def last_code() -> str:
    message = test_email_provider.sent_emails[-1]
    return re.search(r"\b(\d{6})\b", message["subject"]).group(1)


def test_sign_up_sends_a_code_and_blocks_login_until_verified(client: TestClient, session_factory) -> None:
    response = sign_up(client)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["verification_required"] is True
    assert (body["username"], body["display_name"]) == ("lan.nguyen", "Nguyễn Thị Lan")
    assert body["email_verified_at"] is None

    email = test_email_provider.sent_emails[-1]
    assert email["to"] == "Lan.Nguyen@example.com"  # email-validator lowercases the domain
    code = last_code()
    assert code in email["text"] and "Nguyễn Thị Lan" in email["text"]
    with session_factory() as db:
        stored = db.scalar(select(EmailVerificationCode))
        assert stored.code_hash != code and len(stored.code_hash) == 64  # only the hash is stored

    blocked = client.post(f"{BASE}/login", json={"email": "lan.nguyen@example.com", "password": PASSWORD})
    assert blocked.status_code == 403
    assert blocked.json()["detail"]["code"] == "EMAIL_NOT_VERIFIED"
    assert blocked.json()["detail"]["email"] == "Lan.Nguyen@example.com"
    wrong_password = client.post(f"{BASE}/login", json={"email": "lan.nguyen@example.com", "password": "Wrong-Password-1"})
    assert wrong_password.status_code == 401  # no hint about verification without the password

    verified = client.post(f"{BASE}/verify-email", json={"email": "lan.nguyen@example.com", "code": code})
    assert verified.status_code == 200, verified.text
    token = verified.json()["access_token"]
    me = client.get(f"{BASE}/me", headers={"Authorization": f"Bearer {token}"}).json()
    assert me["email_verified_at"] is not None and me["username"] == "lan.nguyen"
    with session_factory() as db:
        assert db.scalar(select(EmailVerificationCode)) is None  # code consumed

    # Login now works with the email or the username (any case).
    for name in ("LAN.NGUYEN@example.com", "Lan.Nguyen"):
        ok = client.post(f"{BASE}/login", json={"identifier": name, "password": PASSWORD})
        assert ok.status_code == 200, (name, ok.text)
    again = client.post(f"{BASE}/verify-email", json={"email": "lan.nguyen@example.com", "code": code})
    assert again.status_code == 409 and again.json()["detail"]["code"] == "ALREADY_VERIFIED"


def test_wrong_codes_count_down_then_lock(client: TestClient) -> None:
    sign_up(client)
    code = last_code()
    wrong = "000000" if code != "000000" else "111111"
    remaining = []
    for _ in range(5):
        response = client.post(f"{BASE}/verify-email", json={"email": "lan.nguyen@example.com", "code": wrong})
        assert response.status_code == 400
        remaining.append((response.json()["detail"]["code"], response.json()["detail"]["remaining_attempts"]))
    assert remaining == [("INVALID_CODE", 4), ("INVALID_CODE", 3), ("INVALID_CODE", 2), ("INVALID_CODE", 1), ("CODE_LOCKED", 0)]
    locked = client.post(f"{BASE}/verify-email", json={"email": "lan.nguyen@example.com", "code": code})
    assert locked.json()["detail"]["code"] == "CODE_LOCKED"  # even the right code is refused now


def test_expired_code_and_resend(client: TestClient, session_factory, monkeypatch) -> None:
    sign_up(client)
    old_code = last_code()
    with session_factory() as db:
        record = db.scalar(select(EmailVerificationCode))
        record.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
    expired = client.post(f"{BASE}/verify-email", json={"email": "lan.nguyen@example.com", "code": old_code})
    assert expired.json()["detail"]["code"] == "CODE_EXPIRED"

    resent = client.post(f"{BASE}/resend-verification", json={"email": "LAN.NGUYEN@example.com"})
    assert resent.status_code == 200 and resent.json()["resend_after_seconds"] == 60
    assert len(test_email_provider.sent_emails) == 2
    new_code = last_code()
    # A second request inside the cooldown sends nothing but answers the same.
    assert client.post(f"{BASE}/resend-verification", json={"email": "lan.nguyen@example.com"}).status_code == 200
    assert len(test_email_provider.sent_emails) == 2
    ok = client.post(f"{BASE}/verify-email", json={"email": "lan.nguyen@example.com", "code": new_code})
    assert ok.status_code == 200


def test_unknown_email_gets_the_same_answers(client: TestClient) -> None:
    resend = client.post(f"{BASE}/resend-verification", json={"email": "nobody@example.com"})
    assert resend.status_code == 200 and not test_email_provider.sent_emails
    verify = client.post(f"{BASE}/verify-email", json={"email": "nobody@example.com", "code": "123456"})
    assert verify.status_code == 400 and verify.json()["detail"]["code"] == "INVALID_CODE"


def test_username_rules_and_availability(client: TestClient) -> None:
    def check(name):
        return client.get(f"{BASE}/username-available", params={"username": name}).json()

    assert check("lan.nguyen") == {"username": "lan.nguyen", "available": True, "reason": None, "message": None}
    sign_up(client)
    assert check("LAN.NGUYEN")["reason"] == "taken"
    assert check("admin")["reason"] == "reserved"
    for bad in ("ab", "1lan", "lan..nguyen", "lan_", "lan nguyen", "lân"):
        assert check(bad)["reason"] == "invalid", bad
    taken = sign_up(client, email="other@example.com", username="lan.NGUYEN")
    assert taken.status_code == 409 and taken.json()["detail"]["code"] == "USERNAME_TAKEN"
    invalid = sign_up(client, email="third@example.com", username="1abc")
    assert invalid.status_code == 422 and invalid.json()["detail"]["code"] == "USERNAME_INVALID"


def test_existing_style_sign_up_without_username_still_works(client: TestClient) -> None:
    response = client.post(f"{BASE}/register", json={"email": "old@example.com", "password": PASSWORD})
    assert response.status_code == 201
    assert response.json()["username"] is None and response.json()["verification_required"] is True


def test_switch_off_means_no_code_and_direct_login(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "require_email_verification", False)
    response = sign_up(client)
    assert response.json()["verification_required"] is False
    assert not test_email_provider.sent_emails
    assert client.post(f"{BASE}/login", json={"identifier": "lan.nguyen", "password": PASSWORD}).status_code == 200


def test_login_payload_must_name_the_account(client: TestClient) -> None:
    assert client.post(f"{BASE}/login", json={"password": PASSWORD}).status_code == 422


def test_stored_user_fields(client: TestClient, session_factory: sessionmaker[Session]) -> None:
    sign_up(client)
    with session_factory() as db:
        user = db.scalar(select(User))
    assert (user.username, user.normalized_username, user.display_name) == ("lan.nguyen", "lan.nguyen", "Nguyễn Thị Lan")


def test_remember_me_issues_a_long_lived_token(client: TestClient) -> None:
    from app.core.security import decode_access_token

    sign_up(client)
    verified = client.post(
        f"{BASE}/verify-email",
        json={"email": "lan.nguyen@example.com", "code": last_code(), "remember_me": True},
    )
    assert verified.json()["expires_in"] == 30 * 24 * 60 * 60

    short = client.post(f"{BASE}/login", json={"identifier": "lan.nguyen", "password": PASSWORD}).json()
    long = client.post(
        f"{BASE}/login", json={"identifier": "lan.nguyen", "password": PASSWORD, "remember_me": True}
    ).json()
    assert short["expires_in"] == 30 * 60
    assert long["expires_in"] == 30 * 24 * 60 * 60
    claims = decode_access_token(long["access_token"])
    assert claims["exp"] - claims["iat"] == 30 * 24 * 60 * 60
