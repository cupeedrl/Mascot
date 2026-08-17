from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.catalog import LearningTrackResponse


class VocabularyEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    word: str
    normalized_word: str
    part_of_speech: str
    meaning: str
    translation: str
    translation_language_code: str
    example_sentences: list[str]
    order_index: int
    is_added: bool = False

    @field_validator("example_sentences")
    @classmethod
    def expose_at_most_one_example(cls, value: list[str]) -> list[str]:
        return value[:1]


class VocabularySetListItem(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    level_code: str
    topic: str
    order_index: int
    learning_track: LearningTrackResponse
    entry_count: int
    added_count: int
    import_status: Literal["none", "partial", "all"]


class VocabularySetListResponse(BaseModel):
    items: list[VocabularySetListItem]
    page: int
    page_size: int
    total: int
    total_pages: int


class VocabularySetDetailResponse(VocabularySetListItem):
    entries: list[VocabularyEntryResponse]


class VocabularyEntryImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entry_ids: list[uuid.UUID] = Field(min_length=1, max_length=100)


class VocabularyImportResponse(BaseModel):
    created_count: int
    skipped_count: int
    imported_entry_ids: list[uuid.UUID]
