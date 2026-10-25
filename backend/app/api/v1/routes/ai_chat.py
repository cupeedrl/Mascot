from __future__ import annotations

import logging
import time
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.ai.action_tokens import issue_action_token
from app.ai.chat_agent import run_chat_agent
from app.ai.chat_schema import AgentTrace
from app.ai.token_usage import current_token_usage, tracks_token_usage
from app.ai.dependencies import get_chat_ai_provider
from app.ai.prompts import CHAT_ASSISTANT_SYSTEM_PROMPT
from app.ai.provider import (
    AIProviderAuthenticationError,
    AIProviderConfigurationError,
    AIProviderError,
    AIProviderNotConfiguredError,
    AIProviderQuotaError,
    AIProviderRateLimitError,
    AIProviderResponseError,
    AIProviderTimeoutError,
    ChatAIProvider,
)
from app.ai.response_language import (
    detect_response_language,
    localized_action_copy,
    response_language_system_hint,
)
from app.ai.tools.executor import ToolExecutionError
from app.api.dependencies import get_current_user
from app.core.config import get_settings
from app.db.session import get_db
from app.models.user import User
from app.models.learning_track import LearningTrack
from app.schemas.ai_chat import (
    AIActionConfirmation,
    AIActionVocabularyDetails,
    AIChatRequest,
    AIChatResponse,
    ChatMessage,
)
from app.services.ai_guard import ai_guard, AICooldownError, AIDuplicateRequestError
from app.services.ai_conversation import (
    AIConversationNotFoundError,
    append_visible_messages,
    create_conversation,
    get_owned_conversation,
    load_recent_conversation_messages,
)
from app.services.ai_logger import record_ai_usage

logger = logging.getLogger("uvicorn.error")
logger.setLevel(logging.INFO)

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/chat", response_model=AIChatResponse)
@tracks_token_usage
def chat_with_assistant(
    payload: AIChatRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    provider: Annotated[ChatAIProvider, Depends(get_chat_ai_provider)],
    response: Response,
) -> AIChatResponse:
    settings = get_settings()
    request_id = uuid4().hex
    response.headers["X-Request-ID"] = request_id
    provider_name = settings.ai_provider
    model_name = (
        settings.groq_model if provider_name == "groq" else settings.openai_model
    )
    trace = AgentTrace()
    start_time = time.perf_counter()

    def observe(status_value: str, status_code: int, error_type: str | None = None) -> None:
        latency_ms = round((time.perf_counter() - start_time) * 1000)
        # Prefer what actually answered: a fallback provider may have served the request.
        usage = current_token_usage()
        used_provider = (usage.provider if usage else None) or provider_name
        used_model = (usage.model if usage else None) or model_name
        record_ai_usage(
            db,
            user_id=current_user.id,
            feature="ai_chat",
            provider=used_provider,
            model=used_model,
            status=status_value,
            status_code=status_code,
            latency_ms=latency_ms,
            error_type=error_type,
        )
        logger.info(
            "AI chat completed (request_id=%s, provider=%s, model=%s, latency_ms=%d, provider_calls=%d, tool_rounds=%d, total_tool_calls=%d, tools=%s, tool_latencies_ms=%s, final_status=%s, error_type=%s)",
            request_id,
            used_provider,
            used_model,
            latency_ms,
            trace.provider_calls,
            trace.tool_rounds,
            trace.total_tool_calls,
            ",".join(trace.tool_names) or "none",
            ",".join(str(value) for value in trace.tool_latencies_ms) or "none",
            status_value,
            error_type or "none",
        )

    submitted_messages = (
        [ChatMessage(role="user", content=payload.message)]
        if payload.message is not None
        else list(payload.messages or [])
    )

    # 1. Deterministically enforce per-message character length limits.
    for msg in submitted_messages:
        if len(msg.content) > settings.ai_chat_max_message_length:
            raise HTTPException(
                status_code=422,
                detail=f"Tin nhắn không được vượt quá {settings.ai_chat_max_message_length} ký tự.",
            )

    # 2. Resolve the JWT-owned conversation and persist only user-visible input.
    if payload.conversation_id is None:
        conversation = create_conversation(db, current_user.id)
        visible_input = [(message.role, message.content) for message in submitted_messages]
    else:
        try:
            conversation = get_owned_conversation(
                db, current_user.id, payload.conversation_id
            )
        except AIConversationNotFoundError as exc:
            raise HTTPException(status_code=404, detail="AI conversation not found.") from exc
        if payload.message is not None:
            visible_input = [("user", payload.message)]
        else:
            latest_user = next(
                (message for message in reversed(submitted_messages) if message.role == "user"),
                None,
            )
            if latest_user is None:
                raise HTTPException(status_code=422, detail="A user message is required.")
            visible_input = [("user", latest_user.content)]

    append_visible_messages(db, conversation, visible_input)
    history = load_recent_conversation_messages(
        db, conversation.id, settings.ai_chat_max_history_messages
    )

    last_user_message = next(
        (message.content for message in reversed(history) if message.role == "user"),
        "",
    )
    response_language = detect_response_language(last_user_message)

    # 3. Construct context: backend-owned system prompt ALWAYS at position 0
    full_messages: list[dict[str, str]] = [
        {"role": "system", "content": CHAT_ASSISTANT_SYSTEM_PROMPT},
        {
            "role": "system",
            "content": response_language_system_hint(response_language),
        },
    ]
    active_track = None
    if payload.learning_track_id is not None:
        active_track = db.scalar(
            select(LearningTrack)
            .options(joinedload(LearningTrack.language))
            .where(
                LearningTrack.id == payload.learning_track_id,
                LearningTrack.is_active.is_(True),
            )
        )
        if active_track is None or not active_track.language.is_active:
            raise HTTPException(status_code=400, detail="Learning track is not available")
        full_messages.append(
            {
                "role": "system",
                "content": (
                    "Active learning context: "
                    f"{active_track.language.name}, {active_track.name}, "
                    f"framework {active_track.level_framework}. "
                    "Personal learning tool results are scoped to this track."
                ),
            }
        )
    for msg in history:
        full_messages.append({"role": msg.role, "content": msg.content})

    # 4. In-flight fingerprinting & rate limit guard
    fingerprint = ai_guard.compute_fingerprint(
        current_user.id,
        "ai_chat",
        {
            "last_message": last_user_message,
            "learning_track_id": str(payload.learning_track_id or "all"),
        },
    )

    try:
        ai_guard.check_and_acquire(
            current_user.id,
            "ai_chat",
            fingerprint,
            cooldown_seconds=2,
        )
    except AICooldownError as exc:
        observe("rate_limited", 429, "AICooldownError")
        response.headers["Retry-After"] = str(exc.retry_after)
        raise HTTPException(
            status_code=429,
            detail=str(exc),
            headers={"Retry-After": str(exc.retry_after)},
        ) from exc
    except AIDuplicateRequestError as exc:
        observe("rate_limited", 409, "AIDuplicateRequestError")
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    # 5. Call AI Chat Agent & Map Errors safely
    try:
        agent_result = run_chat_agent(
            provider=provider,
            messages=full_messages,
            db=db,
            user_id=current_user.id,
            max_tool_rounds=settings.ai_max_tool_rounds,
            max_tool_calls_per_round=settings.ai_max_tool_calls_per_round,
            max_total_tool_calls=settings.ai_max_total_tool_calls,
            max_tool_argument_bytes=settings.ai_tool_max_argument_bytes,
            max_tool_payload_bytes=settings.ai_tool_max_payload_bytes,
            tool_timeout_seconds=settings.ai_tool_timeout_seconds,
            trace=trace,
            request_id=request_id,
            learning_track_id=payload.learning_track_id,
        )
        confirmation_required = None
        usage_status = "success"
        if isinstance(agent_result, str):
            reply_text = agent_result
        else:
            action_token, claims = issue_action_token(
                tool_name=agent_result["tool_name"],
                arguments=agent_result["arguments"],
                user_id=current_user.id,
            )
            details = AIActionVocabularyDetails.model_validate(
                agent_result["arguments"]
            )
            summary, reply_text = localized_action_copy(
                response_language, details.word
            )
            confirmation_required = AIActionConfirmation(
                action_id=claims.action_id,
                action_token=action_token,
                tool_name="add_vocabulary",
                summary=summary,
                expires_at=claims.expires_at,
                vocabulary=details,
            )
            logger.info(
                "AI action proposed (request_id=%s, action_id=%s, tool=add_vocabulary, proposal_status=confirmation_required)",
                request_id,
                claims.action_id,
            )
            usage_status = "confirmation_required"
        append_visible_messages(db, conversation, [("assistant", reply_text)])
        observe(usage_status, 200)
        ai_guard.release(current_user.id, "ai_chat", fingerprint, mark_success=True)
        return AIChatResponse(
            message=ChatMessage(role="assistant", content=reply_text),
            conversation_id=conversation.id,
            confirmation_required=confirmation_required,
        )
    except AIProviderNotConfiguredError as exc:
        observe("failed", 503, "AIProviderNotConfiguredError")
        ai_guard.release(current_user.id, "ai_chat", fingerprint, mark_success=False)
        raise HTTPException(
            status_code=503,
            detail="Dịch vụ AI chưa được cấu hình. Vui lòng liên hệ quản trị viên.",
        ) from exc
    except AIProviderConfigurationError as exc:
        observe("failed", 500, "AIProviderConfigurationError")
        ai_guard.release(current_user.id, "ai_chat", fingerprint, mark_success=False)
        raise HTTPException(
            status_code=500,
            detail="Cấu hình nhà cung cấp AI không hợp lệ.",
        ) from exc
    except AIProviderQuotaError as exc:
        observe("quota_exceeded", 503, "AIProviderQuotaError")
        ai_guard.release(current_user.id, "ai_chat", fingerprint, mark_success=False)
        raise HTTPException(
            status_code=503,
            detail="Hạn ngạch AI hệ thống đã vượt quá giới hạn.",
        ) from exc
    except AIProviderRateLimitError as exc:
        observe("rate_limited", 429, "AIProviderRateLimitError")
        ai_guard.release(current_user.id, "ai_chat", fingerprint, mark_success=False)
        raise HTTPException(
            status_code=429,
            detail="Hệ thống AI đang bận. Vui lòng thử lại sau giây lát.",
        ) from exc
    except AIProviderTimeoutError as exc:
        observe("timeout", 504, "AIProviderTimeoutError")
        ai_guard.release(current_user.id, "ai_chat", fingerprint, mark_success=False)
        raise HTTPException(
            status_code=504,
            detail="Yêu cầu AI đã hết thời gian chờ. Vui lòng thử lại.",
        ) from exc
    except AIProviderResponseError as exc:
        logger.error(
            "AI chat provider response rejected (request_id=%s, error_type=AIProviderResponseError, stage=%s)",
            request_id,
            exc.stage,
        )
        observe("failed", 502, "AIProviderResponseError")
        ai_guard.release(current_user.id, "ai_chat", fingerprint, mark_success=False)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI service returned an invalid response.",
        ) from exc
    except ToolExecutionError:
        logger.exception("AI chat tool execution failed")
        observe("failed", 502, "ToolExecutionError")
        ai_guard.release(current_user.id, "ai_chat", fingerprint, mark_success=False)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI learning data is temporarily unavailable.",
        )
    except AIProviderError as exc:
        logger.error(
            "AI chat provider failed (request_id=%s, error_type=%s)",
            request_id,
            type(exc).__name__,
        )
        observe("failed", 502, type(exc).__name__)
        ai_guard.release(current_user.id, "ai_chat", fingerprint, mark_success=False)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Không thể tạo phản hồi từ AI. Vui lòng thử lại.",
        ) from exc
