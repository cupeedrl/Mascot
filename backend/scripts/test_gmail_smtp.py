"""Quick interactive script to test Gmail SMTP sending.

Usage:
  python scripts/test_gmail_smtp.py <recipient_email>
"""

import os
import sys

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import get_settings
from app.services.email import GmailSmtpEmailProvider, build_password_reset_email_html, build_password_reset_email_text


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python scripts/test_gmail_smtp.py <recipient_email>")
        sys.exit(1)

    recipient = sys.argv[1]
    settings = get_settings()

    username = settings.smtp_username or os.getenv("SMTP_USERNAME")
    password = settings.smtp_app_password.get_secret_value() if settings.smtp_app_password else os.getenv("SMTP_APP_PASSWORD")

    if not username or not password:
        print("Error: SMTP_USERNAME and SMTP_APP_PASSWORD must be configured in environment or .env")
        sys.exit(1)

    print(f"Connecting to {settings.smtp_host}:{settings.smtp_port} as {username}...")
    provider = GmailSmtpEmailProvider(
        host=settings.smtp_host,
        port=settings.smtp_port,
        username=username,
        app_password=password,
        from_address=settings.email_from or username,
        timeout=15.0,
    )

    reset_url = f"{settings.frontend_base_url.rstrip('/')}/reset-password?token=test_token_verification_123"
    html = build_password_reset_email_html(reset_url, settings.password_reset_token_expire_minutes)
    text = build_password_reset_email_text(reset_url, settings.password_reset_token_expire_minutes)

    print(f"Sending test email to: {recipient}...")
    success = provider.send_email(
        to_email=recipient,
        subject="[Mascot Test] Đặt lại mật khẩu Mascot",
        html_content=html,
        text_content=text,
    )

    if success:
        print(" SUCCESS! Test email was sent successfully.")
    else:
        print(" FAILED! Check console error logs above.")


if __name__ == "__main__":
    main()
