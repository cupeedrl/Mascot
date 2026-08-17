from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

ExerciseType = Literal["multiple_choice", "fill_in_blank"]


def _trim_required(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("must not be blank")
    return cleaned


class ExerciseOption(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=8)
    text: str = Field(min_length=1, max_length=500)

    @field_validator("id", "text")
    @classmethod
    def trim_fields(cls, value: str) -> str:
        return _trim_required(value)


class ExerciseResponse(BaseModel):
    """Learner-safe exercise schema. Answer keys are intentionally absent."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    learning_track_id: uuid.UUID
    exercise_type: ExerciseType
    prompt: str
    options: list[ExerciseOption] | None
    source: Literal["manual", "ai"]
    created_at: datetime


class ExerciseListResponse(BaseModel):
    items: list[ExerciseResponse]
    page: int
    page_size: int
    total: int
    total_pages: int


class ExerciseAttemptCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str = Field(min_length=1, max_length=1000)

    @field_validator("answer")
    @classmethod
    def trim_answer(cls, value: str) -> str:
        return _trim_required(value)


class ExerciseAttemptResult(BaseModel):
    id: uuid.UUID
    exercise_id: uuid.UUID
    user_answer: str
    is_correct: bool
    correct_answer: str
    explanation: str | None
    completed_at: datetime


class ExerciseAttemptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    exercise_id: uuid.UUID
    user_answer: str
    correct_answer: str
    is_correct: bool
    completed_at: datetime


class ExerciseAttemptListResponse(BaseModel):
    items: list[ExerciseAttemptResponse]
    page: int
    page_size: int
    total: int
    total_pages: int
