from __future__ import annotations

import json
import logging
import smtplib
import ssl
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class EmailProvider(ABC):
    @abstractmethod
    def send_email(
        self,
        *,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: str,
    ) -> bool:
        pass


class ConsoleEmailProvider(EmailProvider):
    def send_email(
        self,
        *,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: str,
    ) -> bool:
        logger.info(
            "[ConsoleEmailProvider] Mock Email Sent | To: %s | Subject: %s\nText:\n%s",
            to_email,
            subject,
            text_content,
        )
        return True


class TestEmailProvider(EmailProvider):
    def __init__(self) -> None:
        self.sent_emails: list[dict[str, Any]] = []

    def send_email(
        self,
        *,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: str,
    ) -> bool:
        self.sent_emails.append(
            {
                "to": to_email,
                "subject": subject,
                "html": html_content,
                "text": text_content,
            }
        )
        return True

    def clear(self) -> None:
        self.sent_emails.clear()


class ResendEmailProvider(EmailProvider):
    def __init__(self, api_key: str, from_address: str) -> None:
        # Strip all whitespace/newlines to prevent header formatting errors
        self._api_key = api_key.strip()
        self._from_address = from_address.strip()

    def send_email(
        self,
        *,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: str,
    ) -> bool:
        if not self._api_key:
            logger.error("password_reset_email_send_failed: provider=resend error_type=MissingApiKey")
            return False

        url = "https://api.resend.com/emails"
        payload = {
            "from": self._from_address,
            "to": [to_email],
            "subject": subject,
            "html": html_content,
            "text": text_content,
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
                "User-Agent": "Mascot-App/1.0",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=10.0) as resp:
                status_code = resp.getcode()
                if 200 <= status_code < 300:
                    logger.info("Email sent successfully via Resend to %s", to_email)
                    return True
                logger.warning("password_reset_email_send_failed: provider=resend status_code=%s", status_code)
                return False
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
            logger.error("password_reset_email_send_failed: provider=resend error_type=%s", type(exc).__name__)
            return False
        except Exception as exc:
            logger.error("password_reset_email_send_failed: provider=resend error_type=%s", type(exc).__name__)
            return False


class GmailSmtpEmailProvider(EmailProvider):
    def __init__(
        self,
        *,
        host: str = "smtp.gmail.com",
        port: int = 587,
        username: str,
        app_password: str,
        from_address: str | None = None,
        timeout: float = 10.0,
    ) -> None:
        self._host = host.strip()
        self._port = port
        self._username = username.strip()
        self._app_password = app_password.strip()
        self._from_address = (from_address or username).strip()
        self._timeout = timeout

    def _send_attempt(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: str,
    ) -> None:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self._from_address
        msg["To"] = to_email

        # Plain text fallback first, HTML second for MIME standard
        part_text = MIMEText(text_content, "plain", "utf-8")
        part_html = MIMEText(html_content, "html", "utf-8")
        msg.attach(part_text)
        msg.attach(part_html)

        context = ssl.create_default_context()
        with smtplib.SMTP(self._host, self._port, timeout=self._timeout) as server:
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
            server.login(self._username, self._app_password)
            server.send_message(msg)

    def send_email(
        self,
        *,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: str,
    ) -> bool:
        if not self._username or not self._app_password:
            logger.error("password_reset_email_send_failed: provider=gmail_smtp error_type=MissingCredentials")
            return False

        max_attempts = 2
        for attempt in range(1, max_attempts + 1):
            try:
                self._send_attempt(to_email, subject, html_content, text_content)
                logger.info("Email sent successfully via Gmail SMTP to %s", to_email)
                return True
            except (smtplib.SMTPException, OSError, TimeoutError) as exc:
                if attempt < max_attempts:
                    logger.warning(
                        "password_reset_email_send_failed: provider=gmail_smtp attempt=%s/%s error_type=%s. Retrying...",
                        attempt,
                        max_attempts,
                        type(exc).__name__,
                    )
                    continue
                logger.error(
                    "password_reset_email_send_failed: provider=gmail_smtp error_type=%s",
                    type(exc).__name__,
                )
                return False
            except Exception as exc:
                logger.error(
                    "password_reset_email_send_failed: provider=gmail_smtp error_type=%s",
                    type(exc).__name__,
                )
                return False
        return False


# Global test provider singleton for test overrides
test_email_provider = TestEmailProvider()
_override_email_provider: EmailProvider | None = None


def set_email_provider(provider: EmailProvider | None) -> None:
    global _override_email_provider
    _override_email_provider = provider


def get_email_provider() -> EmailProvider:
    if _override_email_provider is not None:
        return _override_email_provider
    settings = get_settings()
    if settings.email_provider == "test":
        return test_email_provider
    if settings.email_provider == "gmail_smtp" and settings.smtp_username and settings.smtp_app_password:
        return GmailSmtpEmailProvider(
            host=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_username,
            app_password=settings.smtp_app_password.get_secret_value(),
            from_address=settings.email_from,
            timeout=settings.smtp_timeout_seconds,
        )
    if settings.email_provider == "resend" and settings.resend_api_key:
        return ResendEmailProvider(
            api_key=settings.resend_api_key.get_secret_value(),
            from_address=settings.email_from,
        )
    return ConsoleEmailProvider()


def build_password_reset_email_html(reset_url: str, expire_minutes: int) -> str:
    return f"""<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="utf-8">
  <title>Đặt lại mật khẩu Mascot</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f8fafc; color: #1e293b; margin: 0; padding: 24px; }}
    .container {{ max-width: 540px; margin: 0 auto; background: #ffffff; border-radius: 16px; border: 1px solid #e2e8f0; padding: 32px; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.03); }}
    .brand {{ font-size: 20px; font-weight: 800; color: #7c3aed; margin-bottom: 20px; }}
    h1 {{ font-size: 22px; font-weight: 700; color: #0f172a; margin-top: 0; }}
    p {{ font-size: 15px; line-height: 1.6; color: #475569; margin: 16px 0; }}
    .btn-wrap {{ margin: 28px 0; }}
    .btn {{ display: inline-block; background-color: #7c3aed; color: #ffffff !important; text-decoration: none; padding: 12px 24px; font-size: 15px; font-weight: 700; border-radius: 10px; }}
    .note {{ font-size: 13.5px; color: #94a3b8; border-top: 1px solid #f1f5f9; padding-top: 18px; margin-top: 28px; }}
    .link-alt {{ font-size: 13px; color: #7c3aed; word-break: break-all; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="brand">🐧 Mascot</div>
    <h1>Đặt lại mật khẩu của bạn</h1>
    <p>Chào bạn,</p>
    <p>Chúng tôi nhận được yêu cầu đặt lại mật khẩu cho tài khoản Mascot của bạn. Hãy bấm vào nút bên dưới để tiến hành tạo mật khẩu mới:</p>
    <div class="btn-wrap">
      <a href="{reset_url}" class="btn" target="_blank">Đặt lại mật khẩu</a>
    </div>
    <p>Liên kết này có hiệu lực trong vòng <strong>{expire_minutes} phút</strong>.</p>
    <p>Nếu bạn không thực hiện yêu cầu này, vui lòng bỏ qua email. Mật khẩu của bạn vẫn được an toàn.</p>
    <div class="note">
      <p>Nếu không bấm được vào nút trên, bạn có thể sao chép liên kết sau vào trình duyệt:</p>
      <p class="link-alt">{reset_url}</p>
    </div>
  </div>
</body>
</html>"""


def build_password_reset_email_text(reset_url: str, expire_minutes: int) -> str:
    return f"""Mascot - Đặt lại mật khẩu

Chào bạn,

Chúng tôi nhận được yêu cầu đặt lại mật khẩu cho tài khoản Mascot của bạn.
Vui lòng truy cập liên kết sau để đặt lại mật khẩu:
{reset_url}

Liên kết này có hiệu lực trong vòng {expire_minutes} phút.
Nếu bạn không yêu cầu đặt lại mật khẩu, vui lòng bỏ qua email này.

Đội ngũ Mascot
"""


def send_password_reset_email(to_email: str, raw_token: str) -> bool:
    settings = get_settings()
    base_url = settings.frontend_base_url.rstrip("/")
    reset_url = f"{base_url}/reset-password?token={raw_token}"
    expire_minutes = settings.password_reset_token_expire_minutes

    html_content = build_password_reset_email_html(reset_url, expire_minutes)
    text_content = build_password_reset_email_text(reset_url, expire_minutes)

    provider = get_email_provider()
    return provider.send_email(
        to_email=to_email,
        subject="Đặt lại mật khẩu Mascot",
        html_content=html_content,
        text_content=text_content,
    )
