from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class HskReleaseSummary(BaseModel):
    id: uuid.UUID
    code: str
    title: str
    status: str
    source_name: str
    source_version: str | None
    data_origin: str
    published_at: datetime | None


class HskTopicCard(BaseModel):
    id: uuid.UUID
    part: int | None = None
    part_count: int = 1
    name_zh: str
    name_vi: str | None
    subtopics: list[str]
    entry_count: int
    saved_count: int


class HskTopicGroup(BaseModel):
    id: uuid.UUID
    name_zh: str
    name_vi: str | None
    topics: list[HskTopicCard]


class HskTopicRef(BaseModel):
    id: uuid.UUID
    name_zh: str
    name_vi: str | None
    level_code: str


class HskLevelSummary(BaseModel):
    level_code: str
    entry_count: int
    reviewed_count: int
    awaiting_review_count: int
    topic_groups: list[HskTopicGroup] = []


class HskLevelsResponse(BaseModel):
    release: HskReleaseSummary | None
    levels: list[HskLevelSummary]


class HskEntryListItem(BaseModel):
    id: uuid.UUID
    raw_word: str
    raw_pinyin: str
    raw_pos: str | None
    official_serial: int | None
    level_code: str
    review_status: str
    sense_count: int
    saved_count: int


class HskEntryListResponse(BaseModel):
    release: HskReleaseSummary | None
    topic: HskTopicRef | None = None
    items: list[HskEntryListItem]
    page: int
    page_size: int
    total: int
    total_pages: int


class HskSourceLevel(BaseModel):
    level_code: str
    role: Literal["primary", "annotation"]


class HskSourceRecord(BaseModel):
    id: uuid.UUID
    record_id_type: str
    record_id: str
    official_serial: int | None
    raw_word: str
    raw_pinyin: str
    raw_pos: str | None
    raw_level_name: str
    levels: list[HskSourceLevel]
    review_status: str
    review_flags: list[str]


class HskPos(BaseModel):
    code: str
    origin: str
    source_label: str | None


class HskExample(BaseModel):
    text_zh: str
    pinyin: str | None
    translation_vi: str | None
    source: str


class HskSense(BaseModel):
    mapping_id: uuid.UUID
    sense_id: uuid.UUID
    sense_key: str
    gloss_en: str | None
    gloss_vi: str | None
    gloss_source: str
    pos: list[HskPos]
    pos_missing: bool
    pronunciations: list[str]
    examples: list[HskExample]
    saveable: bool
    saved_vocabulary_id: uuid.UUID | None


class HskVariant(BaseModel):
    form: str
    type: str
    pinyin: str | None
    source: str


class HskInterpretation(BaseModel):
    lexical_entry_id: uuid.UUID
    headword: str
    lexical_key: str
    pronunciations: list[str]
    variants: list[HskVariant]
    senses: list[HskSense]
    awaiting_sense_review: bool


class HskEntryDetailResponse(BaseModel):
    release: HskReleaseSummary | None
    source: HskSourceRecord
    interpretations: list[HskInterpretation]


class HskSaveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mapping_id: uuid.UUID


class HskTopicEntry(BaseModel):
    id: uuid.UUID
    mapping_id: uuid.UUID | None
    entry_id: uuid.UUID
    word: str
    pinyin: str
    part_of_speech: str | None
    meaning: str | None
    translation: str | None
    example_sentences: list[str]
    order_index: int
    is_added: bool
    saveable: bool


class HskTopicDetailResponse(BaseModel):
    id: uuid.UUID
    name_zh: str
    name_vi: str | None
    level_code: str
    part: int | None = None
    part_count: int = 1
    description: str | None
    learning_track_name: str
    entry_count: int
    added_count: int
    import_status: Literal["none", "partial", "all"]
    gloss_sources: list[str]
    entries: list[HskTopicEntry]


class HskSensesImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mapping_ids: list[uuid.UUID] = Field(min_length=1, max_length=200)


class HskSensesImportResponse(BaseModel):
    created_count: int
    skipped_count: int
    imported_mapping_ids: list[uuid.UUID]


class HskTopicSaveResponse(BaseModel):
    created_count: int
    skipped_count: int


class HskSaveResponse(BaseModel):
    created: bool
    vocabulary_id: uuid.UUID
    reason: Literal["already_saved", "overlapping_personal_word"] | None = None
