from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.core.security import DUMMY_PASSWORD_HASH, hash_password, verify_password
from app.models.password_reset_token import PasswordResetToken
from app.models.user import User
from app.schemas.auth import RegisterRequest


class DuplicateEmailError(Exception):
    """Raised when a normalized email is already registered."""


class InvalidResetTokenError(Exception):
    """Raised when a password reset token is invalid, expired, or already used."""


def normalize_email(email: str) -> str:
    return email.strip().lower()


def hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.strip().encode("utf-8")).hexdigest()


def register_user(db: Session, registration: RegisterRequest) -> User:
    email = str(registration.email).strip()
    normalized_email = normalize_email(email)

    existing_user = db.scalar(
        select(User).where(User.normalized_email == normalized_email)
    )
    if existing_user is not None:
        raise DuplicateEmailError

    user = User(
        email=email,
        normalized_email=normalized_email,
        password_hash=hash_password(registration.password),
    )
    db.add(user)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise DuplicateEmailError from exc

    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    user = db.scalar(
        select(User).where(User.normalized_email == normalize_email(email))
    )

    password_hash = user.password_hash if user is not None else DUMMY_PASSWORD_HASH
    password_matches = verify_password(password, password_hash)

    if user is None or not password_matches or not user.is_active:
        return None
    return user


def create_password_reset_token(db: Session, email: str) -> str | None:
    """Create a new password reset token for the user if exists.

    Returns the raw token (to be sent via email) or None if user not found.
    Plaintext token is never stored in the database.
    """
    normalized = normalize_email(email)
    user = db.scalar(
        select(User).where(User.normalized_email == normalized, User.is_active.is_(True))
    )
    if user is None:
        return None

    now = datetime.now(timezone.utc)
    settings = get_settings()

    # Invalidate any prior unexpired active tokens for this user atomically
    db.execute(
        update(PasswordResetToken)
        .where(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used_at.is_(None),
        )
        .values(used_at=now)
    )

    raw_token = secrets.token_urlsafe(32)
    token_entity = PasswordResetToken(
        user_id=user.id,
        token_hash=hash_token(raw_token),
        expires_at=now + timedelta(minutes=settings.password_reset_token_expire_minutes),
        created_at=now,
    )
    db.add(token_entity)
    db.commit()
    return raw_token


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def reset_password_with_token(db: Session, token: str, new_password: str) -> None:
    """Reset user password using a valid, unexpired reset token.

    Atomically locks the token row and consumes it to ensure strictly one-time execution.
    """
    token_hashed = hash_token(token)
    now = datetime.now(timezone.utc)

    # 1. Acquire exclusive lock on the active (unused) token row
    reset_token = db.scalar(
        select(PasswordResetToken)
        .options(selectinload(PasswordResetToken.user))
        .where(
            PasswordResetToken.token_hash == token_hashed,
            PasswordResetToken.used_at.is_(None),
        )
        .with_for_update()
    )

    # 2. Strict verification: must exist, be unused, and unexpired
    if reset_token is None or _as_utc(reset_token.expires_at) <= now:
        raise InvalidResetTokenError("Đường dẫn đặt lại mật khẩu không hợp lệ hoặc đã hết hạn.")

    user = reset_token.user
    if user is None or not user.is_active:
        raise InvalidResetTokenError("Đường dẫn đặt lại mật khẩu không hợp lệ hoặc đã hết hạn.")

    # 3. Update user password and mark current token used
    user.password_hash = hash_password(new_password)
    reset_token.used_at = now

    # 4. Invalidate all other active reset tokens for this user
    other_tokens = list(
        db.scalars(
            select(PasswordResetToken).where(
                PasswordResetToken.user_id == user.id,
                PasswordResetToken.id != reset_token.id,
                PasswordResetToken.used_at.is_(None),
            )
        )
    )
    for other in other_tokens:
        other.used_at = now

    # 5. Atomically commit all changes
    db.commit()
