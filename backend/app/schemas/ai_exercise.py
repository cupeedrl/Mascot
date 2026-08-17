from __future__ import annotations

import unicodedata
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.exercise import ExerciseResponse, ExerciseType


def _clean_required(value: str) -> str:
    cleaned = unicodedata.normalize("NFKC", value.strip())
    if not cleaned:
        raise ValueError("must not be blank")
    return cleaned


def _normalized(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value.strip()).split()).casefold()


class AIExerciseGenerationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vocabulary_ids: list[uuid.UUID] = Field(min_length=1, max_length=20)
    exercise_type: ExerciseType
    count: int = Field(ge=1, le=10)

    @model_validator(mode="after")
    def validate_selection(self) -> "AIExerciseGenerationRequest":
        if len(set(self.vocabulary_ids)) != len(self.vocabulary_ids):
            raise ValueError("vocabulary_ids must be unique")
        if self.count > len(self.vocabulary_ids):
            raise ValueError("count cannot exceed selected vocabulary count")
        return self


class AIExerciseOption(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=8)
    text: str = Field(min_length=1, max_length=255)

    @field_validator("id")
    @classmethod
    def normalize_id(cls, value: str) -> str:
        return _clean_required(value).upper()

    @field_validator("text")
    @classmethod
    def clean_text(cls, value: str) -> str:
        return _clean_required(value)


class AIMultipleChoiceCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    exercise_type: Literal["multiple_choice"]
    prompt: str = Field(min_length=1, max_length=2000)
    options: list[AIExerciseOption] = Field(min_length=4, max_length=4)
    correct_answer: str = Field(min_length=1, max_length=8)
    explanation: str = Field(min_length=1, max_length=1000)
    source_vocabulary_ids: list[uuid.UUID] = Field(min_length=1, max_length=20)

    @field_validator("prompt", "explanation")
    @classmethod
    def clean_text(cls, value: str) -> str:
        return _clean_required(value)

    @field_validator("correct_answer")
    @classmethod
    def normalize_answer(cls, value: str) -> str:
        return _clean_required(value).upper()

    @model_validator(mode="after")
    def validate_options_and_sources(self) -> "AIMultipleChoiceCandidate":
        option_ids = [option.id for option in self.options]
        if set(option_ids) != {"A", "B", "C", "D"}:
            raise ValueError("option IDs must be exactly A, B, C, and D")
        if self.correct_answer not in option_ids:
            raise ValueError("correct_answer must identify an option")
        option_texts = [_normalized(option.text) for option in self.options]
        if len(set(option_texts)) != len(option_texts):
            raise ValueError("option texts must be unique")
        if len(set(self.source_vocabulary_ids)) != len(self.source_vocabulary_ids):
            raise ValueError("source_vocabulary_ids must be unique")
        return self


class AIFillInBlankCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    exercise_type: Literal["fill_in_blank"]
    prompt: str = Field(min_length=1, max_length=2000)
    correct_answer: str = Field(min_length=1, max_length=255)
    accepted_answers: list[str] = Field(min_length=1, max_length=5)
    explanation: str = Field(min_length=1, max_length=1000)
    source_vocabulary_ids: list[uuid.UUID] = Field(min_length=1, max_length=20)

    @field_validator("prompt", "correct_answer", "explanation")
    @classmethod
    def clean_text(cls, value: str) -> str:
        return _clean_required(value)

    @field_validator("accepted_answers")
    @classmethod
    def clean_answers(cls, values: list[str]) -> list[str]:
        cleaned = [_clean_required(value) for value in values]
        if len({_normalized(value) for value in cleaned}) != len(cleaned):
            raise ValueError("accepted_answers must be unique")
        return cleaned

    @model_validator(mode="after")
    def validate_answer_and_sources(self) -> "AIFillInBlankCandidate":
        if _normalized(self.correct_answer) not in {
            _normalized(answer) for answer in self.accepted_answers
        }:
            raise ValueError("accepted_answers must include correct_answer")
        if "______" not in self.prompt:
            raise ValueError("prompt must contain a six-underscore blank")
        if len(set(self.source_vocabulary_ids)) != len(self.source_vocabulary_ids):
            raise ValueError("source_vocabulary_ids must be unique")
        return self


class AIMultipleChoiceBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    exercises: list[AIMultipleChoiceCandidate] = Field(min_length=1, max_length=10)


class AIFillInBlankBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    exercises: list[AIFillInBlankCandidate] = Field(min_length=1, max_length=10)


class AIExerciseGenerationResponse(BaseModel):
    items: list[ExerciseResponse]
    created_count: int
