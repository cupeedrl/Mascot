from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.catalog import LearningTrackResponse
from app.services.normalization import clean_topic

CEFRLevel = Literal["A1", "A2", "B1", "B2", "C1", "C2"]
LearningStatus = Literal["new", "learning", "review", "mastered"]


def _trim_required(value: str) -> str:
    trimmed = value.strip()
    if not trimmed:
        raise ValueError("must not be blank")
    return trimmed


def _clean_examples(examples: list[str]) -> list[str]:
    cleaned: list[str] = []
    for example in examples:
        trimmed = example.strip()
        if not trimmed:
            raise ValueError("example sentences must not be blank")
        if len(trimmed) > 500:
            raise ValueError("each example sentence must be at most 500 characters")
        cleaned.append(trimmed)
    return cleaned


class VocabularyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    learning_track_id: uuid.UUID
    word: str = Field(min_length=1, max_length=255)
    part_of_speech: str = Field(min_length=1, max_length=64)
    meaning: str = Field(min_length=1, max_length=4000)
    translation: str = Field(min_length=1, max_length=2000)
    translation_language_code: str = Field(default="vi", min_length=2, max_length=16)
    example_sentences: list[str] = Field(default_factory=list, max_length=1)
    level_code: CEFRLevel
    topic: str | None = Field(default=None, max_length=120)
    learning_status: LearningStatus = "new"

    @field_validator("word", "part_of_speech", "meaning", "translation")
    @classmethod
    def trim_required_fields(cls, value: str) -> str:
        return _trim_required(value)

    @field_validator("translation_language_code")
    @classmethod
    def normalize_translation_language(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("must not be blank")
        return normalized

    @field_validator("example_sentences")
    @classmethod
    def validate_examples(cls, value: list[str]) -> list[str]:
        return _clean_examples(value)

    @field_validator("topic")
    @classmethod
    def normalize_topic(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return clean_topic(value)


class VocabularyUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    learning_track_id: uuid.UUID | None = None
    word: str | None = Field(default=None, min_length=1, max_length=255)
    part_of_speech: str | None = Field(default=None, min_length=1, max_length=64)
    meaning: str | None = Field(default=None, min_length=1, max_length=4000)
    translation: str | None = Field(default=None, min_length=1, max_length=2000)
    translation_language_code: str | None = Field(default=None, min_length=2, max_length=16)
    example_sentences: list[str] | None = Field(default=None, max_length=1)
    level_code: CEFRLevel | None = None
    topic: str | None = Field(default=None, max_length=120)
    learning_status: LearningStatus | None = None

    @model_validator(mode="after")
    def reject_null_for_required_fields(self) -> "VocabularyUpdate":
        nullable = {"topic"}
        for field_name in self.model_fields_set - nullable:
            if getattr(self, field_name) is None:
                raise ValueError(f"{field_name} must not be null")
        return self

    @field_validator("word", "part_of_speech", "meaning", "translation")
    @classmethod
    def trim_optional_required_fields(cls, value: str | None) -> str | None:
        return None if value is None else _trim_required(value)

    @field_validator("translation_language_code")
    @classmethod
    def normalize_optional_translation_language(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("must not be blank")
        return normalized

    @field_validator("example_sentences")
    @classmethod
    def validate_optional_examples(cls, value: list[str] | None) -> list[str] | None:
        return None if value is None else _clean_examples(value)

    @field_validator("topic")
    @classmethod
    def normalize_optional_topic(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return clean_topic(value)


class TopicSuggestion(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    vocabulary_count: int


class TopicSuggestionListResponse(BaseModel):
    items: list[TopicSuggestion]


class TopicRenameRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    old_topic: str = Field(min_length=1, max_length=120)
    new_topic: str = Field(min_length=1, max_length=120)

    @field_validator("old_topic", "new_topic")
    @classmethod
    def clean_topics(cls, value: str) -> str:
        cleaned = clean_topic(value)
        if cleaned is None:
            raise ValueError("topic must not be blank")
        return cleaned


class TopicRemoveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topic: str = Field(min_length=1, max_length=120)

    @field_validator("topic")
    @classmethod
    def clean_requested_topic(cls, value: str) -> str:
        cleaned = clean_topic(value)
        if cleaned is None:
            raise ValueError("topic must not be blank")
        return cleaned


class TopicMutationResponse(BaseModel):
    updated_count: int


class VocabularySourceSetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    level_code: str
    topic: str


class VocabularySourceEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    vocabulary_set: VocabularySourceSetResponse


class VocabularyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    learning_track_id: uuid.UUID
    learning_track: LearningTrackResponse
    source_vocabulary_entry_id: uuid.UUID | None
    source_vocabulary_entry: VocabularySourceEntryResponse | None
    word: str
    normalized_word: str
    part_of_speech: str
    meaning: str
    translation: str
    translation_language_code: str
    example_sentences: list[str]
    level_code: str
    topic: str | None
    learning_status: str
    review_count: int
    correct_count: int
    incorrect_count: int
    last_reviewed_at: datetime | None
    next_review_at: datetime | None
    created_at: datetime
    updated_at: datetime

    @field_validator("example_sentences")
    @classmethod
    def expose_at_most_one_example(cls, value: list[str]) -> list[str]:
        return value[:1]


class VocabularyListResponse(BaseModel):
    items: list[VocabularyResponse]
    page: int
    page_size: int
    total: int
    total_pages: int
