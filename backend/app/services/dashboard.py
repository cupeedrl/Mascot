from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import and_, func, or_, select, union_all
from sqlalchemy.orm import Session

from app.models.exercise_attempt import ExerciseAttempt
from app.models.exercise import Exercise
from app.models.vocabulary import Vocabulary

RECENT_VOCABULARY_LIMIT = 6
RECENT_ACTIVITY_DAYS = 14
USER_FACING_TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")


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
    current_streak: int
    longest_streak: int
    recent_active_dates: list[date]
    recently_added_vocabulary: list[Vocabulary]


@dataclass(frozen=True)
class StudyCalendarSnapshot:
    year: int
    month: int
    today: date
    active_dates: list[date]
    current_streak: int
    longest_streak: int
    learning_track_id: uuid.UUID | None


def _to_user_facing_date(value: datetime) -> date:
    """Convert persisted UTC timestamps into the single V1 learner day boundary."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(USER_FACING_TIMEZONE).date()


def _calculate_streaks(
    activity_times: list[datetime], *, current_time: datetime
) -> tuple[int, int, list[date]]:
    active_dates = sorted({_to_user_facing_date(value) for value in activity_times})
    if not active_dates:
        return 0, 0, []

    active_date_set = set(active_dates)
    longest_streak = 1
    run_length = 1
    for previous, current in zip(active_dates, active_dates[1:]):
        if current == previous + timedelta(days=1):
            run_length += 1
        else:
            run_length = 1
        longest_streak = max(longest_streak, run_length)

    today = _to_user_facing_date(current_time)
    latest_active_date = active_dates[-1]
    current_streak = 0
    # A learner who was active yesterday still has an unbroken current streak.
    if latest_active_date <= today and (today - latest_active_date).days <= 1:
        cursor = latest_active_date
        while cursor in active_date_set:
            current_streak += 1
            cursor -= timedelta(days=1)

    recent_start = today - timedelta(days=RECENT_ACTIVITY_DAYS - 1)
    recent_active_dates = [day for day in active_dates if day >= recent_start]
    return current_streak, longest_streak, recent_active_dates


def _learning_activity_times(
    db: Session,
    user_id: uuid.UUID,
    learning_track_id: uuid.UUID | None = None,
) -> list[datetime]:
    """Return all meaningful learner action times using one union query."""
    vocabulary_conditions = [Vocabulary.user_id == user_id]
    exercise_conditions = [ExerciseAttempt.user_id == user_id]
    if learning_track_id is not None:
        vocabulary_conditions.append(Vocabulary.learning_track_id == learning_track_id)
        exercise_conditions.append(Exercise.learning_track_id == learning_track_id)
    activity_events = union_all(
        select(Vocabulary.created_at.label("occurred_at")).where(
            *vocabulary_conditions
        ),
        select(Vocabulary.last_reviewed_at.label("occurred_at")).where(
            *vocabulary_conditions,
            Vocabulary.last_reviewed_at.is_not(None),
        ),
        select(ExerciseAttempt.completed_at.label("occurred_at"))
        .join(Exercise, Exercise.id == ExerciseAttempt.exercise_id)
        .where(*exercise_conditions),
    ).subquery()
    return list(db.scalars(select(activity_events.c.occurred_at)))


def get_dashboard_snapshot(
    db: Session,
    user_id: uuid.UUID,
    *,
    now: datetime | None = None,
    learning_track_id: uuid.UUID | None = None,
) -> DashboardSnapshot:
    current_time = now or datetime.now(UTC)
    vocabulary_conditions = [Vocabulary.user_id == user_id]
    if learning_track_id is not None:
        vocabulary_conditions.append(Vocabulary.learning_track_id == learning_track_id)
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
        ).where(*vocabulary_conditions)
    ).one()

    attempt_conditions = [ExerciseAttempt.user_id == user_id]
    if learning_track_id is not None:
        attempt_conditions.append(Exercise.learning_track_id == learning_track_id)
    attempt_metrics = db.execute(
        select(
            func.count(ExerciseAttempt.id).label("exercises_completed"),
            func.count(ExerciseAttempt.id)
            .filter(ExerciseAttempt.is_correct.is_(True))
            .label("correct_exercise_attempts"),
            func.count(ExerciseAttempt.id)
            .filter(ExerciseAttempt.is_correct.is_(False))
            .label("incorrect_exercise_attempts"),
        )
        .join(Exercise, Exercise.id == ExerciseAttempt.exercise_id)
        .where(*attempt_conditions)
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
            .where(*vocabulary_conditions)
            .order_by(Vocabulary.created_at.desc(), Vocabulary.id.desc())
            .limit(RECENT_VOCABULARY_LIMIT)
        )
    )
    current_streak, longest_streak, recent_active_dates = _calculate_streaks(
        _learning_activity_times(db, user_id, learning_track_id),
        current_time=current_time,
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
        current_streak=current_streak,
        longest_streak=longest_streak,
        recent_active_dates=recent_active_dates,
        recently_added_vocabulary=recent_vocabulary,
    )


def get_study_calendar_snapshot(
    db: Session,
    user_id: uuid.UUID,
    *,
    year: int,
    month: int,
    now: datetime | None = None,
    learning_track_id: uuid.UUID | None = None,
) -> StudyCalendarSnapshot:
    """Return track-scoped learner activity for one calendar month."""
    current_time = now or datetime.now(UTC)
    activity_times = _learning_activity_times(db, user_id, learning_track_id)
    current_streak, longest_streak, _ = _calculate_streaks(
        activity_times,
        current_time=current_time,
    )
    active_dates = sorted(
        {
            activity_date
            for value in activity_times
            if (activity_date := _to_user_facing_date(value)).year == year
            and activity_date.month == month
        }
    )
    return StudyCalendarSnapshot(
        year=year,
        month=month,
        today=_to_user_facing_date(current_time),
        active_dates=active_dates,
        current_streak=current_streak,
        longest_streak=longest_streak,
        learning_track_id=learning_track_id,
    )
