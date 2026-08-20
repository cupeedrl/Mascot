from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.schemas.vocabulary import VocabularyResponse


class ReviewSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_correct: bool
    force: bool = False


class ReviewQueueResponse(BaseModel):
    items: list[VocabularyResponse]
    total: int
    limit: int

