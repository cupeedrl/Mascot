from __future__ import annotations

import logging
import uuid

from sqlalchemy.orm import Session

from app.ai.token_usage import current_token_usage
from app.core.config import get_settings
from app.models.ai_usage_log import AIUsageLog

logger = logging.getLogger(__name__)


def record_ai_usage(
    db: Session,
    *,
    user_id: uuid.UUID | None,
    feature: str,
    provider: str | None = None,
    model: str | None = None,
    status: str,
    status_code: int | None = None,
    latency_ms: int | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    total_tokens: int | None = None,
    error_type: str | None = None,
) -> None:
    """Record an AI usage log entry safely without interrupting user requests.

    Explicit arguments win. Otherwise tokens and model come from the request's
    TokenUsage tracker (see ``app.ai.token_usage``), then from settings.
    """
    try:
        settings = get_settings()
        usage = current_token_usage()
        if (
            usage is not None
            and usage.provider_calls
            and input_tokens is None
            and output_tokens is None
            and total_tokens is None
        ):
            input_tokens = usage.input_tokens
            output_tokens = usage.output_tokens
            total_tokens = usage.total_tokens
        provider = provider or settings.ai_provider
        if not model:
            if usage is not None and usage.model:
                model = usage.model
            elif provider == "openai":
                model = settings.openai_model
            else:
                model = settings.groq_model
        log_entry = AIUsageLog(
            user_id=user_id,
            feature=feature,
            provider=provider,
            model=model,
            status=status,
            status_code=status_code,
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            error_type=error_type,
        )
        db.add(log_entry)
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.warning("Failed to record AI usage log: %s", exc)
