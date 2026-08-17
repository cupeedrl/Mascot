from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.language import Language
    from app.models.vocabulary import Vocabulary
    from app.models.vocabulary_set import VocabularySet


class LearningTrack(Base):
    __tablename__ = "learning_tracks"
    __table_args__ = (
        UniqueConstraint("language_id", "code", name="uq_learning_tracks_language_code"),
        CheckConstraint(
            "length(trim(code)) > 0", name="ck_learning_tracks_code_not_blank"
        ),
        CheckConstraint(
            "code = lower(code)", name="ck_learning_tracks_code_lowercase"
        ),
        CheckConstraint(
            "length(trim(name)) > 0", name="ck_learning_tracks_name_not_blank"
        ),
        CheckConstraint(
            "length(trim(level_framework)) > 0",
            name="ck_learning_tracks_framework_not_blank",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    language_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("languages.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    level_framework: Mapped[str] = mapped_column(String(32), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
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

    language: Mapped["Language"] = relationship(back_populates="learning_tracks")
    vocabularies: Mapped[list["Vocabulary"]] = relationship(
        back_populates="learning_track"
    )
    vocabulary_sets: Mapped[list["VocabularySet"]] = relationship(
        back_populates="learning_track"
    )
