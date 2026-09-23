from __future__ import annotations

import json
import urllib.error
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.services.email import (
    BrevoEmailProvider,
    parse_from_address,
    get_email_provider,
    set_email_provider,
)


def _settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "database_url": "postgresql+psycopg://user:pass@localhost:5432/mascot",
        "jwt_secret_key": "x" * 48,
    }
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


def test_parse_from_address_splits_name_and_email() -> None:
    assert parse_from_address("Mascot <noreply@mascot.app>") == (
        "Mascot",
        "noreply@mascot.app",
    )
    assert parse_from_address("noreply@mascot.app") == ("", "noreply@mascot.app")


def test_brevo_provider_posts_expected_payload() -> None:
    provider = BrevoEmailProvider(
        api_key="brevo-test-key",
        from_address="Mascot <noreply@mascot.app>",
    )
    response = MagicMock()
    response.getcode.return_value = 201
    response.__enter__.return_value = response

    with patch("urllib.request.urlopen", return_value=response) as mock_open:
        sent = provider.send_email(
            to_email="learner@example.com",
            subject="Đặt lại mật khẩu Mascot",
            html_content="<p>Test HTML</p>",
            text_content="Test Text",
        )

    assert sent is True
    request = mock_open.call_args[0][0]
    assert request.full_url == "https://api.brevo.com/v3/smtp/email"
    assert request.get_method() == "POST"
    # urllib title-cases header names it stores.
    assert request.get_header("Api-key") == "brevo-test-key"
    payload = json.loads(request.data.decode("utf-8"))
    assert payload["sender"] == {"email": "noreply@mascot.app", "name": "Mascot"}
    assert payload["to"] == [{"email": "learner@example.com"}]
    assert payload["subject"] == "Đặt lại mật khẩu Mascot"
    assert payload["htmlContent"] == "<p>Test HTML</p>"
    assert payload["textContent"] == "Test Text"


def test_brevo_provider_reports_failure_without_raising() -> None:
    provider = BrevoEmailProvider(api_key="brevo-test-key", from_address="a@b.com")
    error = urllib.error.HTTPError(
        url="https://api.brevo.com/v3/smtp/email",
        code=401,
        msg="Unauthorized",
        hdrs=None,  # type: ignore[arg-type]
        fp=None,
    )

    with patch("urllib.request.urlopen", side_effect=error):
        sent = provider.send_email(
            to_email="learner@example.com",
            subject="Subject",
            html_content="<p>x</p>",
            text_content="x",
        )

    assert sent is False


def test_brevo_provider_refuses_to_send_without_api_key() -> None:
    provider = BrevoEmailProvider(api_key="   ", from_address="a@b.com")

    with patch("urllib.request.urlopen") as mock_open:
        sent = provider.send_email(
            to_email="learner@example.com",
            subject="Subject",
            html_content="<p>x</p>",
            text_content="x",
        )

    assert sent is False
    mock_open.assert_not_called()


def test_brevo_settings_require_an_api_key() -> None:
    with pytest.raises(ValidationError):
        _settings(email_provider="brevo")

    settings = _settings(email_provider="brevo", brevo_api_key="brevo-test-key")
    assert settings.email_provider == "brevo"


def test_provider_factory_returns_brevo_when_configured() -> None:
    set_email_provider(None)
    settings = _settings(
        email_provider="brevo",
        brevo_api_key="brevo-test-key",
        email_from="Mascot <noreply@mascot.app>",
    )

    with patch("app.services.email.get_settings", return_value=settings):
        provider = get_email_provider()

    assert isinstance(provider, BrevoEmailProvider)
