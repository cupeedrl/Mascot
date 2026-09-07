# backend/app/ai/chat_schema.py

from __future__ import annotations

from typing import TypedDict, List, NotRequired, Literal, Optional

# Provider-neutral message structures used by the internal agent loop.

class ProviderToolCall(TypedDict):
    id: str
    name: str
    arguments: str

class AssistantMessage(TypedDict):
    role: Literal["assistant"]
    content: Optional[str]
    tool_calls: NotRequired[List[ProviderToolCall]]

class ToolResultMessage(TypedDict):
    role: Literal["tool"]
    tool_call_id: str
    content: str

class SystemMessage(TypedDict):
    role: Literal["system"]
    content: str

class UserMessage(TypedDict):
    role: Literal["user"]
    content: str

# Union of all message kinds the agent loop can handle.
Message = SystemMessage | UserMessage | AssistantMessage | ToolResultMessage

# Result returned by the provider after a single turn.
class ProviderResult(TypedDict, total=False):
    content: Optional[str]
    tool_calls: NotRequired[List[ProviderToolCall]]
