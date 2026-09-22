from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.dashboard import (
    DashboardResponse,
    RecentVocabularyResponse,
    StudyCalendarResponse,
)
from app.services.dashboard import (
    get_dashboard_snapshot,
    get_study_calendar_snapshot,
)

router = APIRouter(prefix="/dashboard")


@router.get("/study-calendar", response_model=StudyCalendarResponse)
def get_study_calendar(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    year: Annotated[int, Query(ge=2000, le=2100)],
    month: Annotated[int, Query(ge=1, le=12)],
    learning_track_id: uuid.UUID | None = None,
) -> StudyCalendarResponse:
    snapshot = get_study_calendar_snapshot(
        db,
        current_user.id,
        year=year,
        month=month,
        learning_track_id=learning_track_id,
    )
    return StudyCalendarResponse(
        year=snapshot.year,
        month=snapshot.month,
        today=snapshot.today,
        active_dates=snapshot.active_dates,
        current_streak=snapshot.current_streak,
        longest_streak=snapshot.longest_streak,
        learning_track_id=snapshot.learning_track_id,
    )


@router.get("", response_model=DashboardResponse)
def get_dashboard(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    learning_track_id: uuid.UUID | None = None,
) -> DashboardResponse:
    snapshot = get_dashboard_snapshot(
        db, current_user.id, learning_track_id=learning_track_id
    )
    return DashboardResponse(
        total_vocabulary=snapshot.total_vocabulary,
        new_words=snapshot.new_words,
        learning_words=snapshot.learning_words,
        review_words=snapshot.review_words,
        mastered_words=snapshot.mastered_words,
        words_due_for_review=snapshot.words_due_for_review,
        exercises_completed=snapshot.exercises_completed,
        correct_exercise_attempts=snapshot.correct_exercise_attempts,
        incorrect_exercise_attempts=snapshot.incorrect_exercise_attempts,
        exercise_accuracy=snapshot.exercise_accuracy,
        current_streak=snapshot.current_streak,
        longest_streak=snapshot.longest_streak,
        recent_active_dates=snapshot.recent_active_dates,
        recently_added_vocabulary=[
            RecentVocabularyResponse.model_validate(item)
            for item in snapshot.recently_added_vocabulary
        ],
    )
