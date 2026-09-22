from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.catalog import LanguageResponse, LearningTrackResponse
from app.services.catalog import list_active_languages, list_active_learning_tracks

router = APIRouter()
catalog_router = APIRouter(prefix="/catalog")


@router.get("/languages", response_model=list[LanguageResponse])
@catalog_router.get("/languages", response_model=list[LanguageResponse])
def languages(
    _current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[LanguageResponse]:
    return list_active_languages(db)


@router.get("/learning-tracks", response_model=list[LearningTrackResponse])
@catalog_router.get("/learning-tracks", response_model=list[LearningTrackResponse])
def learning_tracks(
    _current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    language_code: Annotated[str | None, Query(min_length=1, max_length=16)] = None,
) -> list[LearningTrackResponse]:
    return list_active_learning_tracks(db, language_code)
