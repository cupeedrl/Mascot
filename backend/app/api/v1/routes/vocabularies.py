from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.vocabulary import (
    LearningStatus,
    TopicMutationResponse,
    TopicRemoveRequest,
    TopicRenameRequest,
    TopicSuggestionListResponse,
    VocabularyCreate,
    VocabularyListResponse,
    VocabularyResponse,
    VocabularyUpdate,
)
from app.services.vocabulary import (
    DuplicateVocabularySenseError,
    LearningTrackUnavailableError,
    TopicNotFoundError,
    TrackLevelError,
    VocabularyNotFoundError,
    create_vocabulary,
    delete_vocabulary,
    get_owned_vocabulary,
    list_personal_topics,
    list_owned_vocabularies,
    remove_personal_topic,
    rename_personal_topic,
    update_vocabulary,
)

router = APIRouter(prefix="/vocabularies")


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="Vocabulary item not found")


def _track_unavailable() -> HTTPException:
    return HTTPException(status_code=400, detail="Learning track is not available")


def _track_level_invalid() -> HTTPException:
    return HTTPException(
        status_code=422,
        detail="Level is not valid for the selected learning track",
    )


def _duplicate_sense(exc: DuplicateVocabularySenseError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "message": (
                "This word already exists in My Vocabulary with the same or "
                "overlapping meaning. Edit the existing entry or add a genuinely "
                "different sense."
            ),
            "existing_vocabulary_id": str(exc.existing.id),
        },
    )


def _topic_not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="Personal topic not found")


@router.post("", response_model=VocabularyResponse, status_code=status.HTTP_201_CREATED)
def create(
    payload: VocabularyCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> VocabularyResponse:
    try:
        return create_vocabulary(db, current_user.id, payload)
    except LearningTrackUnavailableError as exc:
        raise _track_unavailable() from exc
    except TrackLevelError as exc:
        raise _track_level_invalid() from exc
    except DuplicateVocabularySenseError as exc:
        raise _duplicate_sense(exc) from exc


@router.get("", response_model=VocabularyListResponse)
def list_items(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    q: Annotated[str | None, Query(max_length=255)] = None,
    learning_status: LearningStatus | None = None,
    level: Annotated[str | None, Query(min_length=1, max_length=32)] = None,
    topic: Annotated[str | None, Query(max_length=120)] = None,
    learning_track_id: uuid.UUID | None = None,
) -> VocabularyListResponse:
    result = list_owned_vocabularies(
        db,
        current_user.id,
        page=page,
        page_size=page_size,
        query=q,
        learning_status=learning_status,
        level=level,
        topic=topic,
        learning_track_id=learning_track_id,
    )
    return VocabularyListResponse(
        items=result.items,
        page=result.page,
        page_size=result.page_size,
        total=result.total,
        total_pages=result.total_pages,
    )


@router.get("/topics", response_model=TopicSuggestionListResponse)
def list_topics(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    q: Annotated[str | None, Query(max_length=120)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    learning_track_id: uuid.UUID | None = None,
) -> TopicSuggestionListResponse:
    return TopicSuggestionListResponse(
        items=list_personal_topics(
            db,
            current_user.id,
            query=q,
            limit=limit,
            learning_track_id=learning_track_id,
        )
    )


@router.patch("/topics", response_model=TopicMutationResponse)
def rename_topic(
    payload: TopicRenameRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> TopicMutationResponse:
    try:
        count = rename_personal_topic(
            db,
            current_user.id,
            old_topic=payload.old_topic,
            new_topic=payload.new_topic,
            learning_track_id=payload.learning_track_id,
        )
    except TopicNotFoundError as exc:
        raise _topic_not_found() from exc
    return TopicMutationResponse(updated_count=count)


@router.delete("/topics", response_model=TopicMutationResponse)
def remove_topic(
    payload: TopicRemoveRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> TopicMutationResponse:
    try:
        count = remove_personal_topic(
            db,
            current_user.id,
            topic=payload.topic,
            learning_track_id=payload.learning_track_id,
        )
    except TopicNotFoundError as exc:
        raise _topic_not_found() from exc
    return TopicMutationResponse(updated_count=count)


@router.get("/{vocabulary_id}", response_model=VocabularyResponse)
def get_one(
    vocabulary_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> VocabularyResponse:
    try:
        return get_owned_vocabulary(db, current_user.id, vocabulary_id)
    except VocabularyNotFoundError as exc:
        raise _not_found() from exc


@router.patch("/{vocabulary_id}", response_model=VocabularyResponse)
def update(
    vocabulary_id: uuid.UUID,
    payload: VocabularyUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> VocabularyResponse:
    try:
        return update_vocabulary(db, current_user.id, vocabulary_id, payload)
    except VocabularyNotFoundError as exc:
        raise _not_found() from exc
    except LearningTrackUnavailableError as exc:
        raise _track_unavailable() from exc
    except TrackLevelError as exc:
        raise _track_level_invalid() from exc
    except DuplicateVocabularySenseError as exc:
        raise _duplicate_sense(exc) from exc


@router.delete("/{vocabulary_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete(
    vocabulary_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    try:
        delete_vocabulary(db, current_user.id, vocabulary_id)
    except VocabularyNotFoundError as exc:
        raise _not_found() from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
