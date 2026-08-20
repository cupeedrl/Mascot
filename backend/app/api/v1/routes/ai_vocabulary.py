from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response

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
from app.models.user import User
from app.schemas.ai_vocabulary import VocabularyCandidate, VocabularyGenerationRequest
from app.services.ai_guard import ai_guard, AICooldownError, AIDuplicateRequestError
from app.services.ai_vocabulary import (
    InvalidAIVocabularyResponseError,
    generate_vocabulary_candidate,
)

router = APIRouter(prefix="/ai")


@router.post("/vocabulary", response_model=VocabularyCandidate)
def generate_vocabulary(
    payload: VocabularyGenerationRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    provider: Annotated[VocabularyAIProvider, Depends(get_vocabulary_ai_provider)],
    response: Response,
) -> VocabularyCandidate:
    fingerprint = ai_guard.compute_fingerprint(
        current_user.id,
        "vocabulary_enrichment",
        {
            "word": payload.word.strip().lower(),
            "part_of_speech": payload.part_of_speech.strip().lower(),
            "translation": payload.translation.strip(),
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
        response.headers["Retry-After"] = str(exc.retry_after)
        raise HTTPException(
            status_code=429,
            detail=str(exc),
            headers={"Retry-After": str(exc.retry_after)},
        ) from exc
    except AIDuplicateRequestError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    try:
        candidate = generate_vocabulary_candidate(
            provider,
            word=payload.word,
            part_of_speech=payload.part_of_speech,
            translation=payload.translation,
        )
        ai_guard.release(current_user.id, "vocabulary_enrichment", fingerprint, mark_success=True)
        return candidate
    except AIProviderNotConfiguredError as exc:
        ai_guard.release(current_user.id, "vocabulary_enrichment", fingerprint, mark_success=False)
        raise HTTPException(
            status_code=503,
            detail="AI chưa được cấu hình trên máy chủ.",
        ) from exc
    except AIProviderQuotaError as exc:
        ai_guard.release(current_user.id, "vocabulary_enrichment", fingerprint, mark_success=False)
        raise HTTPException(
            status_code=503,
            detail="Nhà cung cấp AI đã hết hạn mức hoặc chưa được cấp quota. Hãy kiểm tra trang Usage và Limits của provider.",
        ) from exc
    except AIProviderRateLimitError as exc:
        ai_guard.release(current_user.id, "vocabulary_enrichment", fingerprint, mark_success=False)
        raise HTTPException(
            status_code=429,
            detail="Dịch vụ AI đang giới hạn số lượng yêu cầu. Vui lòng thử lại sau.",
        ) from exc
    except AIProviderConfigurationError as exc:
        ai_guard.release(current_user.id, "vocabulary_enrichment", fingerprint, mark_success=False)
        raise HTTPException(
            status_code=503,
            detail="API key của nhà cung cấp AI không hợp lệ hoặc không có quyền truy cập model đã cấu hình.",
        ) from exc
    except AIProviderTimeoutError as exc:
        ai_guard.release(current_user.id, "vocabulary_enrichment", fingerprint, mark_success=False)
        raise HTTPException(
            status_code=504,
            detail="Yêu cầu AI quá thời gian chờ. Vui lòng thử lại.",
        ) from exc
    except (AIProviderResponseError, InvalidAIVocabularyResponseError) as exc:
        ai_guard.release(current_user.id, "vocabulary_enrichment", fingerprint, mark_success=False)
        raise HTTPException(
            status_code=502,
            detail="AI trả về dữ liệu từ vựng không hợp lệ.",
        ) from exc
    except AIProviderError as exc:
        ai_guard.release(current_user.id, "vocabulary_enrichment", fingerprint, mark_success=False)
        raise HTTPException(
            status_code=502,
            detail="Dịch vụ AI tạm thời không khả dụng.",
        ) from exc
    except Exception:
        ai_guard.release(current_user.id, "vocabulary_enrichment", fingerprint, mark_success=False)
        raise
