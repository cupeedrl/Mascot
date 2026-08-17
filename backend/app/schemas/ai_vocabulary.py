from __future__ import annotations

import unicodedata
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

CEFRLevel = Literal["A1", "A2", "B1", "B2", "C1", "C2"]


def _trim_required(value: str) -> str:
    cleaned = unicodedata.normalize("NFKC", value.strip())
    if not cleaned:
        raise ValueError("must not be blank")
    return cleaned


def _validate_single_word(value: str) -> str:
    cleaned = _trim_required(value)
    if any(character.isspace() for character in cleaned):
        raise ValueError("must be a single word")
    if not any(character.isalpha() for character in cleaned):
        raise ValueError("must contain letters")
    if not all(character.isalpha() or character in {"-", "'", "’"} for character in cleaned):
        raise ValueError("contains unsupported characters")
    return cleaned


class VocabularyGenerationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    word: str = Field(min_length=1, max_length=80)

    @field_validator("word")
    @classmethod
    def validate_word(cls, value: str) -> str:
        return _validate_single_word(value)


class VocabularyCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    word: str = Field(min_length=1, max_length=80)
    part_of_speech: str = Field(min_length=1, max_length=64)
    definition: str = Field(min_length=1, max_length=1000)
    translation: str = Field(min_length=1, max_length=500)
    cefr_level: CEFRLevel
    examples: list[str] = Field(min_length=1, max_length=1)

    @field_validator("word")
    @classmethod
    def validate_candidate_word(cls, value: str) -> str:
        return _validate_single_word(value)

    @field_validator("part_of_speech", "definition", "translation")
    @classmethod
    def trim_required_fields(cls, value: str) -> str:
        return _trim_required(value)

    @field_validator("examples")
    @classmethod
    def validate_examples(cls, examples: list[str]) -> list[str]:
        cleaned = [_trim_required(example) for example in examples]
        if any(len(example) > 500 for example in cleaned):
            raise ValueError("each example must be at most 500 characters")
        return cleaned
