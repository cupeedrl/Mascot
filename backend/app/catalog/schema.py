from __future__ import annotations

import unicodedata
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.catalog.constants import (
    CATALOG_CEFR_LEVELS,
    CATALOG_PARTS_OF_SPEECH,
)


class CatalogEntrySeed(BaseModel):
    model_config = ConfigDict(extra="forbid")

    word: str = Field(..., min_length=1, max_length=255)
    part_of_speech: str = Field(..., min_length=1, max_length=64)
    ipa: str = Field(..., min_length=1, max_length=100)
    meaning: str = Field(..., min_length=1, max_length=4000)
    translation: str = Field(..., min_length=1, max_length=4000)
    example_sentences: list[str] = Field(..., min_length=1, max_length=1)
    translation_language_code: str = Field(default="vi", max_length=16)

    @field_validator("word", mode="before")
    @classmethod
    def validate_word(cls, v: object) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError("Word cannot be empty.")
        return unicodedata.normalize("NFKC", v.strip())

    @field_validator("part_of_speech", mode="before")
    @classmethod
    def validate_part_of_speech(cls, v: object) -> str:
        if not isinstance(v, str):
            raise ValueError("Part of speech must be a string.")
        normalized = v.strip().lower()
        if normalized not in CATALOG_PARTS_OF_SPEECH:
            raise ValueError(
                f"Invalid part of speech '{v}'. Must be one of: {', '.join(CATALOG_PARTS_OF_SPEECH)}"
            )
        return normalized

    @field_validator("ipa", mode="before")
    @classmethod
    def validate_ipa(cls, v: object) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError("IPA transcription cannot be blank.")
        cleaned = v.strip()
        if not (cleaned.startswith("/") and cleaned.endswith("/")) and not (
            cleaned.startswith("[") and cleaned.endswith("]")
        ):
            # Enforce slash format for standard phonetics
            cleaned = f"/{cleaned.strip('/')}/"
        return cleaned

    @field_validator("meaning", "translation", mode="before")
    @classmethod
    def validate_non_blank_strings(cls, v: object) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError("Meaning and translation must not be empty.")
        return unicodedata.normalize("NFKC", v.strip())

    @field_validator("example_sentences", mode="before")
    @classmethod
    def validate_examples(cls, v: object) -> list[str]:
        if not isinstance(v, list) or len(v) != 1:
            raise ValueError("Catalog entries must have exactly one example sentence.")
        first = v[0]
        if not isinstance(first, str) or not first.strip():
            raise ValueError("Example sentence cannot be blank.")
        return [unicodedata.normalize("NFKC", first.strip())]


class CatalogSetSeed(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(..., min_length=1, max_length=100)
    level_code: str = Field(...)
    topic: str = Field(..., min_length=1, max_length=120)
    name: str | None = Field(default=None, max_length=160)
    description: str | None = None
    entries: list[CatalogEntrySeed] = Field(default_factory=list)

    @field_validator("level_code", mode="before")
    @classmethod
    def validate_level_code(cls, v: object) -> str:
        if not isinstance(v, str) or v.strip().upper() not in CATALOG_CEFR_LEVELS:
            raise ValueError(
                f"Invalid CEFR level '{v}'. Must be one of: {', '.join(CATALOG_CEFR_LEVELS)}"
            )
        return v.strip().upper()

    @field_validator("topic", mode="before")
    @classmethod
    def validate_topic(cls, v: object) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError("Topic cannot be empty.")
        return unicodedata.normalize("NFKC", v.strip())

    @property
    def display_name(self) -> str:
        return self.name or self.topic

    @property
    def display_description(self) -> str:
        return self.description or f"Curated {self.level_code} vocabulary set for General English learners."
