from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1)


class AIChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    messages: list[ChatMessage] = Field(..., min_length=1)


class AIActionVocabularyDetails(BaseModel):
    model_config = ConfigDict(extra="forbid")

    word: str
    ipa: str | None
    part_of_speech: str
    meaning: str
    translation: str
    translation_language_code: str
    example_sentences: list[str]
    level_code: str
    topic: str | None


class AIActionConfirmation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["confirmation_required"] = "confirmation_required"
    action_id: UUID
    action_token: str
    tool_name: Literal["add_vocabulary"]
    summary: str
    expires_at: datetime
    vocabulary: AIActionVocabularyDetails


class AIActionDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_token: str = Field(min_length=1, max_length=16384)


class AIActionVocabularyResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    word: str
    meaning: str
    translation: str
    level_code: str
    topic: str | None
    learning_status: str


class AIActionExecutionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["executed"] = "executed"
    action_id: UUID
    message: str
    vocabulary: AIActionVocabularyResult


class AIActionCancellationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["canceled"] = "canceled"
    action_id: UUID
    message: str


class AIChatResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: ChatMessage
    confirmation_required: AIActionConfirmation | None = None
