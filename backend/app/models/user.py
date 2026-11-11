from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Index, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("length(trim(email)) > 0", name="ck_users_email_not_blank"),
        CheckConstraint(
            "length(trim(normalized_email)) > 0",
            name="ck_users_normalized_email_not_blank",
        ),
        CheckConstraint(
            "length(trim(password_hash)) > 0",
            name="ck_users_password_hash_not_blank",
        ),
        CheckConstraint("role IN ('user', 'admin')", name="ck_users_role_valid"),
        CheckConstraint(
            "(username IS NULL) = (normalized_username IS NULL)",
            name="ck_users_username_pair",
        ),
        CheckConstraint(
            "display_name IS NULL OR length(trim(display_name)) > 0",
            name="ck_users_display_name_not_blank",
        ),
        Index(
            "uq_users_normalized_username",
            "normalized_username",
            unique=True,
            postgresql_where=text("normalized_username IS NOT NULL"),
            sqlite_where=text("normalized_username IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    normalized_email: Mapped[str] = mapped_column(
        String(320),
        nullable=False,
        unique=True,
        index=True,
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    # Optional for accounts created before usernames existed.
    username: Mapped[str | None] = mapped_column(String(30))
    normalized_username: Mapped[str | None] = mapped_column(String(30))
    display_name: Mapped[str | None] = mapped_column(String(80))
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="user",
        server_default=text("'user'"),
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
