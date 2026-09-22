from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.exercise import Exercise
    from app.models.learning_track import LearningTrack
    from app.models.vocabulary_entry import VocabularyEntry


class Vocabulary(Base):
    __tablename__ = "vocabularies"
    __table_args__ = (
        CheckConstraint("length(trim(word)) > 0", name="ck_vocabularies_word_not_blank"),
        CheckConstraint(
            "length(trim(normalized_word)) > 0",
            name="ck_vocabularies_normalized_word_not_blank",
        ),
        CheckConstraint(
            "length(trim(part_of_speech)) > 0",
            name="ck_vocabularies_part_of_speech_not_blank",
        ),
        CheckConstraint(
            "length(trim(meaning)) > 0", name="ck_vocabularies_meaning_not_blank"
        ),
        CheckConstraint(
            "length(trim(translation)) > 0",
            name="ck_vocabularies_translation_not_blank",
        ),
        CheckConstraint(
            "learning_status IN ('new', 'learning', 'review', 'mastered')",
            name="ck_vocabularies_learning_status",
        ),
        CheckConstraint("review_count >= 0", name="ck_vocabularies_review_count"),
        CheckConstraint("correct_count >= 0", name="ck_vocabularies_correct_count"),
        CheckConstraint(
            "incorrect_count >= 0", name="ck_vocabularies_incorrect_count"
        ),
        CheckConstraint(
            "correct_count + incorrect_count <= review_count",
            name="ck_vocabularies_review_totals",
        ),
        Index("ix_vocab_user_created", "user_id", text("created_at DESC")),
        Index(
            "ix_vocab_user_track_status",
            "user_id",
            "learning_track_id",
            "learning_status",
        ),
        Index(
            "ix_vocab_user_track_level",
            "user_id",
            "learning_track_id",
            "level_code",
        ),
        Index(
            "ix_vocab_user_track_topic",
            "user_id",
            "learning_track_id",
            "topic",
        ),
        Index("ix_vocab_user_normalized", "user_id", "learning_track_id", "normalized_word"),
        Index(
            "uq_vocab_user_source_entry",
            "user_id",
            "source_vocabulary_entry_id",
            unique=True,
            postgresql_where=text("source_vocabulary_entry_id IS NOT NULL"),
        ),
        Index(
            "ix_vocab_user_next_review",
            "user_id",
            "next_review_at",
            postgresql_where=text("next_review_at IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    learning_track_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("learning_tracks.id", ondelete="RESTRICT"), nullable=False
    )
    source_vocabulary_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("vocabulary_entries.id", ondelete="SET NULL"), nullable=True
    )
    word: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_word: Mapped[str] = mapped_column(String(255), nullable=False)
    ipa: Mapped[str | None] = mapped_column(String(100), nullable=True)
    part_of_speech: Mapped[str] = mapped_column(String(64), nullable=False)
    meaning: Mapped[str] = mapped_column(Text, nullable=False)
    translation: Mapped[str] = mapped_column(Text, nullable=False)
    translation_language_code: Mapped[str] = mapped_column(
        String(16), nullable=False, default="vi", server_default="vi"
    )
    example_sentences: Mapped[list[str]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=list,
        server_default=text("'[]'"),
    )
    level_code: Mapped[str] = mapped_column(String(32), nullable=False)
    topic: Mapped[str | None] = mapped_column(String(120))
    learning_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="new", server_default="new"
    )
    review_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    correct_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    incorrect_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_review_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    learning_track: Mapped["LearningTrack"] = relationship(
        back_populates="vocabularies"
    )
    source_vocabulary_entry: Mapped["VocabularyEntry | None"] = relationship()
    exercises: Mapped[list["Exercise"]] = relationship(
        secondary="exercise_vocabularies",
        back_populates="vocabularies",
    )
