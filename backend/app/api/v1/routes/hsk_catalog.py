"""Release-aware HSK 1–6 catalog: browse, search, detail and save.

The legacy ``/vocabulary-sets`` (v1) endpoints are unchanged and never read
these tables.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.hsk_catalog import (
    HskEntryDetailResponse,
    HskEntryListResponse,
    HskLevelsResponse,
    HskSaveRequest,
    HskSaveResponse,
    HskSensesImportRequest,
    HskSensesImportResponse,
    HskTopicDetailResponse,
    HskTopicSaveResponse,
)
from app.services.hsk_catalog import (
    HskEntryNotFoundError,
    HskReleaseNotFoundError,
    HskSaveRejectedError,
    HskTopicNotFoundError,
    HskTrackNotFoundError,
    get_entry,
    get_topic_detail,
    list_entries,
    list_levels,
    save_sense,
    save_senses,
    save_topic,
)

router = APIRouter(prefix="/catalog/hsk/{learning_track_id}")

TRACK_NOT_FOUND = "HSK learning track not found"


def _not_found(detail: str) -> HTTPException:
    return HTTPException(status_code=404, detail=detail)


@router.get("/levels", response_model=HskLevelsResponse)
def hsk_levels(
    learning_track_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    release_id: uuid.UUID | None = None,
) -> HskLevelsResponse:
    try:
        return HskLevelsResponse.model_validate(
            list_levels(db, current_user, learning_track_id, release_id)
        )
    except HskTrackNotFoundError as exc:
        raise _not_found(TRACK_NOT_FOUND) from exc
    except HskReleaseNotFoundError as exc:
        raise _not_found("Catalog release not found") from exc


@router.get("/entries", response_model=HskEntryListResponse)
def hsk_entries(
    learning_track_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    level: Annotated[str | None, Query(pattern="^HSK([1-6]|7-9)$")] = None,
    topic_id: uuid.UUID | None = None,
    q: Annotated[str | None, Query(max_length=64)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 30,
    release_id: uuid.UUID | None = None,
) -> HskEntryListResponse:
    try:
        return HskEntryListResponse.model_validate(
            list_entries(
                db,
                current_user,
                learning_track_id,
                level=level,
                query=q,
                page=page,
                page_size=page_size,
                release_id=release_id,
                topic_id=topic_id,
            )
        )
    except HskTrackNotFoundError as exc:
        raise _not_found(TRACK_NOT_FOUND) from exc
    except HskReleaseNotFoundError as exc:
        raise _not_found("Catalog release not found") from exc
    except HskTopicNotFoundError as exc:
        raise _not_found("Catalog topic not found") from exc


@router.get("/topics/{topic_id}", response_model=HskTopicDetailResponse)
def hsk_topic(
    learning_track_id: uuid.UUID,
    topic_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    part: Annotated[int | None, Query(ge=1)] = None,
) -> HskTopicDetailResponse:
    try:
        return HskTopicDetailResponse.model_validate(
            get_topic_detail(db, current_user, learning_track_id, topic_id, part)
        )
    except HskTrackNotFoundError as exc:
        raise _not_found(TRACK_NOT_FOUND) from exc
    except HskTopicNotFoundError as exc:
        raise _not_found("Catalog topic not found") from exc


@router.post("/senses/import", response_model=HskSensesImportResponse)
def hsk_import_senses(
    learning_track_id: uuid.UUID,
    payload: HskSensesImportRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> HskSensesImportResponse:
    try:
        result = save_senses(db, current_user, learning_track_id, payload.mapping_ids)
    except HskTrackNotFoundError as exc:
        raise _not_found(TRACK_NOT_FOUND) from exc
    except HskEntryNotFoundError as exc:
        raise _not_found("Catalog entry not found") from exc
    return HskSensesImportResponse(
        created_count=result.created_count,
        skipped_count=result.skipped_count,
        imported_mapping_ids=result.imported_mapping_ids,
    )


@router.post("/topics/{topic_id}/save-all", response_model=HskTopicSaveResponse)
def hsk_save_topic(
    learning_track_id: uuid.UUID,
    topic_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    part: Annotated[int | None, Query(ge=1)] = None,
) -> HskTopicSaveResponse:
    try:
        result = save_topic(db, current_user, learning_track_id, topic_id, part)
    except HskTrackNotFoundError as exc:
        raise _not_found(TRACK_NOT_FOUND) from exc
    except HskTopicNotFoundError as exc:
        raise _not_found("Catalog topic not found") from exc
    return HskTopicSaveResponse(created_count=result.created_count, skipped_count=result.skipped_count)


@router.get("/entries/{entry_id}", response_model=HskEntryDetailResponse)
def hsk_entry(
    learning_track_id: uuid.UUID,
    entry_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    release_id: uuid.UUID | None = None,
) -> HskEntryDetailResponse:
    try:
        return HskEntryDetailResponse.model_validate(
            get_entry(db, current_user, learning_track_id, entry_id, release_id)
        )
    except HskTrackNotFoundError as exc:
        raise _not_found(TRACK_NOT_FOUND) from exc
    except (HskReleaseNotFoundError, HskEntryNotFoundError) as exc:
        raise _not_found("Catalog entry not found") from exc


@router.post("/entries/{entry_id}/save", response_model=HskSaveResponse)
def hsk_save(
    learning_track_id: uuid.UUID,
    entry_id: uuid.UUID,
    payload: HskSaveRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> HskSaveResponse:
    try:
        result = save_sense(db, current_user, learning_track_id, entry_id, payload.mapping_id)
    except HskTrackNotFoundError as exc:
        raise _not_found(TRACK_NOT_FOUND) from exc
    except HskEntryNotFoundError as exc:
        raise _not_found("Catalog entry not found") from exc
    except HskSaveRejectedError as exc:
        raise HTTPException(
            status_code=409, detail={"message": exc.message, "code": exc.code}
        ) from exc
    return HskSaveResponse(
        created=result.created, vocabulary_id=result.vocabulary_id, reason=result.reason
    )
