from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import DUMMY_PASSWORD_HASH, hash_password, verify_password
from app.models.user import User
from app.schemas.auth import RegisterRequest


class DuplicateEmailError(Exception):
    """Raised when a normalized email is already registered."""


def normalize_email(email: str) -> str:
    return email.strip().lower()


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
