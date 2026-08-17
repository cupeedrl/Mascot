from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.review import ReviewQueueResponse, ReviewSubmission
from app.schemas.vocabulary import VocabularyResponse
from app.services.review import (
    ReviewNotDueError,
    ReviewVocabularyNotFoundError,
    list_due_vocabularies,
    submit_review,
)

router = APIRouter(prefix="/vocabularies")


@router.get("/due-for-review", response_model=ReviewQueueResponse)
def due_for_review(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    learning_track_id: uuid.UUID | None = None,
) -> ReviewQueueResponse:
    queue = list_due_vocabularies(
        db,
        current_user.id,
        limit=limit,
        learning_track_id=learning_track_id,
    )
    return ReviewQueueResponse(items=queue.items, total=queue.total, limit=queue.limit)


@router.post("/{vocabulary_id}/reviews", response_model=VocabularyResponse)
def review_vocabulary(
    vocabulary_id: uuid.UUID,
    payload: ReviewSubmission,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> VocabularyResponse:
    try:
        return submit_review(
            db,
            current_user.id,
            vocabulary_id,
            is_correct=payload.is_correct,
        )
    except ReviewVocabularyNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Vocabulary item not found") from exc
    except ReviewNotDueError as exc:
        raise HTTPException(
            status_code=409,
            detail="Vocabulary item is not due for review",
        ) from exc

