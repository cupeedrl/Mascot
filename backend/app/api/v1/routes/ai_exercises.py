from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.ai.dependencies import get_exercise_ai_provider
from app.ai.provider import (
    AIProviderConfigurationError,
    AIProviderError,
    AIProviderNotConfiguredError,
    AIProviderQuotaError,
    AIProviderRateLimitError,
    AIProviderResponseError,
    AIProviderTimeoutError,
    ExerciseAIProvider,
)
from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.ai_exercise import (
    AIExerciseGenerationRequest,
    AIExerciseGenerationResponse,
)
from app.schemas.exercise import ExerciseResponse
from app.services.ai_exercise import (
    AIExercisePersistenceError,
    InsufficientVocabularyError,
    InvalidAIExerciseResponseError,
    VocabularySelectionNotFoundError,
    VocabularySourceEmptyError,
    VocabularyTrackMismatchError,
    generate_and_store_exercises,
)

router = APIRouter(prefix="/ai/exercises")


@router.post("/generate", response_model=AIExerciseGenerationResponse)
def generate_exercises(
    payload: AIExerciseGenerationRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    provider: Annotated[ExerciseAIProvider, Depends(get_exercise_ai_provider)],
) -> AIExerciseGenerationResponse:
    try:
        exercises = generate_and_store_exercises(
            db,
            provider,
            current_user.id,
            payload,
        )
    except VocabularySelectionNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="Không tìm thấy một hoặc nhiều từ vựng đã chọn.",
        ) from exc
    except VocabularySourceEmptyError as exc:
        raise HTTPException(
            status_code=422,
            detail="Không có từ vựng phù hợp trong nguồn bạn đã chọn.",
        ) from exc
    except VocabularyTrackMismatchError as exc:
        raise HTTPException(
            status_code=422,
            detail="Các từ được chọn phải thuộc cùng một learning track.",
        ) from exc
    except InsufficientVocabularyError as exc:
        raise HTTPException(
            status_code=422,
            detail="Bạn cần ít nhất 4 từ khác nhau để tạo bài tập trắc nghiệm.",
        ) from exc
    except AIProviderNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail="AI chưa được cấu hình trên máy chủ.") from exc
    except AIProviderQuotaError as exc:
        raise HTTPException(status_code=503, detail="Nhà cung cấp AI đã hết hạn mức.") from exc
    except AIProviderRateLimitError as exc:
        raise HTTPException(
            status_code=429,
            detail="Dịch vụ AI đang giới hạn yêu cầu. Vui lòng thử lại sau.",
        ) from exc
    except AIProviderConfigurationError as exc:
        raise HTTPException(
            status_code=503,
            detail="Cấu hình AI không hợp lệ hoặc model không khả dụng.",
        ) from exc
    except AIProviderTimeoutError as exc:
        raise HTTPException(
            status_code=504,
            detail="Yêu cầu AI quá thời gian chờ. Vui lòng thử lại.",
        ) from exc
    except (AIProviderResponseError, InvalidAIExerciseResponseError) as exc:
        raise HTTPException(
            status_code=502,
            detail="AI trả về dữ liệu bài tập không hợp lệ; không có bài nào được lưu.",
        ) from exc
    except AIExercisePersistenceError as exc:
        raise HTTPException(
            status_code=500,
            detail="Không thể lưu bài tập đã tạo.",
        ) from exc
    except AIProviderError as exc:
        raise HTTPException(status_code=502, detail="Dịch vụ AI tạm thời không khả dụng.") from exc

    items = [ExerciseResponse.model_validate(exercise) for exercise in exercises]
    return AIExerciseGenerationResponse(items=items, created_count=len(items))
