from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models.learning_track import LearningTrack
from app.models.vocabulary import Vocabulary
from app.models.vocabulary_entry import VocabularyEntry

INCORRECT_RETRY_DELAY = timedelta(hours=1)
NEW_CORRECT_DELAY = timedelta(days=1)
LEARNING_CORRECT_DELAY = timedelta(days=3)


class ReviewVocabularyNotFoundError(Exception):
    pass


class ReviewNotDueError(Exception):
    pass


@dataclass(frozen=True)
class ReviewQueue:
    items: list[Vocabulary]
    total: int
    limit: int


def _load_options():
    return (
        joinedload(Vocabulary.learning_track).joinedload(LearningTrack.language),
        joinedload(Vocabulary.source_vocabulary_entry).joinedload(
            VocabularyEntry.vocabulary_set
        ),
    )


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _is_due(item: Vocabulary, reviewed_at: datetime) -> bool:
    if item.learning_status == "mastered":
        return False
    if item.next_review_at is None:
        return True
    return _as_utc(item.next_review_at) <= reviewed_at


def list_due_vocabularies(
    db: Session,
    user_id: uuid.UUID,
    *,
    limit: int,
    learning_track_id: uuid.UUID | None = None,
    now: datetime | None = None,
) -> ReviewQueue:
    current_time = now or _utc_now()
    conditions = [
        Vocabulary.user_id == user_id,
        Vocabulary.learning_status != "mastered",
        or_(
            Vocabulary.next_review_at.is_(None),
            Vocabulary.next_review_at <= current_time,
        ),
    ]
    if learning_track_id is not None:
        conditions.append(Vocabulary.learning_track_id == learning_track_id)

    total = db.scalar(select(func.count()).select_from(Vocabulary).where(*conditions)) or 0
    statement = (
        select(Vocabulary)
        .options(*_load_options())
        .where(*conditions)
        .order_by(
            case((Vocabulary.next_review_at.is_(None), 0), else_=1),
            Vocabulary.next_review_at.asc(),
            Vocabulary.created_at.asc(),
            Vocabulary.id.asc(),
        )
        .limit(limit)
    )
    return ReviewQueue(items=list(db.scalars(statement)), total=total, limit=limit)


def submit_review(
    db: Session,
    user_id: uuid.UUID,
    vocabulary_id: uuid.UUID,
    *,
    is_correct: bool,
    reviewed_at: datetime | None = None,
    force: bool = False,
) -> Vocabulary:
    current_time = reviewed_at or _utc_now()
    item = db.scalar(
        select(Vocabulary)
        .options(*_load_options())
        .where(Vocabulary.id == vocabulary_id, Vocabulary.user_id == user_id)
        # Lock only the owned vocabulary row. PostgreSQL rejects a broad
        # FOR UPDATE when joined eager loading includes nullable source data.
        .with_for_update(of=Vocabulary)
    )
    if item is None:
        raise ReviewVocabularyNotFoundError
    if not force and not _is_due(item, current_time):
        raise ReviewNotDueError

    item.review_count += 1
    item.last_reviewed_at = current_time

    if is_correct:
        item.correct_count += 1
        if item.learning_status == "new":
            item.learning_status = "learning"
            item.next_review_at = current_time + NEW_CORRECT_DELAY
        elif item.learning_status == "learning":
            item.learning_status = "review"
            item.next_review_at = current_time + LEARNING_CORRECT_DELAY
        else:
            item.learning_status = "mastered"
            item.next_review_at = None
    else:
        item.incorrect_count += 1
        item.learning_status = "learning"
        item.next_review_at = current_time + INCORRECT_RETRY_DELAY

    db.commit()
    db.refresh(item)
    return item
