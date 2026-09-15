from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AIConversationMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime


class AIConversationSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    title: str
    created_at: datetime
    updated_at: datetime


class AIConversationDetailResponse(AIConversationSummaryResponse):
    messages: list[AIConversationMessageResponse]
