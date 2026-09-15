from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class RecentVocabularyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    word: str
    meaning: str
    level_code: str
    learning_status: str
    created_at: datetime


class DashboardResponse(BaseModel):
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
    recently_added_vocabulary: list[RecentVocabularyResponse]


class StudyCalendarResponse(BaseModel):
    year: int
    month: int
    today: date
    active_dates: list[date]
    current_streak: int
    longest_streak: int
    learning_track_id: uuid.UUID | None
