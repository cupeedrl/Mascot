from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

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
from app.services.ai_vocabulary import (
    InvalidAIVocabularyResponseError,
    generate_vocabulary_candidate,
)

router = APIRouter(prefix="/ai")


@router.post("/vocabulary", response_model=VocabularyCandidate)
def generate_vocabulary(
    payload: VocabularyGenerationRequest,
    _current_user: Annotated[User, Depends(get_current_user)],
    provider: Annotated[VocabularyAIProvider, Depends(get_vocabulary_ai_provider)],
) -> VocabularyCandidate:
    try:
        return generate_vocabulary_candidate(provider, payload.word)
    except AIProviderNotConfiguredError as exc:
        raise HTTPException(
            status_code=503,
            detail="AI chưa được cấu hình trên máy chủ.",
        ) from exc
    except AIProviderQuotaError as exc:
        raise HTTPException(
            status_code=503,
            detail="Nhà cung cấp AI đã hết hạn mức hoặc chưa được cấp quota. Hãy kiểm tra trang Usage và Limits của provider.",
        ) from exc
    except AIProviderRateLimitError as exc:
        raise HTTPException(
            status_code=429,
            detail="Dịch vụ AI đang giới hạn số lượng yêu cầu. Vui lòng thử lại sau.",
        ) from exc
    except AIProviderConfigurationError as exc:
        raise HTTPException(
            status_code=503,
            detail="API key của nhà cung cấp AI không hợp lệ hoặc không có quyền truy cập model đã cấu hình.",
        ) from exc
    except AIProviderTimeoutError as exc:
        raise HTTPException(
            status_code=504,
            detail="Yêu cầu AI quá thời gian chờ. Vui lòng thử lại.",
        ) from exc
    except (AIProviderResponseError, InvalidAIVocabularyResponseError) as exc:
        raise HTTPException(
            status_code=502,
            detail="AI trả về dữ liệu từ vựng không hợp lệ.",
        ) from exc
    except AIProviderError as exc:
        raise HTTPException(
            status_code=502,
            detail="Dịch vụ AI tạm thời không khả dụng.",
        ) from exc
