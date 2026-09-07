from __future__ import annotations

from uuid import UUID
from datetime import datetime, date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.services.normalization import clean_topic

# ----------------------------------------------------------------------
# Argument Schemas
# ----------------------------------------------------------------------
class GetLearningStatsArgs(BaseModel):
    """No client‑supplied arguments – kept for symmetry with other tools."""
    model_config = ConfigDict(extra="forbid")


class GetDueVocabArgs(BaseModel):
    """Bounded limit using native Pydantic field constraints."""
    limit: int = Field(default=20, ge=1, le=100, description="Maximum items to return")
    model_config = ConfigDict(extra="forbid")


class AddVocabularyArgs(BaseModel):
    """Strict model-authored proposal; identity and track are backend-owned."""

    word: str = Field(min_length=1, max_length=255)
    ipa: str | None = Field(default=None, max_length=100)
    part_of_speech: str = Field(min_length=1, max_length=64)
    meaning: str = Field(min_length=1, max_length=4000)
    translation: str = Field(min_length=1, max_length=2000)
    translation_language_code: str = Field(default="vi", min_length=2, max_length=16)
    example_sentences: list[str] = Field(default_factory=list, max_length=1)
    level_code: Literal["A1", "A2", "B1", "B2", "C1", "C2"]
    topic: str | None = Field(default="Khác", max_length=120)

    model_config = ConfigDict(extra="forbid")

    @field_validator("word", "part_of_speech", "meaning", "translation")
    @classmethod
    def trim_required(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("must not be blank")
        return trimmed

    @field_validator("ipa")
    @classmethod
    def normalize_ipa(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None

    @field_validator("translation_language_code")
    @classmethod
    def normalize_language_code(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("example_sentences")
    @classmethod
    def validate_examples(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values]
        if any(not value or len(value) > 500 for value in cleaned):
            raise ValueError("example sentence must contain 1 to 500 characters")
        return cleaned

    @field_validator("topic")
    @classmethod
    def normalize_topic(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return "Khác"
        return clean_topic(value) or "Khác"


# ----------------------------------------------------------------------
# Result Item Models
# ----------------------------------------------------------------------
class RecentVocabularyItem(BaseModel):
    id: UUID
    word: str
    meaning: str
    translation: str
    created_at: datetime

    model_config = ConfigDict(extra="forbid")


class VocabularyItem(BaseModel):
    id: UUID
    word: str
    meaning: str
    translation: str
    learning_status: str
    next_review_at: datetime | None = None
    last_reviewed_at: datetime | None = None

    model_config = ConfigDict(extra="forbid")


# ----------------------------------------------------------------------
# Result Schemas
# ----------------------------------------------------------------------
class LearningStatsResult(BaseModel):
    total_vocabulary: int
    new_words: int
    learning_words: int
    review_words: int
    mastered_words: int
    words_due_for_review: int
    exercises_completed: int
    correct_exercise_attempts: int
    incorrect_exercise_attempts: int
    exercise_accuracy: float
    current_streak: int
    longest_streak: int
    recent_active_dates: list[date]
    recent_vocabulary: list[RecentVocabularyItem]

    model_config = ConfigDict(extra="forbid")


class DueVocabularyResult(BaseModel):
    items: list[VocabularyItem]
    total: int
    limit: int

    model_config = ConfigDict(extra="forbid")


class AddVocabularyResult(BaseModel):
    id: UUID
    word: str
    meaning: str
    translation: str
    level_code: str
    topic: str | None
    learning_status: str

    model_config = ConfigDict(from_attributes=True, extra="forbid")
