from __future__ import annotations

import logging
import time
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.ai.action_tokens import (
    ActionOwnerMismatchError,
    ActionReplayError,
    ActionTokenError,
    ActionTokenExpiredError,
    action_replay_guard,
    verify_action_token,
)
from app.ai.tools.executor import (
    ToolConfirmationRequiredError,
    ToolExecutionError,
    ToolNotFoundError,
    ToolPayloadTooLargeError,
    ToolTimeoutError,
    ToolValidationError,
    execute_confirmed_tool,
    validate_tool_arguments,
)
from app.ai.tools.vocabulary_tools import (
    AddVocabularyDuplicateError,
    DefaultLearningTrackUnavailableError,
)
from app.api.dependencies import get_current_user
from app.core.config import get_settings
from app.db.session import get_db
from app.models.user import User
from app.schemas.ai_chat import (
    AIActionCancellationResponse,
    AIActionDecisionRequest,
    AIActionExecutionResponse,
    AIActionVocabularyResult,
)
from app.services.ai_logger import record_ai_usage
from app.services.ai_conversation import (
    AIConversationNotFoundError,
    append_visible_messages,
    get_owned_conversation,
)

logger = logging.getLogger("uvicorn.error")
logger.setLevel(logging.INFO)

router = APIRouter(prefix="/ai/actions", tags=["ai"])


def _invalid_action() -> HTTPException:
    return HTTPException(status_code=400, detail="AI action token is invalid.")


def _validate_confirmable_action(tool_name: str, arguments: dict) -> None:
    meta, _ = validate_tool_arguments(tool_name, arguments)
    if (
        tool_name != "add_vocabulary"
        or meta["classification"] != "write"
        or not meta["requires_confirmation"]
    ):
        raise ToolConfirmationRequiredError("Action is not confirmable")


def _owned_conversation(db: Session, user_id: UUID, conversation_id: UUID | None):
    if conversation_id is None:
        return None
    try:
        return get_owned_conversation(db, user_id, conversation_id)
    except AIConversationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="AI conversation not found.") from exc


def _audit(
    db: Session,
    *,
    user_id: UUID,
    status_value: str,
    status_code: int,
    latency_ms: int,
    error_type: str | None = None,
) -> None:
    record_ai_usage(
        db,
        user_id=user_id,
        feature="ai_action_add_vocabulary",
        provider="internal",
        model="confirmed_action_v1",
        status=status_value,
        status_code=status_code,
        latency_ms=latency_ms,
        error_type=error_type,
    )


@router.post("/confirm", response_model=AIActionExecutionResponse)
def confirm_action(
    payload: AIActionDecisionRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> AIActionExecutionResponse:
    started_at = time.perf_counter()
    conversation = _owned_conversation(
        db, current_user.id, payload.conversation_id
    )
    try:
        claims = verify_action_token(payload.action_token, current_user.id)
        _validate_confirmable_action(claims.tool_name, claims.arguments)
        action_replay_guard.reserve(claims.action_id, claims.expires_at)
    except ActionTokenExpiredError as exc:
        logger.warning("AI action rejected (action_id=unavailable, tool=unknown, status=expired)")
        raise HTTPException(status_code=400, detail="AI action has expired.") from exc
    except ActionOwnerMismatchError as exc:
        logger.warning("AI action rejected (action_id=unavailable, tool=unknown, status=owner_mismatch)")
        raise HTTPException(status_code=403, detail="AI action belongs to another user.") from exc
    except ActionReplayError as exc:
        logger.warning("AI action rejected (action_id=%s, tool=%s, status=replay)", claims.action_id, claims.tool_name)
        raise HTTPException(status_code=409, detail="AI action was already handled.") from exc
    except (
        ActionTokenError,
        ToolNotFoundError,
        ToolValidationError,
        ToolConfirmationRequiredError,
    ) as exc:
        logger.warning("AI action rejected (action_id=unavailable, tool=unknown, status=invalid)")
        raise _invalid_action() from exc

    settings = get_settings()
    try:
        result = execute_confirmed_tool(
            claims.tool_name,
            claims.arguments,
            db,
            current_user.id,
            timeout_seconds=settings.ai_tool_timeout_seconds,
            max_payload_bytes=settings.ai_tool_max_payload_bytes,
        )
    except AddVocabularyDuplicateError as exc:
        latency_ms = round((time.perf_counter() - started_at) * 1000)
        logger.warning(
            "AI action rejected (action_id=%s, tool=%s, status=conflict, latency_ms=%d)",
            claims.action_id,
            claims.tool_name,
            latency_ms,
        )
        _audit(
            db,
            user_id=current_user.id,
            status_value="conflict",
            status_code=409,
            latency_ms=latency_ms,
            error_type="DuplicateVocabularySenseError",
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": (
                    "This word already exists in My Vocabulary with the same or "
                    "overlapping meaning. Edit the existing entry or add a genuinely "
                    "different sense."
                ),
                "existing_vocabulary_id": str(exc.existing_vocabulary_id),
            },
        ) from exc
    except DefaultLearningTrackUnavailableError as exc:
        raise HTTPException(
            status_code=400, detail="Default learning track is unavailable."
        ) from exc
    except (ToolNotFoundError, ToolValidationError, ToolConfirmationRequiredError) as exc:
        raise _invalid_action() from exc
    except ToolTimeoutError as exc:
        action_replay_guard.release(claims.action_id)
        logger.warning("AI action failed (action_id=%s, tool=%s, status=timeout)", claims.action_id, claims.tool_name)
        raise HTTPException(status_code=504, detail="AI action timed out.") from exc
    except ToolPayloadTooLargeError as exc:
        action_replay_guard.release(claims.action_id)
        logger.warning("AI action failed (action_id=%s, tool=%s, status=invalid_result)", claims.action_id, claims.tool_name)
        raise HTTPException(status_code=502, detail="AI action returned an invalid result.") from exc
    except ToolExecutionError as exc:
        action_replay_guard.release(claims.action_id)
        logger.warning("AI action failed (action_id=%s, tool=%s, status=execution_error)", claims.action_id, claims.tool_name)
        raise HTTPException(status_code=502, detail="AI action could not be completed.") from exc
    except Exception as exc:
        action_replay_guard.release(claims.action_id)
        logger.exception(
            "AI action failed (action_id=%s, tool=%s, status=unexpected_error)",
            claims.action_id,
            claims.tool_name,
        )
        raise HTTPException(status_code=502, detail="AI action could not be completed.") from exc

    latency_ms = round((time.perf_counter() - started_at) * 1000)
    logger.info(
        "AI action executed (action_id=%s, tool=%s, status=success, latency_ms=%d)",
        claims.action_id,
        claims.tool_name,
        latency_ms,
    )
    _audit(
        db,
        user_id=current_user.id,
        status_value="executed",
        status_code=200,
        latency_ms=latency_ms,
    )
    vocabulary = AIActionVocabularyResult.model_validate(result)
    message = f'Added "{vocabulary.word}" to My Vocabulary.'
    if conversation is not None:
        append_visible_messages(db, conversation, [("assistant", message)])
    return AIActionExecutionResponse(
        action_id=claims.action_id,
        message=message,
        vocabulary=vocabulary,
    )


@router.post("/cancel", response_model=AIActionCancellationResponse)
def cancel_action(
    payload: AIActionDecisionRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> AIActionCancellationResponse:
    started_at = time.perf_counter()
    conversation = _owned_conversation(
        db, current_user.id, payload.conversation_id
    )
    try:
        claims = verify_action_token(payload.action_token, current_user.id)
        _validate_confirmable_action(claims.tool_name, claims.arguments)
        action_replay_guard.reserve(claims.action_id, claims.expires_at)
    except ActionTokenExpiredError as exc:
        logger.warning("AI action rejected (action_id=unavailable, tool=unknown, status=expired)")
        raise HTTPException(status_code=400, detail="AI action has expired.") from exc
    except ActionOwnerMismatchError as exc:
        logger.warning("AI action rejected (action_id=unavailable, tool=unknown, status=owner_mismatch)")
        raise HTTPException(status_code=403, detail="AI action belongs to another user.") from exc
    except ActionReplayError as exc:
        logger.warning("AI action rejected (action_id=%s, tool=%s, status=replay)", claims.action_id, claims.tool_name)
        raise HTTPException(status_code=409, detail="AI action was already handled.") from exc
    except (ActionTokenError, ToolNotFoundError, ToolValidationError, ToolConfirmationRequiredError) as exc:
        logger.warning("AI action rejected (action_id=unavailable, tool=unknown, status=invalid)")
        raise _invalid_action() from exc

    latency_ms = round((time.perf_counter() - started_at) * 1000)
    logger.info(
        "AI action canceled (action_id=%s, tool=%s, status=canceled, latency_ms=%d)",
        claims.action_id,
        claims.tool_name,
        latency_ms,
    )
    _audit(
        db,
        user_id=current_user.id,
        status_value="canceled",
        status_code=200,
        latency_ms=latency_ms,
    )
    message = "Vocabulary addition canceled."
    if conversation is not None:
        append_visible_messages(db, conversation, [("assistant", message)])
    return AIActionCancellationResponse(
        action_id=claims.action_id,
        message=message,
    )
