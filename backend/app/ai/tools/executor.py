"""Internal tool executor – framework agnostic.

This module provides a simple function `execute_tool` that validates arguments,
invokes the registered handler, and returns a JSON‑safe dictionary.
It deliberately does **not** raise FastAPI HTTPException; instead it raises
custom runtime errors that the API layer can map to HTTP responses.
"""

from __future__ import annotations

import json
import inspect
import logging
import time
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from .registry import TOOL_REGISTRY, ToolMeta
from pydantic import BaseModel, ValidationError

log = logging.getLogger(__name__)

# ----------------------------------------------------------------------
# Custom exception hierarchy – framework agnostic
# ----------------------------------------------------------------------
class ToolError(RuntimeError):
    """Base class for all tool‑related errors."""

class ToolNotFoundError(ToolError):
    """Raised when a requested tool name is not present in the registry."""

class ToolValidationError(ToolError):
    """Raised when argument validation with Pydantic fails."""

class ToolExecutionError(ToolError):
    """Raised when the handler raises an unexpected exception."""

class ToolTimeoutError(ToolExecutionError):
    """Raised when tool execution exceeds its configured time budget."""

class ToolPayloadTooLargeError(ToolExecutionError):
    """Raised when a validated tool result exceeds its configured size limit."""

class ToolConfirmationRequiredError(ToolError):
    """Raised when a write tool reaches the read-only executor."""


def validate_tool_arguments(name: str, raw_args: dict) -> tuple[ToolMeta, BaseModel]:
    """Resolve a whitelisted tool and validate model-authored arguments."""
    meta = TOOL_REGISTRY.get(name)
    if meta is None:
        raise ToolNotFoundError(f"Tool '{name}' is not registered")
    try:
        return meta, meta["arg_schema"].model_validate(raw_args)
    except ValidationError as exc:
        log.warning("Tool argument validation failed (tool=%s)", name)
        raise ToolValidationError("Invalid tool arguments") from exc

# ----------------------------------------------------------------------
def execute_tool(
    name: str,
    raw_args: dict,
    db: Session,
    current_user_id: UUID,
    *,
    timeout_seconds: float | None = None,
    max_payload_bytes: int | None = None,
    learning_track_id: UUID | None = None,
) -> dict:
    """Execute a registered tool and return a JSON‑safe dict.

    Parameters
    ----------
    name: str
        The tool name as registered in ``TOOL_REGISTRY``.
    raw_args: dict
        Unvalidated arguments supplied by the LLM.
    db: Session
        SQLAlchemy session for DB access.
    current_user_id: UUID
        The authenticated user's identifier – injected from the JWT layer.

    Returns
    -------
    dict
        ``result_schema.model_dump(mode="json")`` – guarantees UUID, date,
        datetime are serialised as JSON‑compatible strings.

    Raises
    ------
    ToolNotFoundError
        If ``name`` does not exist in the registry.
    ToolValidationError
        If the supplied arguments do not conform to the tool's ``arg_schema``.
    ToolExecutionError
        If the handler raises any unexpected exception.
    """
    meta, args_obj = validate_tool_arguments(name, raw_args)
    if meta["classification"] != "read" or meta["requires_confirmation"]:
        raise ToolConfirmationRequiredError(
            "Write tools cannot execute through the read-only executor"
        )
    return _execute_validated_tool(
        meta,
        args_obj,
        db,
        current_user_id,
        timeout_seconds=timeout_seconds,
        max_payload_bytes=max_payload_bytes,
        wrap_handler_errors=True,
        enforce_elapsed_after_success=True,
        learning_track_id=learning_track_id,
    )


def execute_confirmed_tool(
    name: str,
    raw_args: dict,
    db: Session,
    current_user_id: UUID,
    *,
    timeout_seconds: float | None = None,
    max_payload_bytes: int | None = None,
) -> dict:
    """Execute only a whitelisted write tool after the API confirmation boundary."""
    meta, args_obj = validate_tool_arguments(name, raw_args)
    if meta["classification"] != "write" or not meta["requires_confirmation"]:
        raise ToolConfirmationRequiredError("Tool is not a confirmable write action")
    return _execute_validated_tool(
        meta,
        args_obj,
        db,
        current_user_id,
        timeout_seconds=timeout_seconds,
        max_payload_bytes=max_payload_bytes,
        wrap_handler_errors=False,
        enforce_elapsed_after_success=False,
        learning_track_id=None,
    )


def _execute_validated_tool(
    meta: ToolMeta,
    args_obj: BaseModel,
    db: Session,
    current_user_id: UUID,
    *,
    timeout_seconds: float | None,
    max_payload_bytes: int | None,
    wrap_handler_errors: bool,
    enforce_elapsed_after_success: bool,
    learning_track_id: UUID | None,
) -> dict:
    name = meta["name"]

    # Apply a database-side statement timeout for the current PostgreSQL
    # transaction. The elapsed-time check below also covers non-query work.
    started_at = time.perf_counter()
    try:
        if (
            timeout_seconds is not None
            and db.get_bind().dialect.name == "postgresql"
        ):
            timeout_ms = max(1, round(timeout_seconds * 1000))
            db.execute(
                text("SELECT set_config('statement_timeout', :timeout, true)"),
                {"timeout": f"{timeout_ms}ms"},
            )
        handler = meta["handler"]
        if "learning_track_id" in inspect.signature(handler).parameters:
            result_obj = handler(
                args_obj,
                db,
                current_user_id,
                learning_track_id=learning_track_id,
            )
        else:
            result_obj = handler(args_obj, db, current_user_id)
    except Exception as exc:
        if (
            timeout_seconds is not None
            and time.perf_counter() - started_at >= timeout_seconds
        ):
            raise ToolTimeoutError("Tool execution exceeded its time budget") from exc
        if not wrap_handler_errors:
            raise
        log.exception("Unexpected error while executing tool %s", name)
        raise ToolExecutionError("Tool execution failed") from exc

    elapsed_seconds = time.perf_counter() - started_at
    if (
        enforce_elapsed_after_success
        and timeout_seconds is not None
        and elapsed_seconds > timeout_seconds
    ):
        raise ToolTimeoutError("Tool execution exceeded its time budget")

    # Enforce the declared result schema contract
    try:
        validated_result = meta["result_schema"].model_validate(result_obj)
    except ValidationError as exc:
        log.exception("Result schema validation failed for tool %s", name)
        raise ToolExecutionError("Tool returned invalid result shape") from exc

    # Serialize to JSON‑compatible dict (UUID/date/datetime become strings)
    result = validated_result.model_dump(mode="json")
    if max_payload_bytes is not None:
        payload_size = len(
            json.dumps(result, separators=(",", ":")).encode("utf-8")
        )
        if payload_size > max_payload_bytes:
            raise ToolPayloadTooLargeError("Tool result exceeded its size limit")
    return result
# NOTE FOR PHASE 3
# The POST /api/v1/ai/chat endpoint already exists from Phase 1.
# Phase 3 must extend that existing route to integrate the bounded tool‑calling
# loop; do NOT create a duplicate chat endpoint.
