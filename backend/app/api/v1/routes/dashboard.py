from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.dashboard import DashboardResponse, RecentVocabularyResponse
from app.services.dashboard import get_dashboard_snapshot

router = APIRouter(prefix="/dashboard")


@router.get("", response_model=DashboardResponse)
def get_dashboard(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> DashboardResponse:
    snapshot = get_dashboard_snapshot(db, current_user.id)
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
        recently_added_vocabulary=[
            RecentVocabularyResponse.model_validate(item)
            for item in snapshot.recently_added_vocabulary
        ],
    )
