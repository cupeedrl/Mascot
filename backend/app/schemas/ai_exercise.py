from __future__ import annotations

import unicodedata
import uuid
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.exercise import ExerciseResponse, ExerciseType

ExerciseSourceMode = Literal["recent", "topic", "custom"]


def _clean_required(value: str) -> str:
    cleaned = unicodedata.normalize("NFKC", value.strip())
    if not cleaned:
        raise ValueError("must not be blank")
    return cleaned


def _normalized(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value.strip()).split()).casefold()


class AIExerciseGenerationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_mode: ExerciseSourceMode = "custom"
    topic: str | None = Field(default=None, max_length=120)
    vocabulary_ids: list[uuid.UUID] = Field(default_factory=list, max_length=1000)
    exercise_type: ExerciseType
    count: int = Field(default=5, ge=1, le=15)
    learning_track_id: uuid.UUID | None = None

    @field_validator("topic")
    @classmethod
    def clean_topic(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _clean_required(value)

    @model_validator(mode="after")
    def validate_selection(self) -> "AIExerciseGenerationRequest":
        if len(set(self.vocabulary_ids)) != len(self.vocabulary_ids):
            raise ValueError("vocabulary_ids must be unique")
        if self.source_mode == "custom":
            if not self.vocabulary_ids:
                raise ValueError("custom source requires vocabulary_ids")
            if self.topic is not None:
                raise ValueError("custom source does not accept topic")
        elif self.source_mode == "topic":
            if self.topic is None:
                raise ValueError("topic source requires topic")
            if self.vocabulary_ids:
                raise ValueError("topic source does not accept vocabulary_ids")
        elif self.topic is not None or self.vocabulary_ids:
            raise ValueError("recent source does not accept topic or vocabulary_ids")
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
    target_vocabulary_id: uuid.UUID

    @field_validator("prompt")
    @classmethod
    def normalize_sentence_blank(cls, value: str) -> str:
        cleaned = _clean_required(value)
        blanks = re.findall(r"_{3,}", cleaned)
        if len(blanks) != 1:
            raise ValueError("prompt must contain exactly one blank")
        # Groq can occasionally use five or six underscores even when the
        # intended question is an otherwise valid sentence cloze. Store one
        # canonical placeholder so downstream rendering and grading agree.
        return cleaned.replace(blanks[0], "_______", 1)

    @field_validator("explanation")
    @classmethod
    def clean_text(cls, value: str) -> str:
        return _clean_required(value)

    @field_validator("correct_answer")
    @classmethod
    def normalize_answer(cls, value: str) -> str:
        return _clean_required(value).upper()

    @model_validator(mode="after")
    def validate_options_and_prompt(self) -> "AIMultipleChoiceCandidate":
        option_ids = [option.id for option in self.options]
        if set(option_ids) != {"A", "B", "C", "D"}:
            raise ValueError("option IDs must be exactly A, B, C, and D")
        if self.correct_answer not in option_ids:
            raise ValueError("correct_answer must identify an option")
        option_texts = [_normalized(option.text) for option in self.options]
        if len(set(option_texts)) != len(option_texts):
            raise ValueError("option texts must be unique")
        if self.prompt.count("_______") != 1 or re.search(
            r"_{3,}", self.prompt.replace("_______", "", 1)
        ):
            raise ValueError("prompt must contain exactly one seven-underscore blank")
        if "\n" in self.prompt or not re.search(
            r"[.!?。！？][\"')\]]*$", self.prompt
        ):
            raise ValueError("prompt must be exactly one complete sentence")
        lowered = _normalized(self.prompt)
        if re.match(r"^(what does|which word(?:\s+\w+){0,3}\s+mean)", lowered):
            raise ValueError("prompt must be a contextual sentence-cloze question")
        return self


class AIFillInBlankItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    number: int = Field(ge=1, le=4)
    options: list[AIExerciseOption] = Field(min_length=4, max_length=4)
    correct_answer: str = Field(min_length=1, max_length=8)
    target_vocabulary_id: uuid.UUID
    explanation: str = Field(min_length=1, max_length=1000)

    @field_validator("explanation")
    @classmethod
    def clean_text(cls, value: str) -> str:
        return _clean_required(value)

    @field_validator("correct_answer")
    @classmethod
    def normalize_answer(cls, value: str) -> str:
        return _clean_required(value).upper()

    @model_validator(mode="after")
    def validate_options(self) -> "AIFillInBlankItem":
        option_ids = [option.id for option in self.options]
        if set(option_ids) != {"A", "B", "C", "D"}:
            raise ValueError("option IDs must be exactly A, B, C, and D")
        if self.correct_answer not in option_ids:
            raise ValueError("correct_answer must identify an option")
        option_texts = [_normalized(option.text) for option in self.options]
        if len(set(option_texts)) != len(option_texts):
            raise ValueError("option texts must be unique within a blank")
        return self


class AIFillInBlankCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    exercise_type: Literal["fill_in_blank"]
    title: str = Field(min_length=1, max_length=200)
    passage: str = Field(min_length=1, max_length=4000)
    blanks: list[AIFillInBlankItem] = Field(min_length=4, max_length=4)

    @field_validator("title", "passage")
    @classmethod
    def clean_text(cls, value: str) -> str:
        return _clean_required(value)

    @model_validator(mode="after")
    def validate_passage_and_blanks(self) -> "AIFillInBlankCandidate":
        if [blank.number for blank in self.blanks] != [1, 2, 3, 4]:
            raise ValueError("blank numbers must be exactly 1, 2, 3, and 4")
        for number in range(1, 5):
            placeholder = f"({number}) ______"
            if self.passage.count(placeholder) != 1:
                raise ValueError(f"passage must contain {placeholder} exactly once")
        without_expected = self.passage
        for number in range(1, 5):
            without_expected = without_expected.replace(f"({number}) ______", "", 1)
        if re.search(r"\(\d+\)\s*_{3,}|_{3,}", without_expected):
            raise ValueError("passage contains an unexpected blank")
        return self


class AIMultipleChoiceBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    exercises: list[AIMultipleChoiceCandidate] = Field(min_length=1, max_length=15)


class AIFillInBlankBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    exercises: list[AIFillInBlankCandidate] = Field(min_length=1, max_length=1)


class AIExerciseGenerationResponse(BaseModel):
    items: list[ExerciseResponse]
    created_count: int
    resumed: bool = False

