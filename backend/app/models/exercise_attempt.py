from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.exercise import Exercise


class ExerciseAttempt(Base):
    __tablename__ = "exercise_attempts"
    __table_args__ = (
        CheckConstraint(
            "length(trim(user_answer)) > 0",
            name="ck_exercise_attempts_user_answer_not_blank",
        ),
        CheckConstraint(
            "length(trim(correct_answer)) > 0",
            name="ck_exercise_attempts_correct_answer_not_blank",
        ),
        Index(
            "ix_exercise_attempts_user_completed",
            "user_id",
            text("completed_at DESC"),
        ),
        Index("ix_exercise_attempts_user_correct", "user_id", "is_correct"),
        Index("ix_exercise_attempts_exercise_id", "exercise_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    exercise_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("exercises.id", ondelete="RESTRICT"), nullable=False
    )
    user_answer: Mapped[str] = mapped_column(Text, nullable=False)
    # Snapshot semantics: this PLAN-approved column keeps the answer used when
    # the attempt was graded even if the exercise changes later.
    correct_answer: Mapped[str] = mapped_column(Text, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    exercise: Mapped["Exercise"] = relationship(back_populates="attempts")
