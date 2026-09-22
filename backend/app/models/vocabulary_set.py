from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.learning_track import LearningTrack
    from app.models.vocabulary_entry import VocabularyEntry


class VocabularySet(Base):
    __tablename__ = "vocabulary_sets"
    __table_args__ = (
        UniqueConstraint(
            "learning_track_id", "level_code", "topic", name="uq_vocab_sets_track_level_topic"
        ),
        CheckConstraint("length(trim(name)) > 0", name="ck_vocab_sets_name_not_blank"),
        CheckConstraint("length(trim(level_code)) > 0", name="ck_vocab_sets_level_not_blank"),
        CheckConstraint("length(trim(topic)) > 0", name="ck_vocab_sets_topic_not_blank"),
        CheckConstraint("order_index >= 0", name="ck_vocab_sets_order_nonnegative"),
        Index(
            "ix_vocab_sets_track_level_active",
            "learning_track_id",
            "level_code",
            "is_active",
        ),
        Index("ix_vocab_sets_topic", "topic"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    learning_track_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("learning_tracks.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    level_code: Mapped[str] = mapped_column(String(32), nullable=False)
    topic: Mapped[str] = mapped_column(String(120), nullable=False)
    order_index: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
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

    learning_track: Mapped["LearningTrack"] = relationship(
        back_populates="vocabulary_sets"
    )
    entries: Mapped[list["VocabularyEntry"]] = relationship(
        back_populates="vocabulary_set",
        order_by="VocabularyEntry.order_index",
    )
