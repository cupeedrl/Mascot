from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class HskReleaseSummary(BaseModel):
    id: uuid.UUID
    code: str
    title: str
    status: str
    source_name: str
    source_version: str | None
    data_origin: str
    published_at: datetime | None


class HskLevelSummary(BaseModel):
    level_code: str
    entry_count: int
    reviewed_count: int
    awaiting_review_count: int


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


class HskSaveResponse(BaseModel):
    created: bool
    vocabulary_id: uuid.UUID
    reason: Literal["already_saved", "overlapping_personal_word"] | None = None
