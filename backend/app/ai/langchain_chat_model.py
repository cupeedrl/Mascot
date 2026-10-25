"""LangChain chat model backed by Mascot's ChatAIProvider.

The LangGraph workflow talks to a standard LangChain chat model. This adapter
is that model: it converts LangChain messages to Mascot's provider-neutral
dicts, calls the configured ChatAIProvider (Groq, OpenAI, or a test fake),
validates the untrusted result, and returns an AIMessage. Provider SDK code
stays inside the existing providers.

The round trip is lossless. Every AIMessage keeps the exact assistant dict,
including raw JSON argument strings, under ASSISTANT_MESSAGE_KEY, so the
provider receives the same messages the legacy loop sends.
"""

from __future__ import annotations

import json
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field

from app.ai.agent_guardrails import validate_provider_result
from app.ai.chat_schema import AssistantMessage, Message, ProviderToolCall
from app.ai.chat_stream import current_stream_callback
from app.ai.provider import AIProviderResponseError

ASSISTANT_MESSAGE_KEY = "mascot_assistant_message"


class ProviderChatModel(BaseChatModel):
    """LangChain chat model that delegates every call to a ChatAIProvider."""

    # Excluded from serialization: the provider holds SDK clients and secrets.
    provider: Any = Field(exclude=True)

    @property
    def _llm_type(self) -> str:
        return "mascot-chat-ai-provider"

    def bind_tools(self, tools: Any, **kwargs: Any) -> Any:
        # Tools are Mascot's provider-neutral definitions built from TOOL_REGISTRY.
        return self.bind(tool_definitions=list(tools), **kwargs)

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        call_options: dict[str, Any] = {
            "messages": to_provider_messages(messages),
            "tool_definitions": kwargs.get("tool_definitions", []),
        }
        # Set only while /ai/chat/stream runs a turn (see app.ai.chat_stream).
        on_event = current_stream_callback()
        streaming = on_event is not None and getattr(self.provider, "supports_streaming", False)
        if streaming:
            call_options["on_event"] = on_event
        result = self.provider.generate_chat_response_with_tools(**call_options)
        # Validate before the result becomes part of the conversation. Streamed
        # deltas were only a draft: the validated result below is authoritative.
        content, tool_calls = validate_provider_result(result)
        if streaming and tool_calls:
            # The model moved on to tools: any text it streamed is not the answer.
            on_event("discard", "")
        message = _to_ai_message(content, tool_calls)
        return ChatResult(generations=[ChatGeneration(message=message)])


def provider_tool_calls(message: BaseMessage) -> list[ProviderToolCall]:
    """Validated tool calls of an assistant message, in provider order."""
    if not isinstance(message, AIMessage):
        return []
    assistant = message.additional_kwargs.get(ASSISTANT_MESSAGE_KEY, {})
    return list(assistant.get("tool_calls", []))


def to_langchain_messages(messages: list[Message]) -> list[BaseMessage]:
    return [_to_langchain_message(message) for message in messages]


def to_provider_messages(messages: list[BaseMessage]) -> list[Message]:
    return [_to_provider_message(message) for message in messages]


def _to_langchain_message(message: Message) -> BaseMessage:
    role = message.get("role")
    if role == "system":
        return SystemMessage(content=message["content"])
    if role == "user":
        return HumanMessage(content=message["content"])
    if role == "assistant":
        return AIMessage(
            content=message.get("content") or "",
            additional_kwargs={ASSISTANT_MESSAGE_KEY: dict(message)},
        )
    if role == "tool":
        return ToolMessage(
            content=message["content"], tool_call_id=message["tool_call_id"]
        )
    raise AIProviderResponseError("unsupported_chat_role", f"Unsupported chat role: {role}")


def _to_provider_message(message: BaseMessage) -> Message:
    if isinstance(message, SystemMessage):
        return {"role": "system", "content": message.content}
    if isinstance(message, HumanMessage):
        return {"role": "user", "content": message.content}
    if isinstance(message, AIMessage):
        stored = message.additional_kwargs.get(ASSISTANT_MESSAGE_KEY)
        if stored is not None:
            return dict(stored)
        return {"role": "assistant", "content": message.content}
    if isinstance(message, ToolMessage):
        return {
            "role": "tool",
            "tool_call_id": message.tool_call_id,
            "content": message.content,
        }
    raise AIProviderResponseError(
        "unsupported_chat_role", f"Unsupported chat role: {message.type}"
    )


def _to_ai_message(
    content: str | None, tool_calls: list[ProviderToolCall]
) -> AIMessage:
    assistant: AssistantMessage = {"role": "assistant", "content": content}
    if tool_calls:
        assistant["tool_calls"] = tool_calls

    # Standard LangChain view of the same calls. Mascot routing and execution use
    # the raw calls above, so malformed arguments still reach Mascot's own checks.
    parsed_calls: list[dict[str, Any]] = []
    invalid_calls: list[dict[str, Any]] = []
    for call in tool_calls:
        try:
            args = json.loads(call["arguments"]) if call["arguments"] else {}
        except ValueError:
            args = None
        if isinstance(args, dict):
            parsed_calls.append({"id": call["id"], "name": call["name"], "args": args})
        else:
            invalid_calls.append({
                "id": call["id"],
                "name": call["name"],
                "args": call["arguments"],
                "error": "Tool arguments are not a JSON object.",
            })

    return AIMessage(
        content=content or "",
        tool_calls=parsed_calls,
        invalid_tool_calls=invalid_calls,
        additional_kwargs={ASSISTANT_MESSAGE_KEY: assistant},
    )
