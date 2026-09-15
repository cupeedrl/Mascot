from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.learning_track import LearningTrack
    from app.models.user import User


class UserLearningPreference(Base):
    __tablename__ = "user_learning_preferences"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "learning_track_id",
            name="uq_user_learning_preferences_user_track",
        ),
        CheckConstraint(
            "current_level_code IS NULL OR length(trim(current_level_code)) > 0",
            name="ck_user_learning_preferences_level_not_blank",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    learning_track_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("learning_tracks.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    current_level_code: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    user: Mapped["User"] = relationship()
    learning_track: Mapped["LearningTrack"] = relationship()
