from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload

from app.models.exercise import Exercise
from app.models.exercise_attempt import ExerciseAttempt
from app.models.language import Language
from app.models.learning_track import LearningTrack
from app.models.vocabulary import Vocabulary
from app.services.dashboard import get_dashboard_snapshot
from app.services.learning_preference import get_stored_current_level
from app.services.normalization import clean_topic, normalize_topic

RECENT_ATTEMPT_LIMIT = 20
RECENT_TOPIC_SOURCE_LIMIT = 20
WEAK_TOPIC_MIN_DUE_WORDS = 2
PROFILE_TOPIC_LIMIT = 3


class LearningProfileTrackUnavailableError(Exception):
    pass


@dataclass(frozen=True)
class LearningProfileSnapshot:
    language_code: str
    language_name: str
    track_code: str
    track_name: str
    framework: str
    current_level: str | None
    total_vocabulary: int
    new_words: int
    learning_words: int
    review_words: int
    mastered_words: int
    due_words: int
    recent_accuracy: float | None
    recent_attempts: int
    current_streak: int
    weak_topics: list[str]
    recent_topics: list[str]
    recent_active_dates: list[date]


def _resolve_track(
    db: Session, learning_track_id: uuid.UUID | None
) -> LearningTrack:
    statement = (
        select(LearningTrack)
        .join(LearningTrack.language)
        .options(joinedload(LearningTrack.language))
        .where(
            LearningTrack.is_active.is_(True),
            Language.is_active.is_(True),
        )
    )
    if learning_track_id is not None:
        statement = statement.where(LearningTrack.id == learning_track_id)
    else:
        statement = statement.where(
            Language.code == "en", LearningTrack.code == "general-english"
        )
    track = db.scalar(statement)
    if track is None:
        raise LearningProfileTrackUnavailableError
    return track


def _recent_accuracy(
    db: Session, user_id: uuid.UUID, learning_track_id: uuid.UUID
) -> tuple[float | None, int]:
    results = list(
        db.scalars(
            select(ExerciseAttempt.is_correct)
            .join(Exercise, Exercise.id == ExerciseAttempt.exercise_id)
            .where(
                ExerciseAttempt.user_id == user_id,
                Exercise.learning_track_id == learning_track_id,
            )
            .order_by(
                ExerciseAttempt.completed_at.desc(), ExerciseAttempt.id.desc()
            )
            .limit(RECENT_ATTEMPT_LIMIT)
        )
    )
    if not results:
        return None, 0
    return round(sum(1 for result in results if result) / len(results), 2), len(results)


def _weak_topics(
    db: Session,
    user_id: uuid.UUID,
    learning_track_id: uuid.UUID,
    current_time: datetime,
) -> list[str]:
    topics = list(
        db.scalars(
            select(Vocabulary.topic).where(
                Vocabulary.user_id == user_id,
                Vocabulary.learning_track_id == learning_track_id,
                Vocabulary.learning_status != "mastered",
                Vocabulary.topic.is_not(None),
                or_(
                    Vocabulary.next_review_at.is_(None),
                    Vocabulary.next_review_at <= current_time,
                ),
            )
        )
    )
    counts: dict[str, tuple[str, int]] = {}
    for raw_topic in topics:
        display = clean_topic(raw_topic)
        if not display or normalize_topic(display) == normalize_topic("Khác"):
            continue
        key = normalize_topic(display)
        previous_display, count = counts.get(key, (display, 0))
        counts[key] = (previous_display, count + 1)
    ranked = sorted(
        (
            (display, count)
            for display, count in counts.values()
            if count >= WEAK_TOPIC_MIN_DUE_WORDS
        ),
        key=lambda item: (-item[1], item[0].casefold()),
    )
    return [display for display, _count in ranked[:PROFILE_TOPIC_LIMIT]]


def _recent_topics(
    db: Session, user_id: uuid.UUID, learning_track_id: uuid.UUID
) -> list[str]:
    rows = list(
        db.scalars(
            select(Vocabulary.topic)
            .where(
                Vocabulary.user_id == user_id,
                Vocabulary.learning_track_id == learning_track_id,
                Vocabulary.topic.is_not(None),
            )
            .order_by(Vocabulary.created_at.desc(), Vocabulary.id.desc())
            .limit(RECENT_TOPIC_SOURCE_LIMIT)
        )
    )
    result: list[str] = []
    seen: set[str] = set()
    for raw_topic in rows:
        display = clean_topic(raw_topic)
        if not display:
            continue
        key = normalize_topic(display)
        if key in seen:
            continue
        seen.add(key)
        result.append(display)
        if len(result) == PROFILE_TOPIC_LIMIT:
            break
    return result


def get_learning_profile(
    db: Session,
    user_id: uuid.UUID,
    *,
    learning_track_id: uuid.UUID | None,
    now: datetime | None = None,
) -> LearningProfileSnapshot:
    track = _resolve_track(db, learning_track_id)
    snapshot = get_dashboard_snapshot(
        db, user_id, now=now, learning_track_id=track.id
    )
    current_time = now or datetime.now(UTC)
    recent_accuracy, recent_attempts = _recent_accuracy(db, user_id, track.id)
    return LearningProfileSnapshot(
        language_code=track.language.code,
        language_name=track.language.name,
        track_code=track.code,
        track_name=track.name,
        framework=track.level_framework,
        current_level=get_stored_current_level(db, user_id, track.id),
        total_vocabulary=snapshot.total_vocabulary,
        new_words=snapshot.new_words,
        learning_words=snapshot.learning_words,
        review_words=snapshot.review_words,
        mastered_words=snapshot.mastered_words,
        due_words=snapshot.words_due_for_review,
        recent_accuracy=recent_accuracy,
        recent_attempts=recent_attempts,
        current_streak=snapshot.current_streak,
        weak_topics=_weak_topics(db, user_id, track.id, current_time),
        recent_topics=_recent_topics(db, user_id, track.id),
        recent_active_dates=snapshot.recent_active_dates,
    )
