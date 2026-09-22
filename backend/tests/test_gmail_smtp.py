from __future__ import annotations

import smtplib
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.services.email import GmailSmtpEmailProvider, get_email_provider, set_email_provider


def test_gmail_smtp_provider_successful_send() -> None:
    provider = GmailSmtpEmailProvider(
        host="smtp.gmail.com",
        port=587,
        username="mascot_sender@gmail.com",
        app_password="abcd-efgh-ijkl-mnop",
        from_address="Mascot Support <mascot_sender@gmail.com>",
        timeout=5.0,
    )

    mock_smtp_instance = MagicMock()
    mock_smtp_context = MagicMock()
    mock_smtp_context.__enter__.return_value = mock_smtp_instance

    with patch("smtplib.SMTP", return_value=mock_smtp_context) as mock_smtp_class:
        success = provider.send_email(
            to_email="learner@example.com",
            subject="Đặt lại mật khẩu Mascot",
            html_content="<p>Test HTML</p>",
            text_content="Test Text",
        )

        assert success is True
        mock_smtp_class.assert_called_once_with("smtp.gmail.com", 587, timeout=5.0)
        mock_smtp_instance.ehlo.assert_called()
        mock_smtp_instance.starttls.assert_called_once()
        mock_smtp_instance.login.assert_called_once_with(
            "mascot_sender@gmail.com", "abcd-efgh-ijkl-mnop"
        )
        assert mock_smtp_instance.send_message.call_count == 1
        sent_msg = mock_smtp_instance.send_message.call_args[0][0]
        assert sent_msg["To"] == "learner@example.com"
        assert sent_msg["From"] == "Mascot Support <mascot_sender@gmail.com>"
        assert sent_msg["Subject"] == "Đặt lại mật khẩu Mascot"


def test_gmail_smtp_provider_retry_and_safe_failure() -> None:
    provider = GmailSmtpEmailProvider(
        host="smtp.gmail.com",
        port=587,
        username="mascot_sender@gmail.com",
        app_password="abcd-efgh-ijkl-mnop",
    )

    mock_smtp_instance = MagicMock()
    mock_smtp_instance.login.side_effect = smtplib.SMTPAuthenticationError(535, b"Authentication failed")
    mock_smtp_context = MagicMock()
    mock_smtp_context.__enter__.return_value = mock_smtp_instance

    with patch("smtplib.SMTP", return_value=mock_smtp_context):
        success = provider.send_email(
            to_email="learner@example.com",
            subject="Đặt lại mật khẩu Mascot",
            html_content="<p>Test HTML</p>",
            text_content="Test Text",
        )
        # Should gracefully return False without raising unhandled exception
        assert success is False
        # Retried once (2 total attempts)
        assert mock_smtp_instance.login.call_count == 2


def test_gmail_smtp_config_validation() -> None:
    # 1. Missing username & password raises validation error
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            database_url="postgresql+psycopg://user:pass@localhost:5432/db",
            jwt_secret_key="a" * 32,
            email_provider="gmail_smtp",
        )
    assert "SMTP_USERNAME and SMTP_APP_PASSWORD are required" in str(exc_info.value)

    # 2. Providing valid SMTP config succeeds
    valid_settings = Settings(
        database_url="postgresql+psycopg://user:pass@localhost:5432/db",
        jwt_secret_key="a" * 32,
        email_provider="gmail_smtp",
        smtp_username="sender@gmail.com",
        smtp_app_password="valid-app-password",
    )
    assert valid_settings.email_provider == "gmail_smtp"
    assert valid_settings.smtp_host == "smtp.gmail.com"
    assert valid_settings.smtp_port == 587


def test_get_email_provider_instantiates_gmail_smtp() -> None:
    mock_settings = MagicMock()
    mock_settings.email_provider = "gmail_smtp"
    mock_settings.smtp_host = "smtp.gmail.com"
    mock_settings.smtp_port = 587
    mock_settings.smtp_username = "bot@gmail.com"
    mock_settings.smtp_app_password.get_secret_value.return_value = "secret-pass"
    mock_settings.email_from = "Mascot <bot@gmail.com>"
    mock_settings.smtp_timeout_seconds = 10.0

    # Ensure no override is active
    set_email_provider(None)
    with patch("app.services.email.get_settings", return_value=mock_settings):
        provider = get_email_provider()
        assert isinstance(provider, GmailSmtpEmailProvider)
        assert provider._username == "bot@gmail.com"
        assert provider._app_password == "secret-pass"
