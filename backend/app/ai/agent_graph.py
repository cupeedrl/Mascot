"""LangGraph workflow for the Mascot AI Learning Assistant.

    START ──► model ──route_after_model──► END   (final answer or pending write)
                ▲               │
                └──── tools ◄───┘                 (read tools only)

LangGraph owns the control flow. Mascot owns every rule:

- the chat model adapter validates untrusted provider output;
- `model_node` enforces tool budgets and intercepts write tools, which end the
  run as a PendingToolAction and are only executed after explicit confirmation
  through /ai/actions/confirm;
- `tool_node` executes read tools through Mascot's executor.

Identity, the DB session, limits and tracing travel in the runtime context,
never in graph state, so model output can never read or change them.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Annotated, Any, Callable, TypedDict
from uuid import UUID

from langchain_core.messages import AnyMessage, ToolMessage
from langchain_core.runnables import Runnable
from langgraph.errors import GraphRecursionError
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.runtime import Runtime
from sqlalchemy.orm import Session

from app.ai.agent_guardrails import (
    build_tool_definitions,
    parse_tool_arguments,
    record_tool_latency,
    safe_log_identifier,
    safe_tool_name,
)
from app.ai.chat_schema import AgentTrace, Message, PendingToolAction
from app.ai.langchain_chat_model import (
    ProviderChatModel,
    provider_tool_calls,
    to_langchain_messages,
)
from app.ai.provider import AIProviderError, AIProviderResponseError, ChatAIProvider
from app.ai.tools.executor import (
    ToolExecutionError,
    ToolNotFoundError,
    ToolValidationError,
    validate_tool_arguments,
)
from app.ai.tools.registry import TOOL_REGISTRY

logger = logging.getLogger("uvicorn.error")
logger.setLevel(logging.INFO)


class AgentState(TypedDict):
    """Data that changes while the graph runs."""

    messages: Annotated[list[AnyMessage], add_messages]
    tool_rounds: int
    total_tool_calls: int
    pending_action: PendingToolAction | None


@dataclass(frozen=True)
class AgentContext:
    """Per-request dependencies and limits. Never visible to the model."""

    model: Runnable
    db: Session
    user_id: UUID
    learning_track_id: UUID | None
    execute_tool: Callable[..., dict]
    max_tool_rounds: int
    max_tool_calls_per_round: int
    max_total_tool_calls: int
    max_tool_argument_bytes: int
    max_tool_payload_bytes: int
    tool_timeout_seconds: float
    trace: AgentTrace | None
    request_id: str


def model_node(state: AgentState, runtime: Runtime[AgentContext]) -> dict[str, Any]:
    """Ask the model for the next step, then apply Mascot's budgets and write policy."""
    context = runtime.context
    trace = context.trace
    if trace is not None:
        trace.provider_calls += 1
    try:
        ai_message = context.model.invoke(state["messages"])
    except AIProviderError:
        raise
    except Exception as exc:
        logger.error(
            "Unexpected provider failure (request_id=%s, error_type=%s)",
            context.request_id,
            type(exc).__name__,
        )
        raise AIProviderResponseError(
            "provider_call_failed",
            f"Failed to obtain chat response from provider: {exc}",
        ) from exc

    tool_calls = provider_tool_calls(ai_message)
    if not tool_calls:
        if not ai_message.content.strip():
            raise AIProviderResponseError(
                "empty_response",
                "Provider returned an empty response without tool calls.",
            )
        return {"messages": [ai_message]}

    if state["tool_rounds"] >= context.max_tool_rounds:
        logger.warning(
            "Chat agent reached maximum allowed tool rounds (%d) without final answer.",
            context.max_tool_rounds,
        )
        raise AIProviderResponseError(
            "max_tool_rounds_exceeded",
            f"Agent exceeded maximum tool rounds ({context.max_tool_rounds}) without producing a final answer.",
        )
    if len(tool_calls) > context.max_tool_calls_per_round:
        raise AIProviderResponseError(
            "too_many_tool_calls",
            "Provider requested too many tool calls in one round.",
        )
    total_tool_calls = state["total_tool_calls"] + len(tool_calls)
    if total_tool_calls > context.max_total_tool_calls:
        raise AIProviderResponseError(
            "too_many_total_tool_calls",
            "Provider requested too many tool calls in one turn.",
        )
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
            raw_args = parse_tool_arguments(
                write_call["arguments"], context.max_tool_argument_bytes
            )
            _, validated_args = validate_tool_arguments(write_call["name"], raw_args)
        except ToolValidationError:
            # Invalid proposals continue to tool_node, where the executor rejects
            # them and the model receives an invalid_tool_arguments observation.
            pass
        else:
            logger.info(
                "AI write proposed (request_id=%s, tool=%s, tool_call_id=%s, args_valid=true, status=confirmation_required)",
                context.request_id,
                safe_tool_name(write_call["name"]),
                safe_log_identifier(write_call["id"]),
            )
            if trace is not None:
                trace.tool_names.append(safe_tool_name(write_call["name"]))
            # The write is NOT executed here: the run ends with a proposal.
            return {
                "total_tool_calls": total_tool_calls,
                "pending_action": {
                    "tool_name": write_call["name"],
                    "arguments": validated_args.model_dump(mode="json"),
                },
            }

    return {"messages": [ai_message], "total_tool_calls": total_tool_calls}


def route_after_model(state: AgentState) -> str:
    """END on a pending write or a final answer; otherwise run the requested tools."""
    if state["pending_action"] is not None:
        return END
    if provider_tool_calls(state["messages"][-1]):
        return "tools"
    return END


def tool_node(state: AgentState, runtime: Runtime[AgentContext]) -> dict[str, Any]:
    """Execute the requested read tools through Mascot's executor, in order."""
    context = runtime.context
    trace = context.trace
    tool_messages: list[ToolMessage] = []

    for tool_call in provider_tool_calls(state["messages"][-1]):
        tool_call_id = tool_call["id"]
        tool_name = tool_call["name"]
        safe_name = safe_tool_name(tool_name)
        safe_call_id = safe_log_identifier(tool_call_id)
        if trace is not None:
            trace.tool_names.append(safe_name)
        logger.info(
            "AI tool requested (request_id=%s, tool=%s, tool_call_id=%s)",
            context.request_id,
            safe_name,
            safe_call_id,
        )
        started_at = time.perf_counter()

        try:
            args = parse_tool_arguments(
                tool_call["arguments"], context.max_tool_argument_bytes
            )
            raw_tool_result = context.execute_tool(
                name=tool_name,
                raw_args=args,
                db=context.db,
                current_user_id=context.user_id,
                timeout_seconds=context.tool_timeout_seconds,
                max_payload_bytes=context.max_tool_payload_bytes,
                learning_track_id=context.learning_track_id,
            )
            tool_result = json.dumps(raw_tool_result)
            logger.info(
                "AI tool completed (request_id=%s, tool=%s, tool_call_id=%s, args_valid=true, status=success, latency_ms=%d)",
                context.request_id,
                safe_name,
                safe_call_id,
                record_tool_latency(trace, started_at),
            )
        except ToolNotFoundError:
            logger.warning(
                "AI tool rejected (request_id=%s, tool=%s, tool_call_id=%s, args_valid=unknown, status=unknown_tool, latency_ms=%d)",
                context.request_id,
                safe_name,
                safe_call_id,
                record_tool_latency(trace, started_at),
            )
            tool_result = json.dumps({"ok": False, "error": "unknown_tool"})
        except ToolValidationError:
            logger.warning(
                "AI tool rejected (request_id=%s, tool=%s, tool_call_id=%s, args_valid=false, status=invalid_arguments, latency_ms=%d)",
                context.request_id,
                safe_name,
                safe_call_id,
                record_tool_latency(trace, started_at),
            )
            tool_result = json.dumps({"ok": False, "error": "invalid_tool_arguments"})
        except ToolExecutionError:
            logger.exception(
                "AI tool failed (request_id=%s, tool=%s, tool_call_id=%s, args_valid=true, status=execution_error, latency_ms=%d)",
                context.request_id,
                safe_name,
                safe_call_id,
                record_tool_latency(trace, started_at),
            )
            raise
        except Exception as exc:
            logger.error(
                "Unexpected tool failure (request_id=%s, tool=%s, tool_call_id=%s, error_type=%s)",
                context.request_id,
                safe_name,
                safe_call_id,
                type(exc).__name__,
            )
            raise ToolExecutionError(f"Unexpected tool failure: {exc}") from exc

        tool_messages.append(ToolMessage(content=tool_result, tool_call_id=tool_call_id))

    tool_rounds = state["tool_rounds"] + 1
    if trace is not None:
        trace.tool_rounds = tool_rounds
    return {"messages": tool_messages, "tool_rounds": tool_rounds}


def build_agent_graph() -> Any:
    graph = StateGraph(AgentState, context_schema=AgentContext)
    graph.add_node("model", model_node)
    graph.add_node("tools", tool_node)
    graph.add_edge(START, "model")
    graph.add_conditional_edges("model", route_after_model, ["tools", END])
    graph.add_edge("tools", "model")
    return graph.compile()


AGENT_GRAPH = build_agent_graph()


def recursion_limit(max_tool_rounds: int) -> int:
    """Backstop only. model_node enforces the real budget first.

    A run takes at most 2 * max_tool_rounds + 1 steps: model, then a
    (tools, model) pair per round.
    """
    return 2 * max_tool_rounds + 2


def run_agent_graph(
    provider: ChatAIProvider,
    messages: list[Message],
    db: Session,
    user_id: UUID,
    execute_tool: Callable[..., dict],
    max_tool_rounds: int,
    max_tool_calls_per_round: int,
    max_total_tool_calls: int,
    max_tool_argument_bytes: int,
    max_tool_payload_bytes: int,
    tool_timeout_seconds: float,
    trace: AgentTrace | None,
    request_id: str,
    learning_track_id: UUID | None,
) -> str | PendingToolAction:
    """Run one chat turn through the graph and return the final text or a proposal."""
    context = AgentContext(
        model=ProviderChatModel(provider=provider).bind_tools(build_tool_definitions()),
        db=db,
        user_id=user_id,
        learning_track_id=learning_track_id,
        execute_tool=execute_tool,
        max_tool_rounds=max_tool_rounds,
        max_tool_calls_per_round=max_tool_calls_per_round,
        max_total_tool_calls=max_total_tool_calls,
        max_tool_argument_bytes=max_tool_argument_bytes,
        max_tool_payload_bytes=max_tool_payload_bytes,
        tool_timeout_seconds=tool_timeout_seconds,
        trace=trace,
        request_id=request_id,
    )
    initial_state: AgentState = {
        "messages": to_langchain_messages(messages),
        "tool_rounds": 0,
        "total_tool_calls": 0,
        "pending_action": None,
    }
    try:
        final_state = AGENT_GRAPH.invoke(
            initial_state,
            context=context,
            config={"recursion_limit": recursion_limit(max_tool_rounds)},
        )
    except GraphRecursionError as exc:
        raise AIProviderResponseError(
            "max_tool_rounds_exceeded",
            "Agent graph exceeded its step limit without producing a final answer.",
        ) from exc

    if final_state["pending_action"] is not None:
        return final_state["pending_action"]
    return final_state["messages"][-1].content.strip()
