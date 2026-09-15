from __future__ import annotations

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
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
    get_active_unfinished_exercises,
)
from app.services.ai_guard import AICooldownError, AIDuplicateRequestError

from app.services.ai_logger import record_ai_usage

router = APIRouter(prefix="/ai/exercises")
logger = logging.getLogger(__name__)


@router.get("/active", response_model=AIExerciseGenerationResponse)
def get_active_session(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    learning_track_id: uuid.UUID | None = None,
) -> AIExerciseGenerationResponse:
    exercises = get_active_unfinished_exercises(
        db, current_user.id, learning_track_id
    )
    items = [ExerciseResponse.model_validate(exercise) for exercise in exercises]
    return AIExerciseGenerationResponse(
        items=items,
        created_count=len(items),
        resumed=True if items else False,
    )


@router.post("/generate", response_model=AIExerciseGenerationResponse)
def generate_exercises(
    payload: AIExerciseGenerationRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    provider: Annotated[ExerciseAIProvider, Depends(get_exercise_ai_provider)],
    response: Response,
) -> AIExerciseGenerationResponse:
    import time
    start_time = time.perf_counter()

    try:
        exercises, resumed = generate_and_store_exercises(
            db,
            provider,
            current_user.id,
            payload,
        )
        latency_ms = round((time.perf_counter() - start_time) * 1000)
        if not resumed:
            record_ai_usage(
                db,
                user_id=current_user.id,
                feature="exercise_generation",
                status="success",
                status_code=200,
                latency_ms=latency_ms,
            )
    except AICooldownError as exc:
        latency_ms = round((time.perf_counter() - start_time) * 1000)
        record_ai_usage(
            db,
            user_id=current_user.id,
            feature="exercise_generation",
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
            feature="exercise_generation",
            status="rate_limited",
            status_code=409,
            latency_ms=latency_ms,
            error_type="AIDuplicateRequestError",
        )
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc
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
        latency_ms = round((time.perf_counter() - start_time) * 1000)
        record_ai_usage(
            db,
            user_id=current_user.id,
            feature="exercise_generation",
            status="failed",
            status_code=503,
            latency_ms=latency_ms,
            error_type="AIProviderNotConfiguredError",
        )
        raise HTTPException(status_code=503, detail="AI chưa được cấu hình trên máy chủ.") from exc
    except AIProviderQuotaError as exc:
        latency_ms = round((time.perf_counter() - start_time) * 1000)
        record_ai_usage(
            db,
            user_id=current_user.id,
            feature="exercise_generation",
            status="failed",
            status_code=503,
            latency_ms=latency_ms,
            error_type="AIProviderQuotaError",
        )
        raise HTTPException(status_code=503, detail="Nhà cung cấp AI đã hết hạn mức.") from exc
    except AIProviderRateLimitError as exc:
        latency_ms = round((time.perf_counter() - start_time) * 1000)
        record_ai_usage(
            db,
            user_id=current_user.id,
            feature="exercise_generation",
            status="rate_limited",
            status_code=429,
            latency_ms=latency_ms,
            error_type="AIProviderRateLimitError",
        )
        raise HTTPException(
            status_code=429,
            detail="Dịch vụ AI đang giới hạn yêu cầu. Vui lòng thử lại sau.",
        ) from exc
    except AIProviderConfigurationError as exc:
        latency_ms = round((time.perf_counter() - start_time) * 1000)
        record_ai_usage(
            db,
            user_id=current_user.id,
            feature="exercise_generation",
            status="failed",
            status_code=503,
            latency_ms=latency_ms,
            error_type="AIProviderConfigurationError",
        )
        raise HTTPException(
            status_code=503,
            detail="Cấu hình AI không hợp lệ hoặc model không khả dụng.",
        ) from exc
    except AIProviderTimeoutError as exc:
        latency_ms = round((time.perf_counter() - start_time) * 1000)
        record_ai_usage(
            db,
            user_id=current_user.id,
            feature="exercise_generation",
            status="failed",
            status_code=504,
            latency_ms=latency_ms,
            error_type="AIProviderTimeoutError",
        )
        raise HTTPException(
            status_code=504,
            detail="Yêu cầu AI quá thời gian chờ. Vui lòng thử lại.",
        ) from exc
    except (AIProviderResponseError, InvalidAIExerciseResponseError) as exc:
        latency_ms = round((time.perf_counter() - start_time) * 1000)
        record_ai_usage(
            db,
            user_id=current_user.id,
            feature="exercise_generation",
            status="failed",
            status_code=502,
            latency_ms=latency_ms,
            error_type=type(exc).__name__,
        )
        stage = exc.stage if isinstance(exc, AIProviderResponseError) else "exercise_validation"
        logger.warning(
            "AI exercise generation rejected (stage=%s, user_id=%s, error=%s, reason=%s)",
            stage,
            current_user.id,
            type(exc).__name__,
            str(exc) or "provider returned no parseable structured result",
        )
        raise HTTPException(
            status_code=502,
            detail="AI trả về dữ liệu bài tập không hợp lệ; không có bài nào được lưu.",
        ) from exc
    except AIExercisePersistenceError as exc:
        latency_ms = round((time.perf_counter() - start_time) * 1000)
        record_ai_usage(
            db,
            user_id=current_user.id,
            feature="exercise_generation",
            status="failed",
            status_code=500,
            latency_ms=latency_ms,
            error_type="AIExercisePersistenceError",
        )
        raise HTTPException(
            status_code=500,
            detail="Không thể lưu bài tập đã tạo.",
        ) from exc
    except AIProviderError as exc:
        latency_ms = round((time.perf_counter() - start_time) * 1000)
        record_ai_usage(
            db,
            user_id=current_user.id,
            feature="exercise_generation",
            status="failed",
            status_code=502,
            latency_ms=latency_ms,
            error_type="AIProviderError",
        )
        raise HTTPException(status_code=502, detail="Dịch vụ AI tạm thời không khả dụng.") from exc

    items = [ExerciseResponse.model_validate(exercise) for exercise in exercises]
    return AIExerciseGenerationResponse(
        items=items,
        created_count=len(items),
        resumed=resumed,
    )
