from __future__ import annotations

import uuid
from dataclasses import dataclass
from math import ceil

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models.language import Language
from app.models.learning_track import LearningTrack
from app.models.vocabulary import Vocabulary
from app.models.vocabulary_entry import VocabularyEntry
from app.schemas.vocabulary import VocabularyCreate, VocabularyUpdate
from app.services.normalization import normalize_word

CEFR_LEVELS = {"A1", "A2", "B1", "B2", "C1", "C2"}


def _vocabulary_load_options():
    return (
        joinedload(Vocabulary.learning_track).joinedload(LearningTrack.language),
        joinedload(Vocabulary.source_vocabulary_entry).joinedload(
            VocabularyEntry.vocabulary_set
        ),
    )


class VocabularyNotFoundError(Exception):
    pass


class LearningTrackUnavailableError(Exception):
    pass


class TrackLevelError(Exception):
    pass


@dataclass(frozen=True)
class VocabularyPage:
    items: list[Vocabulary]
    page: int
    page_size: int
    total: int
    total_pages: int


def _load_active_track(db: Session, track_id: uuid.UUID) -> LearningTrack:
    track = db.scalar(
        select(LearningTrack)
        .join(LearningTrack.language)
        .options(joinedload(LearningTrack.language))
        .where(
            LearningTrack.id == track_id,
            LearningTrack.is_active.is_(True),
            Language.is_active.is_(True),
        )
    )
    if track is None:
        raise LearningTrackUnavailableError
    return track


def _validate_level(track: LearningTrack, level_code: str) -> None:
    if track.level_framework != "CEFR" or level_code not in CEFR_LEVELS:
        raise TrackLevelError


def create_vocabulary(
    db: Session, user_id: uuid.UUID, payload: VocabularyCreate
) -> Vocabulary:
    track = _load_active_track(db, payload.learning_track_id)
    _validate_level(track, payload.level_code)
    data = payload.model_dump()
    item = Vocabulary(
        **data,
        user_id=user_id,
        normalized_word=normalize_word(payload.word),
        learning_track=track,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def get_owned_vocabulary(
    db: Session, user_id: uuid.UUID, vocabulary_id: uuid.UUID
) -> Vocabulary:
    item = db.scalar(
        select(Vocabulary)
        .options(*_vocabulary_load_options())
        .where(Vocabulary.id == vocabulary_id, Vocabulary.user_id == user_id)
    )
    if item is None:
        raise VocabularyNotFoundError
    return item


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def list_owned_vocabularies(
    db: Session,
    user_id: uuid.UUID,
    *,
    page: int,
    page_size: int,
    query: str | None = None,
    learning_status: str | None = None,
    level: str | None = None,
    topic: str | None = None,
    learning_track_id: uuid.UUID | None = None,
) -> VocabularyPage:
    conditions = [Vocabulary.user_id == user_id]

    if query and (clean_query := query.strip()):
        pattern = f"%{_escape_like(normalize_word(clean_query))}%"
        conditions.append(
            or_(
                Vocabulary.normalized_word.like(pattern, escape="\\"),
                func.lower(Vocabulary.word).like(pattern, escape="\\"),
                func.lower(Vocabulary.meaning).like(pattern, escape="\\"),
                func.lower(Vocabulary.translation).like(pattern, escape="\\"),
            )
        )
    if learning_status:
        conditions.append(Vocabulary.learning_status == learning_status)
    if level:
        conditions.append(Vocabulary.level_code == level)
    if topic and (clean_topic := topic.strip()):
        conditions.append(func.lower(Vocabulary.topic) == clean_topic.lower())
    if learning_track_id:
        conditions.append(Vocabulary.learning_track_id == learning_track_id)

    total = db.scalar(select(func.count()).select_from(Vocabulary).where(*conditions)) or 0
    statement = (
        select(Vocabulary)
        .options(*_vocabulary_load_options())
        .where(*conditions)
        .order_by(Vocabulary.created_at.desc(), Vocabulary.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = list(db.scalars(statement))
    return VocabularyPage(
        items=items,
        page=page,
        page_size=page_size,
        total=total,
        total_pages=ceil(total / page_size) if total else 0,
    )


def update_vocabulary(
    db: Session,
    user_id: uuid.UUID,
    vocabulary_id: uuid.UUID,
    payload: VocabularyUpdate,
) -> Vocabulary:
    item = get_owned_vocabulary(db, user_id, vocabulary_id)
    changes = payload.model_dump(exclude_unset=True)

    track = item.learning_track
    if "learning_track_id" in changes:
        track = _load_active_track(db, changes["learning_track_id"])
        item.learning_track = track
    resulting_level = changes.get("level_code", item.level_code)
    _validate_level(track, resulting_level)

    for field_name, value in changes.items():
        setattr(item, field_name, value)
    if "word" in changes:
        item.normalized_word = normalize_word(changes["word"])

    db.commit()
    db.refresh(item)
    return item


def delete_vocabulary(
    db: Session, user_id: uuid.UUID, vocabulary_id: uuid.UUID
) -> None:
    item = get_owned_vocabulary(db, user_id, vocabulary_id)
    db.delete(item)
    db.commit()
