from __future__ import annotations

import json
import logging
import time
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.ai.chat_schema import (
    AssistantMessage,
    Message,
    ProviderResult,
    ProviderToolCall,
    SystemMessage,
    ToolResultMessage,
    UserMessage,
)
from app.ai.prompts import CHAT_ASSISTANT_SYSTEM_PROMPT
from app.ai.provider import (
    AIProviderConfigurationError,
    AIProviderError,
    AIProviderResponseError,
    ChatAIProvider,
)
from app.ai.tools.executor import (
    ToolExecutionError,
    ToolNotFoundError,
    ToolValidationError,
    execute_tool,
)
from app.ai.tools.registry import TOOL_REGISTRY

logger = logging.getLogger(__name__)

DEFAULT_MAX_TOOL_ROUNDS = 3
DEFAULT_MAX_TOOL_CALLS_PER_ROUND = 4
DEFAULT_MAX_TOTAL_TOOL_CALLS = 8
DEFAULT_MAX_TOOL_ARGUMENT_BYTES = 8192
DEFAULT_MAX_TOOL_PAYLOAD_BYTES = 65536
DEFAULT_TOOL_TIMEOUT_SECONDS = 5.0


def _build_tool_definitions() -> list[dict[str, Any]]:
    """Create provider-neutral tool specifications for the LLM."""
    tools: list[dict[str, Any]] = []
    for tool_name, tool_meta in TOOL_REGISTRY.items():
        arg_schema = tool_meta.get("arg_schema") if isinstance(tool_meta, dict) else getattr(tool_meta, "arg_schema", None)
        parameters = (
            arg_schema.model_json_schema()
            if hasattr(arg_schema, "model_json_schema")
            else {"type": "object", "properties": {}}
        )
        desc = tool_meta.get("description") if isinstance(tool_meta, dict) else getattr(tool_meta, "description", "")
        tools.append({
            "name": tool_name,
            "description": desc,
            "parameters": parameters,
        })
    return tools


def run_chat_agent(
    provider: ChatAIProvider,
    messages: list[dict[str, str]],
    db: Session,
    user_id: UUID,
    max_tool_rounds: int = DEFAULT_MAX_TOOL_ROUNDS,
    max_tool_calls_per_round: int = DEFAULT_MAX_TOOL_CALLS_PER_ROUND,
    max_total_tool_calls: int = DEFAULT_MAX_TOTAL_TOOL_CALLS,
    max_tool_argument_bytes: int = DEFAULT_MAX_TOOL_ARGUMENT_BYTES,
    max_tool_payload_bytes: int = DEFAULT_MAX_TOOL_PAYLOAD_BYTES,
    tool_timeout_seconds: float = DEFAULT_TOOL_TIMEOUT_SECONDS,
) -> str:
    """Run the bounded single-agent loop for the Mascot AI Learning Assistant."""
    generate_with_tools_fn = getattr(
        provider, "generate_chat_response_with_tools", None
    )
    if not callable(generate_with_tools_fn):
        raise AIProviderConfigurationError(
            "Configured AI provider does not support tool calling required by chat agent."
        )

    tools = _build_tool_definitions()
    conversation: list[Message] = list(messages)  # type: ignore[arg-type]

    tool_rounds = 0
    total_tool_calls = 0
    while True:
        try:
            result: ProviderResult = generate_with_tools_fn(
                messages=conversation,
                tool_definitions=tools,
            )
        except AIProviderError:
            raise
        except Exception as exc:
            logger.exception("Unexpected error during provider chat call: %s", exc)
            raise AIProviderResponseError(
                "provider_call_failed",
                f"Failed to obtain chat response from provider: {exc}",
            ) from exc

        content, tool_calls = _validate_provider_result(result)

        if not tool_calls:
            if not content or not content.strip():
                raise AIProviderResponseError(
                    "empty_response",
                    "Provider returned an empty response without tool calls.",
                )
            return content.strip()

        if tool_rounds >= max_tool_rounds:
            logger.warning(
                "Chat agent reached maximum allowed tool rounds (%d) without final answer.",
                max_tool_rounds,
            )
            raise AIProviderResponseError(
                "max_tool_rounds_exceeded",
                f"Agent exceeded maximum tool rounds ({max_tool_rounds}) without producing a final answer.",
            )

        if len(tool_calls) > max_tool_calls_per_round:
            raise AIProviderResponseError(
                "too_many_tool_calls",
                "Provider requested too many tool calls in one round.",
            )
        if total_tool_calls + len(tool_calls) > max_total_tool_calls:
            raise AIProviderResponseError(
                "too_many_total_tool_calls",
                "Provider requested too many tool calls in one turn.",
            )
        total_tool_calls += len(tool_calls)

        assistant_msg: AssistantMessage = {
            "role": "assistant",
            "content": content,
            "tool_calls": tool_calls,
        }
        conversation.append(assistant_msg)

        for tc in tool_calls:
            tc_id = tc.get("id") if isinstance(tc, dict) else getattr(tc, "id")
            tc_name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name")
            tc_args_str = tc.get("arguments") if isinstance(tc, dict) else getattr(tc, "arguments")

            logger.info(
                "AI tool requested (tool=%s, tool_call_id=%s)",
                tc_name,
                tc_id,
            )
            tool_started_at = time.perf_counter()

            try:
                try:
                    if len(tc_args_str.encode("utf-8")) > max_tool_argument_bytes:
                        raise ValueError("Tool arguments exceed the size limit.")
                    args = json.loads(tc_args_str) if tc_args_str else {}
                    if not isinstance(args, dict):
                        raise ValueError("Tool arguments must be a JSON object.")
                except Exception as json_err:
                    raise ToolValidationError(
                        f"Malformed JSON arguments: {json_err}"
                    ) from json_err

                raw_tool_result = execute_tool(
                    name=tc_name,
                    raw_args=args,
                    db=db,
                    current_user_id=user_id,
                    timeout_seconds=tool_timeout_seconds,
                    max_payload_bytes=max_tool_payload_bytes,
                )
                tool_result_str = json.dumps(raw_tool_result)
                logger.info(
                    "AI tool completed (tool=%s, tool_call_id=%s, args_valid=true, status=success, latency_ms=%d)",
                    tc_name,
                    tc_id,
                    round((time.perf_counter() - tool_started_at) * 1000),
                )

            except ToolNotFoundError:
                logger.warning(
                    "AI tool rejected (tool=%s, tool_call_id=%s, args_valid=unknown, status=unknown_tool, latency_ms=%d)",
                    tc_name,
                    tc_id,
                    round((time.perf_counter() - tool_started_at) * 1000),
                )
                tool_result_str = json.dumps({
                    "ok": False,
                    "error": "unknown_tool",
                })
            except ToolValidationError:
                logger.warning(
                    "AI tool rejected (tool=%s, tool_call_id=%s, args_valid=false, status=invalid_arguments, latency_ms=%d)",
                    tc_name,
                    tc_id,
                    round((time.perf_counter() - tool_started_at) * 1000),
                )
                tool_result_str = json.dumps({
                    "ok": False,
                    "error": "invalid_tool_arguments",
                })
            except ToolExecutionError:
                logger.exception(
                    "AI tool failed (tool=%s, tool_call_id=%s, args_valid=true, status=execution_error, latency_ms=%d)",
                    tc_name,
                    tc_id,
                    round((time.perf_counter() - tool_started_at) * 1000),
                )
                raise
            except Exception as exc:
                logger.exception(
                    "Unexpected fatal failure executing tool '%s': %s",
                    tc_name,
                    exc,
                )
                raise ToolExecutionError(
                    f"Unexpected tool failure: {exc}"
                ) from exc

            tool_msg: ToolResultMessage = {
                "role": "tool",
                "tool_call_id": tc_id,
                "content": tool_result_str,
            }
            conversation.append(tool_msg)

        tool_rounds += 1


def _validate_provider_result(result: object) -> tuple[str | None, list[ProviderToolCall]]:
    """Validate untrusted provider output before adding it to the conversation."""
    if not isinstance(result, dict):
        raise AIProviderResponseError("invalid_result", "Provider result must be an object.")
    if set(result) - {"content", "tool_calls"}:
        raise AIProviderResponseError(
            "invalid_result", "Provider result contains unsupported fields."
        )

    content = result.get("content")
    if content is not None and not isinstance(content, str):
        raise AIProviderResponseError(
            "invalid_content", "Provider content must be text or null."
        )

    raw_tool_calls = result.get("tool_calls")
    if raw_tool_calls is None:
        return content, []
    if not isinstance(raw_tool_calls, list):
        raise AIProviderResponseError(
            "invalid_tool_calls", "Provider tool_calls must be a list."
        )

    validated: list[ProviderToolCall] = []
    seen_ids: set[str] = set()
    for raw_call in raw_tool_calls:
        if not isinstance(raw_call, dict) or set(raw_call) != {
            "id",
            "name",
            "arguments",
        }:
            raise AIProviderResponseError(
                "invalid_tool_call", "Provider tool call has an invalid shape."
            )
        call_id = raw_call["id"]
        name = raw_call["name"]
        arguments = raw_call["arguments"]
        if (
            not isinstance(call_id, str)
            or not call_id.strip()
            or call_id in seen_ids
        ):
            raise AIProviderResponseError(
                "invalid_tool_call_id", "Provider tool call id is invalid."
            )
        if not isinstance(name, str) or not name.strip():
            raise AIProviderResponseError(
                "invalid_tool_name", "Provider tool name is invalid."
            )
        if not isinstance(arguments, str):
            raise AIProviderResponseError(
                "invalid_tool_arguments", "Provider tool arguments must be JSON text."
            )
        seen_ids.add(call_id)
        validated.append({"id": call_id, "name": name, "arguments": arguments})
    return content, validated
