from __future__ import annotations

import logging
import time
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.ai.chat_agent import run_chat_agent
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
from app.ai.tools.executor import ToolExecutionError
from app.api.dependencies import get_current_user
from app.core.config import get_settings
from app.db.session import get_db
from app.models.user import User
from app.schemas.ai_chat import AIChatRequest, AIChatResponse, ChatMessage
from app.services.ai_guard import ai_guard, AICooldownError, AIDuplicateRequestError
from app.services.ai_logger import record_ai_usage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/chat", response_model=AIChatResponse)
def chat_with_assistant(
    payload: AIChatRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    provider: Annotated[ChatAIProvider, Depends(get_chat_ai_provider)],
    response: Response,
) -> AIChatResponse:
    settings = get_settings()

    # 1. Deterministically enforce per-message character length limits
    for msg in payload.messages:
        if len(msg.content) > settings.ai_chat_max_message_length:
            raise HTTPException(
                status_code=422,
                detail=f"Tin nhắn không được vượt quá {settings.ai_chat_max_message_length} ký tự.",
            )

    # 2. Deterministically trim history to keep at most the approved maximum history messages
    history = payload.messages
    if len(history) > settings.ai_chat_max_history_messages:
        history = history[-settings.ai_chat_max_history_messages :]

    # 3. Construct context: backend-owned system prompt ALWAYS at position 0
    full_messages: list[dict[str, str]] = [
        {"role": "system", "content": CHAT_ASSISTANT_SYSTEM_PROMPT}
    ]
    for msg in history:
        full_messages.append({"role": msg.role, "content": msg.content})

    # 4. In-flight fingerprinting & rate limit guard
    start_time = time.perf_counter()
    last_user_message = next(
        (m.content for m in reversed(history) if m.role == "user"), ""
    )
    fingerprint = ai_guard.compute_fingerprint(
        current_user.id,
        "ai_chat",
        {"last_message": last_user_message},
    )

    try:
        ai_guard.check_and_acquire(
            current_user.id,
            "ai_chat",
            fingerprint,
            cooldown_seconds=2,
        )
    except AICooldownError as exc:
        latency_ms = round((time.perf_counter() - start_time) * 1000)
        record_ai_usage(
            db,
            user_id=current_user.id,
            feature="ai_chat",
            status="rate_limited",
            status_code=429,
            latency_ms=latency_ms,
            error_type="AICooldownError",
        )
        response.headers["Retry-After"] = str(exc.retry_after)
        raise HTTPException(
            status_code=429,
            detail=str(exc),
            headers={"Retry-After": str(exc.retry_after)},
        ) from exc
    except AIDuplicateRequestError as exc:
        latency_ms = round((time.perf_counter() - start_time) * 1000)
        record_ai_usage(
            db,
            user_id=current_user.id,
            feature="ai_chat",
            status="rate_limited",
            status_code=409,
            latency_ms=latency_ms,
            error_type="AIDuplicateRequestError",
        )
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    # 5. Call AI Chat Agent & Map Errors safely
    try:
        reply_text = run_chat_agent(
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
        )
        latency_ms = round((time.perf_counter() - start_time) * 1000)
        record_ai_usage(
            db,
            user_id=current_user.id,
            feature="ai_chat",
            status="success",
            status_code=200,
            latency_ms=latency_ms,
        )
        ai_guard.release(current_user.id, "ai_chat", fingerprint, mark_success=True)
        return AIChatResponse(message=ChatMessage(role="assistant", content=reply_text))
    except AIProviderNotConfiguredError as exc:
        latency_ms = round((time.perf_counter() - start_time) * 1000)
        record_ai_usage(
            db,
            user_id=current_user.id,
            feature="ai_chat",
            status="failed",
            status_code=503,
            latency_ms=latency_ms,
            error_type="AIProviderNotConfiguredError",
        )
        ai_guard.release(current_user.id, "ai_chat", fingerprint, mark_success=False)
        raise HTTPException(
            status_code=503,
            detail="Dịch vụ AI chưa được cấu hình. Vui lòng liên hệ quản trị viên.",
        ) from exc
    except AIProviderConfigurationError as exc:
        latency_ms = round((time.perf_counter() - start_time) * 1000)
        record_ai_usage(
            db,
            user_id=current_user.id,
            feature="ai_chat",
            status="failed",
            status_code=500,
            latency_ms=latency_ms,
            error_type="AIProviderConfigurationError",
        )
        ai_guard.release(current_user.id, "ai_chat", fingerprint, mark_success=False)
        raise HTTPException(
            status_code=500,
            detail="Cấu hình nhà cung cấp AI không hợp lệ.",
        ) from exc
    except AIProviderQuotaError as exc:
        latency_ms = round((time.perf_counter() - start_time) * 1000)
        record_ai_usage(
            db,
            user_id=current_user.id,
            feature="ai_chat",
            status="quota_exceeded",
            status_code=503,
            latency_ms=latency_ms,
            error_type="AIProviderQuotaError",
        )
        ai_guard.release(current_user.id, "ai_chat", fingerprint, mark_success=False)
        raise HTTPException(
            status_code=503,
            detail="Hạn ngạch AI hệ thống đã vượt quá giới hạn.",
        ) from exc
    except AIProviderRateLimitError as exc:
        latency_ms = round((time.perf_counter() - start_time) * 1000)
        record_ai_usage(
            db,
            user_id=current_user.id,
            feature="ai_chat",
            status="rate_limited",
            status_code=429,
            latency_ms=latency_ms,
            error_type="AIProviderRateLimitError",
        )
        ai_guard.release(current_user.id, "ai_chat", fingerprint, mark_success=False)
        raise HTTPException(
            status_code=429,
            detail="Hệ thống AI đang bận. Vui lòng thử lại sau giây lát.",
        ) from exc
    except AIProviderTimeoutError as exc:
        latency_ms = round((time.perf_counter() - start_time) * 1000)
        record_ai_usage(
            db,
            user_id=current_user.id,
            feature="ai_chat",
            status="timeout",
            status_code=504,
            latency_ms=latency_ms,
            error_type="AIProviderTimeoutError",
        )
        ai_guard.release(current_user.id, "ai_chat", fingerprint, mark_success=False)
        raise HTTPException(
            status_code=504,
            detail="Yêu cầu AI đã hết thời gian chờ. Vui lòng thử lại.",
        ) from exc
    except AIProviderResponseError as exc:
        logger.error("AI chat provider returned invalid response: %s", exc)
        latency_ms = round((time.perf_counter() - start_time) * 1000)
        record_ai_usage(
            db,
            user_id=current_user.id,
            feature="ai_chat",
            status="failed",
            status_code=502,
            latency_ms=latency_ms,
            error_type="AIProviderResponseError",
        )
        ai_guard.release(current_user.id, "ai_chat", fingerprint, mark_success=False)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI service returned an invalid response.",
        ) from exc
    except ToolExecutionError:
        logger.exception("AI chat tool execution failed")
        latency_ms = round((time.perf_counter() - start_time) * 1000)
        record_ai_usage(
            db,
            user_id=current_user.id,
            feature="ai_chat",
            status="failed",
            status_code=502,
            latency_ms=latency_ms,
            error_type="ToolExecutionError",
        )
        ai_guard.release(current_user.id, "ai_chat", fingerprint, mark_success=False)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI learning data is temporarily unavailable.",
        )
    except AIProviderError as exc:
        logger.error("AI chat provider generic error: %s", exc)
        latency_ms = round((time.perf_counter() - start_time) * 1000)
        record_ai_usage(
            db,
            user_id=current_user.id,
            feature="ai_chat",
            status="failed",
            status_code=502,
            latency_ms=latency_ms,
            error_type=type(exc).__name__,
        )
        ai_guard.release(current_user.id, "ai_chat", fingerprint, mark_success=False)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Không thể tạo phản hồi từ AI. Vui lòng thử lại.",
        ) from exc
