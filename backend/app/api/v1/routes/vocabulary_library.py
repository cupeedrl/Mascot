from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.vocabulary import CEFRLevel
from app.schemas.vocabulary_library import (
    VocabularyEntryImportRequest,
    VocabularyImportResponse,
    VocabularySetDetailResponse,
    VocabularySetListResponse,
)
from app.services.vocabulary_library import (
    VocabularyEntryNotFoundError,
    VocabularySetNotFoundError,
    get_vocabulary_set,
    import_vocabulary_entries,
    import_vocabulary_set,
    list_vocabulary_sets,
)

router = APIRouter()


def _set_not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="Vocabulary set not found")


def _entry_not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="Vocabulary entry not found")


@router.get("/vocabulary-sets", response_model=VocabularySetListResponse)
def list_sets(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    language: Annotated[str | None, Query(max_length=16)] = None,
    learning_track: Annotated[str | None, Query(max_length=64)] = None,
    level: CEFRLevel | None = None,
    topic: Annotated[str | None, Query(max_length=120)] = None,
) -> VocabularySetListResponse:
    result = list_vocabulary_sets(
        db,
        current_user.id,
        page=page,
        page_size=page_size,
        language=language,
        learning_track=learning_track,
        level=level,
        topic=topic,
    )
    return VocabularySetListResponse(
        items=result.items,
        page=result.page,
        page_size=result.page_size,
        total=result.total,
        total_pages=result.total_pages,
    )


@router.get(
    "/vocabulary-sets/{vocabulary_set_id}",
    response_model=VocabularySetDetailResponse,
)
def get_set(
    vocabulary_set_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> VocabularySetDetailResponse:
    try:
        return VocabularySetDetailResponse.model_validate(
            get_vocabulary_set(db, current_user.id, vocabulary_set_id)
        )
    except VocabularySetNotFoundError as exc:
        raise _set_not_found() from exc


@router.post(
    "/vocabulary-entries/{entry_id}/add-to-my-vocabulary",
    response_model=VocabularyImportResponse,
)
def add_one_entry(
    entry_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> VocabularyImportResponse:
    try:
        result = import_vocabulary_entries(db, current_user.id, [entry_id])
    except VocabularyEntryNotFoundError as exc:
        raise _entry_not_found() from exc
    return VocabularyImportResponse(
        created_count=result.created_count,
        skipped_count=result.skipped_count,
        imported_entry_ids=result.imported_entry_ids,
    )


@router.post("/vocabulary-entries/import", response_model=VocabularyImportResponse)
def add_multiple_entries(
    payload: VocabularyEntryImportRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> VocabularyImportResponse:
    try:
        result = import_vocabulary_entries(db, current_user.id, payload.entry_ids)
    except VocabularyEntryNotFoundError as exc:
        raise _entry_not_found() from exc
    return VocabularyImportResponse(
        created_count=result.created_count,
        skipped_count=result.skipped_count,
        imported_entry_ids=result.imported_entry_ids,
    )


@router.post(
    "/vocabulary-sets/{vocabulary_set_id}/start-learning",
    response_model=VocabularyImportResponse,
)
def start_learning_set(
    vocabulary_set_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> VocabularyImportResponse:
    try:
        result = import_vocabulary_set(db, current_user.id, vocabulary_set_id)
    except VocabularySetNotFoundError as exc:
        raise _set_not_found() from exc
    return VocabularyImportResponse(
        created_count=result.created_count,
        skipped_count=result.skipped_count,
        imported_entry_ids=result.imported_entry_ids,
    )
