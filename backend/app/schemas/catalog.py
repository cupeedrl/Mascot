from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, computed_field

from app.learning_levels import get_level_codes


class LanguageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str
    native_name: str | None


class LearningTrackResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str
    description: str | None
    level_framework: str
    language: LanguageResponse

    @computed_field
    @property
    def level_codes(self) -> list[str]:
        return list(get_level_codes(self.level_framework))
