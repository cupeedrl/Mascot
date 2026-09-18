from __future__ import annotations

import json
import logging
import time
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.ai.agent_graph import run_agent_graph
from app.ai.agent_guardrails import (
    build_tool_definitions as _build_tool_definitions,
    parse_tool_arguments as _parse_tool_arguments,
    record_tool_latency as _record_tool_latency,
    safe_log_identifier as _safe_log_identifier,
    safe_tool_name as _safe_tool_name,
    validate_provider_result as _validate_provider_result,
)
from app.ai.chat_schema import (
    AssistantMessage,
    AgentTrace,
    Message,
    ProviderResult,
    ProviderToolCall,
    PendingToolAction,
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
    validate_tool_arguments,
)
from app.ai.tools.registry import TOOL_REGISTRY
from app.core.config import get_settings

logger = logging.getLogger("uvicorn.error")
logger.setLevel(logging.INFO)

DEFAULT_MAX_TOOL_ROUNDS = 3
DEFAULT_MAX_TOOL_CALLS_PER_ROUND = 4
DEFAULT_MAX_TOTAL_TOOL_CALLS = 8
DEFAULT_MAX_TOOL_ARGUMENT_BYTES = 8192
DEFAULT_MAX_TOOL_PAYLOAD_BYTES = 65536
DEFAULT_TOOL_TIMEOUT_SECONDS = 5.0


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
    trace: AgentTrace | None = None,
    request_id: str = "untracked",
    learning_track_id: UUID | None = None,
) -> str | PendingToolAction:
    """Run the bounded single-agent workflow for the Mascot AI Learning Assistant.

    By default the workflow runs as a LangGraph graph (`agent_graph.py`).
    `settings.ai_agent_engine = "legacy"` selects the original custom loop, kept
    for rollback. Both engines share the same guardrails and return the final
    answer text, or a PendingToolAction that still needs explicit confirmation.
    """
    if not callable(getattr(provider, "generate_chat_response_with_tools", None)):
        raise AIProviderConfigurationError(
            "Configured AI provider does not support tool calling required by chat agent."
        )
    options: dict[str, Any] = {
        "provider": provider,
        "messages": messages,
        "db": db,
        "user_id": user_id,
        "max_tool_rounds": max_tool_rounds,
        "max_tool_calls_per_round": max_tool_calls_per_round,
        "max_total_tool_calls": max_total_tool_calls,
        "max_tool_argument_bytes": max_tool_argument_bytes,
        "max_tool_payload_bytes": max_tool_payload_bytes,
        "tool_timeout_seconds": tool_timeout_seconds,
        "trace": trace,
        "request_id": request_id,
        "learning_track_id": learning_track_id,
    }
    if get_settings().ai_agent_engine == "legacy":
        return _run_legacy_chat_agent(**options)
    # execute_tool is resolved from this module at call time, so the executor
    # seam is the same for both engines.
    return run_agent_graph(**options, execute_tool=execute_tool)


def _run_legacy_chat_agent(
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
    trace: AgentTrace | None = None,
    request_id: str = "untracked",
    learning_track_id: UUID | None = None,
) -> str | PendingToolAction:
    """Original custom agent loop, kept unchanged for rollback (AI_AGENT_ENGINE=legacy)."""
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
        if trace is not None:
            trace.provider_calls += 1
        try:
            result: ProviderResult = generate_with_tools_fn(
                messages=conversation,
                tool_definitions=tools,
            )
        except AIProviderError:
            raise
        except Exception as exc:
            logger.error(
                "Unexpected provider failure (request_id=%s, error_type=%s)",
                request_id,
                type(exc).__name__,
            )
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
        if trace is not None:
            trace.total_tool_calls = total_tool_calls

        write_calls = [
            tool_call
            for tool_call in tool_calls
            if (
                (meta := TOOL_REGISTRY.get(tool_call["name"])) is not None
                and meta["classification"] == "write"
            )
        ]
        if write_calls:
            if len(tool_calls) != 1 or len(write_calls) != 1:
                raise AIProviderResponseError(
                    "mixed_write_tool_calls",
                    "A write proposal must be the only tool call in its round.",
                )
            write_call = write_calls[0]
            meta = TOOL_REGISTRY[write_call["name"]]
            if not meta["requires_confirmation"]:
                raise AIProviderResponseError(
                    "unsafe_write_tool",
                    "Write tool is missing its confirmation requirement.",
                )
            try:
                raw_args = _parse_tool_arguments(
                    write_call["arguments"], max_tool_argument_bytes
                )
                _, validated_args = validate_tool_arguments(
                    write_call["name"], raw_args
                )
            except ToolValidationError:
                pass
            else:
                logger.info(
                    "AI write proposed (request_id=%s, tool=%s, tool_call_id=%s, args_valid=true, status=confirmation_required)",
                    request_id,
                    _safe_tool_name(write_call["name"]),
                    _safe_log_identifier(write_call["id"]),
                )
                if trace is not None:
                    trace.tool_names.append(_safe_tool_name(write_call["name"]))
                return {
                    "tool_name": write_call["name"],
                    "arguments": validated_args.model_dump(mode="json"),
                }

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

            safe_tool_name = _safe_tool_name(tc_name)
            safe_tool_call_id = _safe_log_identifier(tc_id)
            if trace is not None:
                trace.tool_names.append(safe_tool_name)
            logger.info(
                "AI tool requested (request_id=%s, tool=%s, tool_call_id=%s)",
                request_id,
                safe_tool_name,
                safe_tool_call_id,
            )
            tool_started_at = time.perf_counter()

            try:
                args = _parse_tool_arguments(tc_args_str, max_tool_argument_bytes)

                raw_tool_result = execute_tool(
                    name=tc_name,
                    raw_args=args,
                    db=db,
                    current_user_id=user_id,
                    timeout_seconds=tool_timeout_seconds,
                    max_payload_bytes=max_tool_payload_bytes,
                    learning_track_id=learning_track_id,
                )
                tool_result_str = json.dumps(raw_tool_result)
                logger.info(
                    "AI tool completed (request_id=%s, tool=%s, tool_call_id=%s, args_valid=true, status=success, latency_ms=%d)",
                    request_id,
                    safe_tool_name,
                    safe_tool_call_id,
                    _record_tool_latency(trace, tool_started_at),
                )

            except ToolNotFoundError:
                logger.warning(
                    "AI tool rejected (request_id=%s, tool=%s, tool_call_id=%s, args_valid=unknown, status=unknown_tool, latency_ms=%d)",
                    request_id,
                    safe_tool_name,
                    safe_tool_call_id,
                    _record_tool_latency(trace, tool_started_at),
                )
                tool_result_str = json.dumps({
                    "ok": False,
                    "error": "unknown_tool",
                })
            except ToolValidationError:
                logger.warning(
                    "AI tool rejected (request_id=%s, tool=%s, tool_call_id=%s, args_valid=false, status=invalid_arguments, latency_ms=%d)",
                    request_id,
                    safe_tool_name,
                    safe_tool_call_id,
                    _record_tool_latency(trace, tool_started_at),
                )
                tool_result_str = json.dumps({
                    "ok": False,
                    "error": "invalid_tool_arguments",
                })
            except ToolExecutionError:
                logger.exception(
                    "AI tool failed (request_id=%s, tool=%s, tool_call_id=%s, args_valid=true, status=execution_error, latency_ms=%d)",
                    request_id,
                    safe_tool_name,
                    safe_tool_call_id,
                    _record_tool_latency(trace, tool_started_at),
                )
                raise
            except Exception as exc:
                logger.error(
                    "Unexpected tool failure (request_id=%s, tool=%s, tool_call_id=%s, error_type=%s)",
                    request_id,
                    safe_tool_name,
                    safe_tool_call_id,
                    type(exc).__name__,
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
        if trace is not None:
            trace.tool_rounds = tool_rounds
