from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LearningPreferenceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_level_code: str | None = Field(max_length=32)

    @field_validator("current_level_code")
    @classmethod
    def normalize_level_code(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("Level code must not be blank")
        return normalized


class LearningPreferenceResponse(BaseModel):
    learning_track_id: uuid.UUID
    framework: str
    current_level_code: str | None
    level_codes: list[str]
