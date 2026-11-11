from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.core.security import DUMMY_PASSWORD_HASH, hash_password, verify_password
from app.models.email_verification_code import EmailVerificationCode
from app.models.password_reset_token import PasswordResetToken
from app.models.user import User
from app.schemas.auth import RegisterRequest


class DuplicateEmailError(Exception):
    """Raised when a normalized email is already registered."""


class InvalidResetTokenError(Exception):
    """Raised when a password reset token is invalid, expired, or already used."""


class AccountDisabledError(Exception):
    """Raised when credentials are valid but account is disabled."""


class DuplicateUsernameError(Exception):
    """Raised when a normalized username is already taken."""


class InvalidUsernameError(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


class EmailNotVerifiedError(Exception):
    """Raised when credentials are valid but the email is not confirmed yet."""

    def __init__(self, user: User) -> None:
        self.user = user
        super().__init__("email not verified")


class VerificationCodeError(Exception):
    """Raised for a wrong, expired or locked email verification code."""

    def __init__(self, code: str, remaining_attempts: int | None = None) -> None:
        self.code = code
        self.remaining_attempts = remaining_attempts
        super().__init__(code)


class AlreadyVerifiedError(Exception):
    """Raised when an account's email is already confirmed."""


USERNAME_PATTERN = re.compile(r"^[a-z][a-z0-9._]{2,29}$")
RESERVED_USERNAMES = frozenset(
    {"admin", "administrator", "root", "mascot", "support", "system", "api", "help", "null", "undefined", "me"}
)
VERIFICATION_MAX_ATTEMPTS = 5


def normalize_username(username: str) -> str:
    return username.strip().lower()


def username_problem(db: Session, username: str) -> str | None:
    """Return why a username cannot be used ("invalid", "reserved", "taken") or None."""
    normalized = normalize_username(username)
    if not USERNAME_PATTERN.fullmatch(normalized) or normalized.endswith((".", "_")) or ".." in normalized:
        return "invalid"
    if normalized in RESERVED_USERNAMES:
        return "reserved"
    if db.scalar(select(User.id).where(User.normalized_username == normalized)) is not None:
        return "taken"
    return None


def _code_hash(user_id, code: str) -> str:
    secret = get_settings().jwt_secret_key.get_secret_value().encode("utf-8")
    return hmac.new(secret, f"{user_id}:{code}".encode("utf-8"), hashlib.sha256).hexdigest()


def create_email_verification_code(db: Session, user: User) -> str:
    """Replace the user's active code with a new 6-digit code and return it."""
    code = f"{secrets.randbelow(1_000_000):06d}"
    minutes = get_settings().email_verification_code_expire_minutes
    db.query(EmailVerificationCode).filter(EmailVerificationCode.user_id == user.id).delete()
    db.add(
        EmailVerificationCode(
            user_id=user.id,
            code_hash=_code_hash(user.id, code),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=minutes),
            attempts=0,
        )
    )
    db.commit()
    return code


def verify_email_code(db: Session, email: str, code: str) -> User:
    """Confirm a user's email. Unknown emails fail like a wrong code."""
    user = db.scalar(select(User).where(User.normalized_email == normalize_email(email)))
    if user is not None and user.email_verified_at is not None:
        raise AlreadyVerifiedError
    record = (
        db.scalar(select(EmailVerificationCode).where(EmailVerificationCode.user_id == user.id))
        if user is not None
        else None
    )
    if user is None or record is None:
        raise VerificationCodeError("INVALID_CODE", 0)
    if _as_utc(record.expires_at) <= datetime.now(timezone.utc):
        raise VerificationCodeError("CODE_EXPIRED")
    if record.attempts >= VERIFICATION_MAX_ATTEMPTS:
        raise VerificationCodeError("CODE_LOCKED")
    if not hmac.compare_digest(record.code_hash, _code_hash(user.id, code)):
        record.attempts += 1
        db.commit()
        remaining = VERIFICATION_MAX_ATTEMPTS - record.attempts
        raise VerificationCodeError("INVALID_CODE" if remaining else "CODE_LOCKED", remaining)
    user.email_verified_at = datetime.now(timezone.utc)
    db.delete(record)
    db.commit()
    db.refresh(user)
    return user


def user_needing_verification(db: Session, email: str) -> User | None:
    user = db.scalar(select(User).where(User.normalized_email == normalize_email(email)))
    if user is None or user.email_verified_at is not None or not user.is_active:
        return None
    return user


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

    username = None
    if registration.username is not None:
        problem = username_problem(db, registration.username)
        if problem == "taken":
            raise DuplicateUsernameError
        if problem is not None:
            raise InvalidUsernameError(problem)
        username = normalize_username(registration.username)

    require_verification = get_settings().require_email_verification
    user = User(
        email=email,
        normalized_email=normalized_email,
        password_hash=hash_password(registration.password),
        username=username,
        normalized_username=username,
        display_name=registration.display_name,
        email_verified_at=None if require_verification else datetime.now(timezone.utc),
    )
    db.add(user)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if username and db.scalar(select(User.id).where(User.normalized_username == username)):
            raise DuplicateUsernameError from exc
        raise DuplicateEmailError from exc

    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    """Check credentials. ``email`` may also be a username (no "@")."""
    login_name = email.strip()
    if "@" in login_name:
        condition = User.normalized_email == normalize_email(login_name)
    else:
        condition = User.normalized_username == normalize_username(login_name)
    user = db.scalar(select(User).where(condition))

    password_hash = user.password_hash if user is not None else DUMMY_PASSWORD_HASH
    password_matches = verify_password(password, password_hash)

    if user is None or not password_matches:
        return None

    if not user.is_active:
        raise AccountDisabledError

    if get_settings().require_email_verification and user.email_verified_at is None:
        raise EmailNotVerifiedError(user)

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


def validate_reset_token(db: Session, token: str) -> bool:
    """Verify if a password reset token is valid and unused without consuming it."""
    if not token or len(token.strip()) < 16:
        return False

    token_hashed = hash_token(token.strip())
    now = datetime.now(timezone.utc)

    reset_token = db.scalar(
        select(PasswordResetToken)
        .options(selectinload(PasswordResetToken.user))
        .where(
            PasswordResetToken.token_hash == token_hashed,
            PasswordResetToken.used_at.is_(None),
        )
    )

    if reset_token is None or _as_utc(reset_token.expires_at) <= now:
        return False

    user = reset_token.user
    if user is None or not user.is_active:
        return False

    return True


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
