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
    from app.models.vocabulary_set import VocabularySet


class VocabularyEntry(Base):
    __tablename__ = "vocabulary_entries"
    __table_args__ = (
        CheckConstraint("length(trim(word)) > 0", name="ck_vocab_entries_word_not_blank"),
        CheckConstraint(
            "length(trim(normalized_word)) > 0", name="ck_vocab_entries_normalized_not_blank"
        ),
        CheckConstraint(
            "length(trim(part_of_speech)) > 0", name="ck_vocab_entries_pos_not_blank"
        ),
        CheckConstraint(
            "length(trim(meaning)) > 0", name="ck_vocab_entries_meaning_not_blank"
        ),
        CheckConstraint(
            "length(trim(translation)) > 0", name="ck_vocab_entries_translation_not_blank"
        ),
        CheckConstraint("order_index >= 0", name="ck_vocab_entries_order_nonnegative"),
        Index("ix_vocab_entries_set_order", "vocabulary_set_id", "order_index"),
        Index("ix_vocab_entries_normalized", "normalized_word"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    vocabulary_set_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("vocabulary_sets.id", ondelete="CASCADE"), nullable=False
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
    order_index: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
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

    vocabulary_set: Mapped["VocabularySet"] = relationship(back_populates="entries")
