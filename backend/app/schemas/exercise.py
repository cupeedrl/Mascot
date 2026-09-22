from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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


class ExerciseClozeBlank(BaseModel):
    model_config = ConfigDict(extra="forbid")

    number: int = Field(ge=1, le=4)
    options: list[ExerciseOption] = Field(min_length=4, max_length=4)


class ExerciseResponse(BaseModel):
    """Learner-safe exercise schema. Answer keys are intentionally absent."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    learning_track_id: uuid.UUID
    exercise_type: ExerciseType
    prompt: str
    options: list[ExerciseOption] | list[ExerciseClozeBlank] | None
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

    answer: str | None = Field(default=None, min_length=1, max_length=1000)
    answers: dict[str, str] | None = None

    @field_validator("answer")
    @classmethod
    def trim_answer(cls, value: str | None) -> str | None:
        return _trim_required(value) if value is not None else None

    @field_validator("answers")
    @classmethod
    def validate_answers(cls, value: dict[str, str] | None) -> dict[str, str] | None:
        if value is None:
            return None
        if set(value) != {"1", "2", "3", "4"}:
            raise ValueError("answers must contain exactly keys 1, 2, 3, and 4")
        return {key: _trim_required(answer).upper() for key, answer in value.items()}

    @field_validator("answers", mode="after")
    @classmethod
    def limit_answers(cls, value: dict[str, str] | None) -> dict[str, str] | None:
        if value is not None and any(len(answer) > 8 for answer in value.values()):
            raise ValueError("each answer must be at most 8 characters")
        return value

    @model_validator(mode="after")
    def require_one_answer_shape(self) -> "ExerciseAttemptCreate":
        if (self.answer is None) == (self.answers is None):
            raise ValueError("provide exactly one of answer or answers")
        return self


class ExerciseBlankResult(BaseModel):
    number: int
    is_correct: bool
    correct_answer: str
    explanation: str | None


class ExerciseAttemptResult(BaseModel):
    id: uuid.UUID
    exercise_id: uuid.UUID
    user_answer: str
    is_correct: bool
    correct_answer: str
    explanation: str | None
    completed_at: datetime
    correct_count: int | None = None
    total: int | None = None
    score_percent: int | None = None
    results: list[ExerciseBlankResult] = Field(default_factory=list)


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
