from __future__ import annotations

import logging
import uuid

from sqlalchemy.orm import Session

from app.models.ai_usage_log import AIUsageLog

logger = logging.getLogger(__name__)


def record_ai_usage(
    db: Session,
    *,
    user_id: uuid.UUID | None,
    feature: str,
    provider: str = "groq",
    model: str = "llama-3.3-70b-versatile",
    status: str,
    status_code: int | None = None,
    latency_ms: int | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    total_tokens: int | None = None,
    error_type: str | None = None,
) -> None:
    """Record an AI usage log entry safely without interrupting user requests."""
    try:
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
