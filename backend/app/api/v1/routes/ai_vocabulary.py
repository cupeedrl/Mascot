from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.ai.dependencies import get_vocabulary_ai_provider
from app.ai.provider import (
    AIProviderConfigurationError,
    AIProviderError,
    AIProviderNotConfiguredError,
    AIProviderQuotaError,
    AIProviderRateLimitError,
    AIProviderResponseError,
    AIProviderTimeoutError,
    VocabularyAIProvider,
)
from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.ai_vocabulary import VocabularyCandidate, VocabularyGenerationRequest
from app.services.ai_guard import ai_guard, AICooldownError, AIDuplicateRequestError
from app.services.ai_logger import record_ai_usage
from app.services.ai_vocabulary import (
    AIVocabularyTrackUnavailableError,
    InvalidAIVocabularyResponseError,
    generate_vocabulary_candidate,
)

router = APIRouter(prefix="/ai")


@router.post("/vocabulary", response_model=VocabularyCandidate)
def generate_vocabulary(
    payload: VocabularyGenerationRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    provider: Annotated[VocabularyAIProvider, Depends(get_vocabulary_ai_provider)],
    response: Response,
) -> VocabularyCandidate:
    import time
    start_time = time.perf_counter()
    fingerprint = ai_guard.compute_fingerprint(
        current_user.id,
        "vocabulary_enrichment",
        {
            "word": payload.word.strip().lower(),
            "part_of_speech": payload.part_of_speech.strip().lower(),
            "translation": payload.translation.strip(),
            "learning_track_id": str(payload.learning_track_id or "default"),
        },
    )

    try:
        ai_guard.check_and_acquire(
            current_user.id,
            "vocabulary_enrichment",
            fingerprint,
            cooldown_seconds=5,
        )
    except AICooldownError as exc:
        latency_ms = round((time.perf_counter() - start_time) * 1000)
        record_ai_usage(
            db,
            user_id=current_user.id,
            feature="vocabulary_enrichment",
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
            feature="vocabulary_enrichment",
            status="rate_limited",
            status_code=409,
            latency_ms=latency_ms,
            error_type="AIDuplicateRequestError",
        )
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    try:
        candidate = generate_vocabulary_candidate(
            db,
            provider,
            word=payload.word,
            part_of_speech=payload.part_of_speech,
            translation=payload.translation,
            learning_track_id=payload.learning_track_id,
        )
        latency_ms = round((time.perf_counter() - start_time) * 1000)
        record_ai_usage(
            db,
            user_id=current_user.id,
            feature="vocabulary_enrichment",
            status="success",
            status_code=200,
            latency_ms=latency_ms,
        )
        ai_guard.release(current_user.id, "vocabulary_enrichment", fingerprint, mark_success=True)
        return candidate
    except AIVocabularyTrackUnavailableError as exc:
        ai_guard.release(current_user.id, "vocabulary_enrichment", fingerprint, mark_success=False)
        raise HTTPException(status_code=400, detail="Learning track is not available") from exc
    except AIProviderNotConfiguredError as exc:
        latency_ms = round((time.perf_counter() - start_time) * 1000)
        record_ai_usage(
            db,
            user_id=current_user.id,
            feature="vocabulary_enrichment",
            status="failed",
            status_code=503,
            latency_ms=latency_ms,
            error_type="AIProviderNotConfiguredError",
        )
        ai_guard.release(current_user.id, "vocabulary_enrichment", fingerprint, mark_success=False)
        raise HTTPException(
            status_code=503,
            detail="AI chưa được cấu hình trên máy chủ.",
        ) from exc
    except AIProviderQuotaError as exc:
        latency_ms = round((time.perf_counter() - start_time) * 1000)
        record_ai_usage(
            db,
            user_id=current_user.id,
            feature="vocabulary_enrichment",
            status="failed",
            status_code=503,
            latency_ms=latency_ms,
            error_type="AIProviderQuotaError",
        )
        ai_guard.release(current_user.id, "vocabulary_enrichment", fingerprint, mark_success=False)
        raise HTTPException(
            status_code=503,
            detail="Nhà cung cấp AI đã hết hạn mức hoặc chưa được cấp quota. Hãy kiểm tra trang Usage và Limits của provider.",
        ) from exc
    except AIProviderRateLimitError as exc:
        latency_ms = round((time.perf_counter() - start_time) * 1000)
        record_ai_usage(
            db,
            user_id=current_user.id,
            feature="vocabulary_enrichment",
            status="rate_limited",
            status_code=429,
            latency_ms=latency_ms,
            error_type="AIProviderRateLimitError",
        )
        ai_guard.release(current_user.id, "vocabulary_enrichment", fingerprint, mark_success=False)
        raise HTTPException(
            status_code=429,
            detail="Dịch vụ AI đang giới hạn số lượng yêu cầu. Vui lòng thử lại sau.",
        ) from exc
    except AIProviderConfigurationError as exc:
        latency_ms = round((time.perf_counter() - start_time) * 1000)
        record_ai_usage(
            db,
            user_id=current_user.id,
            feature="vocabulary_enrichment",
            status="failed",
            status_code=503,
            latency_ms=latency_ms,
            error_type="AIProviderConfigurationError",
        )
        ai_guard.release(current_user.id, "vocabulary_enrichment", fingerprint, mark_success=False)
        raise HTTPException(
            status_code=503,
            detail="API key của nhà cung cấp AI không hợp lệ hoặc không có quyền truy cập model đã cấu hình.",
        ) from exc
    except AIProviderTimeoutError as exc:
        latency_ms = round((time.perf_counter() - start_time) * 1000)
        record_ai_usage(
            db,
            user_id=current_user.id,
            feature="vocabulary_enrichment",
            status="failed",
            status_code=504,
            latency_ms=latency_ms,
            error_type="AIProviderTimeoutError",
        )
        ai_guard.release(current_user.id, "vocabulary_enrichment", fingerprint, mark_success=False)
        raise HTTPException(
            status_code=504,
            detail="Yêu cầu AI quá thời gian chờ. Vui lòng thử lại.",
        ) from exc
    except (AIProviderResponseError, InvalidAIVocabularyResponseError) as exc:
        latency_ms = round((time.perf_counter() - start_time) * 1000)
        record_ai_usage(
            db,
            user_id=current_user.id,
            feature="vocabulary_enrichment",
            status="failed",
            status_code=502,
            latency_ms=latency_ms,
            error_type=type(exc).__name__,
        )
        ai_guard.release(current_user.id, "vocabulary_enrichment", fingerprint, mark_success=False)
        raise HTTPException(
            status_code=502,
            detail="AI trả về dữ liệu từ vựng không hợp lệ.",
        ) from exc
    except AIProviderError as exc:
        latency_ms = round((time.perf_counter() - start_time) * 1000)
        record_ai_usage(
            db,
            user_id=current_user.id,
            feature="vocabulary_enrichment",
            status="failed",
            status_code=502,
            latency_ms=latency_ms,
            error_type="AIProviderError",
        )
        ai_guard.release(current_user.id, "vocabulary_enrichment", fingerprint, mark_success=False)
        raise HTTPException(
            status_code=502,
            detail="Dịch vụ AI tạm thời không khả dụng.",
        ) from exc
    except Exception:
        latency_ms = round((time.perf_counter() - start_time) * 1000)
        record_ai_usage(
            db,
            user_id=current_user.id,
            feature="vocabulary_enrichment",
            status="failed",
            status_code=500,
            latency_ms=latency_ms,
            error_type="UnhandledException",
        )
        ai_guard.release(current_user.id, "vocabulary_enrichment", fingerprint, mark_success=False)
        raise
