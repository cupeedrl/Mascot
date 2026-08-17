from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.exercise import (
    ExerciseAttemptCreate,
    ExerciseAttemptListResponse,
    ExerciseAttemptResult,
    ExerciseListResponse,
    ExerciseResponse,
    ExerciseType,
)
from app.services.exercise import (
    ExerciseNotFoundError,
    InvalidStoredExerciseError,
    get_owned_exercise,
    list_owned_attempts,
    list_owned_exercises,
    submit_attempt,
)

router = APIRouter(prefix="/exercises")
attempts_router = APIRouter(prefix="/exercise-attempts")


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="Exercise not found")


@router.get("", response_model=ExerciseListResponse)
def list_exercises(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    exercise_type: ExerciseType | None = None,
    learning_track_id: uuid.UUID | None = None,
) -> ExerciseListResponse:
    result = list_owned_exercises(
        db,
        current_user.id,
        page=page,
        page_size=page_size,
        exercise_type=exercise_type,
        learning_track_id=learning_track_id,
    )
    return ExerciseListResponse(
        items=result.items,
        page=result.page,
        page_size=result.page_size,
        total=result.total,
        total_pages=result.total_pages,
    )


@router.get("/{exercise_id}", response_model=ExerciseResponse)
def get_exercise(
    exercise_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ExerciseResponse:
    try:
        return ExerciseResponse.model_validate(
            get_owned_exercise(db, current_user.id, exercise_id)
        )
    except ExerciseNotFoundError as exc:
        raise _not_found() from exc


@router.post("/{exercise_id}/attempts", response_model=ExerciseAttemptResult)
def create_attempt(
    exercise_id: uuid.UUID,
    payload: ExerciseAttemptCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ExerciseAttemptResult:
    try:
        result = submit_attempt(db, current_user.id, exercise_id, payload.answer)
    except ExerciseNotFoundError as exc:
        raise _not_found() from exc
    except InvalidStoredExerciseError as exc:
        raise HTTPException(
            status_code=409,
            detail="Exercise answer configuration is invalid",
        ) from exc

    return ExerciseAttemptResult(
        id=result.attempt.id,
        exercise_id=result.attempt.exercise_id,
        user_answer=result.attempt.user_answer,
        is_correct=result.attempt.is_correct,
        correct_answer=result.attempt.correct_answer,
        explanation=result.explanation,
        completed_at=result.attempt.completed_at,
    )


@attempts_router.get("", response_model=ExerciseAttemptListResponse)
def list_attempts(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    exercise_id: uuid.UUID | None = None,
) -> ExerciseAttemptListResponse:
    result = list_owned_attempts(
        db,
        current_user.id,
        page=page,
        page_size=page_size,
        exercise_id=exercise_id,
    )
    return ExerciseAttemptListResponse(
        items=result.items,
        page=result.page,
        page_size=result.page_size,
        total=result.total,
        total_pages=result.total_pages,
    )
