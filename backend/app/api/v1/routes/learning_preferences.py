from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.learning_preference import (
    LearningPreferenceResponse,
    LearningPreferenceUpdate,
)
from app.services.learning_preference import (
    InvalidLearningPreferenceLevelError,
    LearningPreferenceTrackUnavailableError,
    get_learning_preference,
    set_learning_preference,
)

router = APIRouter(prefix="/learning-preferences")


def _track_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Learning track is not available",
    )


@router.get("/{learning_track_id}", response_model=LearningPreferenceResponse)
def read_learning_preference(
    learning_track_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> LearningPreferenceResponse:
    try:
        return LearningPreferenceResponse.model_validate(
            get_learning_preference(db, current_user.id, learning_track_id),
            from_attributes=True,
        )
    except LearningPreferenceTrackUnavailableError as exc:
        raise _track_not_found() from exc


@router.put("/{learning_track_id}", response_model=LearningPreferenceResponse)
def update_learning_preference(
    learning_track_id: uuid.UUID,
    payload: LearningPreferenceUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> LearningPreferenceResponse:
    try:
        snapshot = set_learning_preference(
            db,
            current_user.id,
            learning_track_id,
            payload.current_level_code,
        )
    except LearningPreferenceTrackUnavailableError as exc:
        raise _track_not_found() from exc
    except InvalidLearningPreferenceLevelError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Level is not valid for the selected learning track",
        ) from exc
    return LearningPreferenceResponse.model_validate(snapshot, from_attributes=True)
