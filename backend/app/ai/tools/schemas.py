from __future__ import annotations

from uuid import UUID
from datetime import datetime, date
from pydantic import BaseModel, ConfigDict, Field

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
