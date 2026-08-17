from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    JSON,
    String,
    Table,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.exercise_attempt import ExerciseAttempt
    from app.models.learning_track import LearningTrack
    from app.models.vocabulary import Vocabulary


exercise_vocabularies = Table(
    "exercise_vocabularies",
    Base.metadata,
    Column(
        "exercise_id",
        ForeignKey("exercises.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "vocabulary_id",
        ForeignKey("vocabularies.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Index("ix_exercise_vocabularies_vocabulary_id", "vocabulary_id"),
)


class Exercise(Base):
    __tablename__ = "exercises"
    __table_args__ = (
        CheckConstraint(
            "exercise_type IN ('multiple_choice', 'fill_in_blank')",
            name="ck_exercises_type",
        ),
        CheckConstraint(
            "source IN ('manual', 'ai')",
            name="ck_exercises_source",
        ),
        CheckConstraint(
            "length(trim(prompt)) > 0",
            name="ck_exercises_prompt_not_blank",
        ),
        CheckConstraint(
            "length(trim(correct_answer)) > 0",
            name="ck_exercises_answer_not_blank",
        ),
        Index(
            "ix_exercises_user_track_created",
            "user_id",
            "learning_track_id",
            text("created_at DESC"),
        ),
        Index("ix_exercises_user_type", "user_id", "exercise_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    learning_track_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("learning_tracks.id", ondelete="RESTRICT"), nullable=False
    )
    exercise_type: Mapped[str] = mapped_column(String(32), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[list[dict[str, str]] | None] = mapped_column(
        JSON(none_as_null=True).with_variant(
            JSONB(none_as_null=True), "postgresql"
        ),
        nullable=True,
    )
    correct_answer: Mapped[str] = mapped_column(Text, nullable=False)
    accepted_answers: Mapped[list[str]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=list,
        server_default=text("'[]'"),
    )
    explanation: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(
        String(20), nullable=False, default="manual", server_default="manual"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    learning_track: Mapped["LearningTrack"] = relationship()
    vocabularies: Mapped[list["Vocabulary"]] = relationship(
        secondary=exercise_vocabularies,
        back_populates="exercises",
    )
    attempts: Mapped[list["ExerciseAttempt"]] = relationship(
        back_populates="exercise"
    )

    @property
    def source_vocabulary_ids(self) -> list[uuid.UUID]:
        return [item.id for item in self.vocabularies]
