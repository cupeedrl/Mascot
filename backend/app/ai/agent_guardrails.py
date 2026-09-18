"""Mascot-owned guardrails for the AI chat agent.

These helpers enforce Mascot's rules around the model, independent of how the
agent loop is orchestrated. Both the LangGraph workflow (`agent_graph.py`) and
the legacy custom loop (`chat_agent.py`) use them, so there is exactly one
implementation of each rule.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from typing import Any

from app.ai.chat_schema import AgentTrace, ProviderToolCall
from app.ai.provider import AIProviderResponseError
from app.ai.tools.executor import ToolValidationError
from app.ai.tools.registry import TOOL_REGISTRY


def build_tool_definitions() -> list[dict[str, Any]]:
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


def record_tool_latency(trace: AgentTrace | None, started_at: float) -> int:
    latency_ms = round((time.perf_counter() - started_at) * 1000)
    if trace is not None:
        trace.tool_latencies_ms.append(latency_ms)
    return latency_ms


def safe_tool_name(name: object) -> str:
    return name if isinstance(name, str) and name in TOOL_REGISTRY else "unknown"


def safe_log_identifier(value: object) -> str:
    text = value if isinstance(value, str) else ""
    if re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", text):
        return text
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
    return f"sha256:{digest}"


def parse_tool_arguments(arguments: str, max_bytes: int) -> dict[str, Any]:
    try:
        if len(arguments.encode("utf-8")) > max_bytes:
            raise ValueError("Tool arguments exceed the size limit.")
        parsed = json.loads(arguments) if arguments else {}
        if not isinstance(parsed, dict):
            raise ValueError("Tool arguments must be a JSON object.")
        return parsed
    except Exception as exc:
        raise ToolValidationError("Invalid tool arguments") from exc


def validate_provider_result(result: object) -> tuple[str | None, list[ProviderToolCall]]:
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
