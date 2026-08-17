from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.models.exercise_attempt import ExerciseAttempt
from app.models.vocabulary import Vocabulary

RECENT_VOCABULARY_LIMIT = 6


@dataclass(frozen=True)
class DashboardSnapshot:
    total_vocabulary: int
    new_words: int
    learning_words: int
    review_words: int
    mastered_words: int
    words_due_for_review: int
    exercises_completed: int
    correct_exercise_attempts: int
    incorrect_exercise_attempts: int
    exercise_accuracy: float
    recently_added_vocabulary: list[Vocabulary]


def get_dashboard_snapshot(
    db: Session,
    user_id: uuid.UUID,
    *,
    now: datetime | None = None,
) -> DashboardSnapshot:
    current_time = now or datetime.now(UTC)
    vocabulary_metrics = db.execute(
        select(
            func.count(Vocabulary.id).label("total_vocabulary"),
            func.count(Vocabulary.id)
            .filter(Vocabulary.learning_status == "new")
            .label("new_words"),
            func.count(Vocabulary.id)
            .filter(Vocabulary.learning_status == "learning")
            .label("learning_words"),
            func.count(Vocabulary.id)
            .filter(Vocabulary.learning_status == "review")
            .label("review_words"),
            func.count(Vocabulary.id)
            .filter(Vocabulary.learning_status == "mastered")
            .label("mastered_words"),
            func.count(Vocabulary.id)
            .filter(
                and_(
                    Vocabulary.learning_status != "mastered",
                    or_(
                        Vocabulary.next_review_at.is_(None),
                        Vocabulary.next_review_at <= current_time,
                    ),
                )
            )
            .label("words_due_for_review"),
        ).where(Vocabulary.user_id == user_id)
    ).one()

    attempt_metrics = db.execute(
        select(
            func.count(ExerciseAttempt.id).label("exercises_completed"),
            func.count(ExerciseAttempt.id)
            .filter(ExerciseAttempt.is_correct.is_(True))
            .label("correct_exercise_attempts"),
            func.count(ExerciseAttempt.id)
            .filter(ExerciseAttempt.is_correct.is_(False))
            .label("incorrect_exercise_attempts"),
        ).where(ExerciseAttempt.user_id == user_id)
    ).one()

    exercises_completed = int(attempt_metrics.exercises_completed)
    correct_attempts = int(attempt_metrics.correct_exercise_attempts)
    exercise_accuracy = (
        round((correct_attempts / exercises_completed) * 100, 1)
        if exercises_completed
        else 0.0
    )

    recent_vocabulary = list(
        db.scalars(
            select(Vocabulary)
            .where(Vocabulary.user_id == user_id)
            .order_by(Vocabulary.created_at.desc(), Vocabulary.id.desc())
            .limit(RECENT_VOCABULARY_LIMIT)
        )
    )

    return DashboardSnapshot(
        total_vocabulary=int(vocabulary_metrics.total_vocabulary),
        new_words=int(vocabulary_metrics.new_words),
        learning_words=int(vocabulary_metrics.learning_words),
        review_words=int(vocabulary_metrics.review_words),
        mastered_words=int(vocabulary_metrics.mastered_words),
        words_due_for_review=int(vocabulary_metrics.words_due_for_review),
        exercises_completed=exercises_completed,
        correct_exercise_attempts=correct_attempts,
        incorrect_exercise_attempts=int(
            attempt_metrics.incorrect_exercise_attempts
        ),
        exercise_accuracy=exercise_accuracy,
        recently_added_vocabulary=recent_vocabulary,
    )
