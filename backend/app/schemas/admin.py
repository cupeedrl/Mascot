from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.vocabulary import CEFRLevel


class AdminOverviewResponse(BaseModel):
    total_users: int
    total_catalog_entries: int
    total_personal_vocabulary: int
    total_practice_sessions: int


class AdminUserListItem(BaseModel):
    id: uuid.UUID
    email: str
    role: Literal["user", "admin"]
    is_active: bool
    created_at: datetime
    last_active_at: datetime | None = None
    personal_vocabulary_count: int
    practice_session_count: int


class AdminUserListResponse(BaseModel):
    items: list[AdminUserListItem]
    page: int
    page_size: int
    total: int
    total_pages: int


class AdminUserRecentActivityItem(BaseModel):
    id: uuid.UUID
    exercise_id: uuid.UUID
    is_correct: bool
    user_answer: str
    correct_answer: str
    completed_at: datetime


class AdminUserDetailResponse(BaseModel):
    id: uuid.UUID
    email: str
    role: Literal["user", "admin"]
    is_active: bool
    created_at: datetime
    last_active_at: datetime | None = None
    total_vocabulary: int
    learning_words: int
    mastered_words: int
    exercises_completed: int
    exercise_accuracy: float
    current_streak: int
    longest_streak: int
    recent_activity: list[AdminUserRecentActivityItem] = Field(default_factory=list)


class AdminUpdateUserRoleRequest(BaseModel):
    role: Literal["user", "admin"]


class AdminUpdateUserStatusRequest(BaseModel):
    is_active: bool


class AdminCatalogEntryItem(BaseModel):
    id: uuid.UUID
    vocabulary_set_id: uuid.UUID
    word: str
    ipa: str | None = None
    part_of_speech: str
    meaning: str
    translation: str
    example_sentences: list[str]
    level_code: str
    topic: str
    set_name: str
    order_index: int
    created_at: datetime
    updated_at: datetime


class AdminCatalogListResponse(BaseModel):
    items: list[AdminCatalogEntryItem]
    page: int
    page_size: int
    total: int
    total_pages: int


class AdminCreateCatalogEntryRequest(BaseModel):
    word: str = Field(min_length=1, max_length=255)
    ipa: str | None = Field(default=None, max_length=100)
    part_of_speech: str = Field(min_length=1, max_length=64)
    meaning: str = Field(min_length=1)
    translation: str = Field(min_length=1)
    example_sentences: list[str] = Field(min_length=1, max_length=5)
    level_code: CEFRLevel
    topic: str = Field(min_length=1, max_length=120)


class AdminUpdateCatalogEntryRequest(BaseModel):
    word: str | None = Field(default=None, min_length=1, max_length=255)
    ipa: str | None = Field(default=None, max_length=100)
    part_of_speech: str | None = Field(default=None, min_length=1, max_length=64)
    meaning: str | None = Field(default=None, min_length=1)
    translation: str | None = Field(default=None, min_length=1)
    example_sentences: list[str] | None = Field(default=None, min_length=1, max_length=5)
    level_code: CEFRLevel | None = None
    topic: str | None = Field(default=None, min_length=1, max_length=120)
