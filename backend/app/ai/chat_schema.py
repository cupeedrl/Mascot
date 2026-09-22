# backend/app/ai/chat_schema.py

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TypedDict, List, NotRequired, Literal, Optional

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


class PendingToolAction(TypedDict):
    tool_name: str
    arguments: dict[str, Any]


@dataclass
class AgentTrace:
    """Sanitized request-scoped metrics populated by the agent loop."""

    provider_calls: int = 0
    tool_rounds: int = 0
    total_tool_calls: int = 0
    tool_names: list[str] = field(default_factory=list)
    tool_latencies_ms: list[int] = field(default_factory=list)
