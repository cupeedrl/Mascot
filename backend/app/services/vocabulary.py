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
from app.learning_levels import is_valid_level
from app.schemas.vocabulary import VocabularyCreate, VocabularyUpdate
from app.services.normalization import (
    clean_topic,
    normalize_text,
    normalize_topic,
    normalize_word,
)

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


class DuplicateVocabularySenseError(Exception):
    def __init__(self, existing: Vocabulary) -> None:
        self.existing = existing
        super().__init__("Vocabulary sense overlaps an existing item")


class TopicNotFoundError(Exception):
    pass


@dataclass(frozen=True)
class VocabularyPage:
    items: list[Vocabulary]
    page: int
    page_size: int
    total: int
    total_pages: int


@dataclass(frozen=True)
class PersonalTopic:
    name: str
    vocabulary_count: int


def vocabulary_senses_overlap(
    existing: Vocabulary,
    *,
    word: str,
    meaning: str,
    translation: str,
) -> bool:
    return (
        normalize_word(existing.word) == normalize_word(word)
        and (
            normalize_text(existing.meaning) == normalize_text(meaning)
            or normalize_text(existing.translation) == normalize_text(translation)
        )
    )


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
    if not is_valid_level(track.level_framework, level_code):
        raise TrackLevelError


def _find_duplicate_sense(
    db: Session,
    user_id: uuid.UUID,
    *,
    learning_track_id: uuid.UUID,
    word: str,
    meaning: str,
    translation: str,
    exclude_vocabulary_id: uuid.UUID | None = None,
) -> Vocabulary | None:
    conditions = [
        Vocabulary.user_id == user_id,
        Vocabulary.learning_track_id == learning_track_id,
    ]
    if exclude_vocabulary_id is not None:
        conditions.append(Vocabulary.id != exclude_vocabulary_id)

    for existing in db.scalars(select(Vocabulary).where(*conditions)):
        if vocabulary_senses_overlap(
            existing,
            word=word,
            meaning=meaning,
            translation=translation,
        ):
            return existing
    return None


def _ensure_distinct_sense(
    db: Session,
    user_id: uuid.UUID,
    *,
    learning_track_id: uuid.UUID,
    word: str,
    meaning: str,
    translation: str,
    exclude_vocabulary_id: uuid.UUID | None = None,
) -> None:
    duplicate = _find_duplicate_sense(
        db,
        user_id,
        learning_track_id=learning_track_id,
        word=word,
        meaning=meaning,
        translation=translation,
        exclude_vocabulary_id=exclude_vocabulary_id,
    )
    if duplicate is not None:
        raise DuplicateVocabularySenseError(duplicate)


def create_vocabulary(
    db: Session, user_id: uuid.UUID, payload: VocabularyCreate
) -> Vocabulary:
    track = _load_active_track(db, payload.learning_track_id)
    _validate_level(track, payload.level_code)
    _ensure_distinct_sense(
        db,
        user_id,
        learning_track_id=track.id,
        word=payload.word,
        meaning=payload.meaning,
        translation=payload.translation,
    )
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
    if level and (normalized_level := level.strip().upper()):
        conditions.append(Vocabulary.level_code == normalized_level)
    if topic and (requested_topic := clean_topic(topic)):
        conditions.append(func.lower(Vocabulary.topic) == requested_topic.lower())
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

    _ensure_distinct_sense(
        db,
        user_id,
        learning_track_id=track.id,
        word=changes.get("word", item.word),
        meaning=changes.get("meaning", item.meaning),
        translation=changes.get("translation", item.translation),
        exclude_vocabulary_id=item.id,
    )

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


def list_personal_topics(
    db: Session,
    user_id: uuid.UUID,
    *,
    query: str | None,
    limit: int,
    learning_track_id: uuid.UUID | None = None,
) -> list[PersonalTopic]:
    conditions = [Vocabulary.user_id == user_id, Vocabulary.topic.is_not(None)]
    if learning_track_id is not None:
        conditions.append(Vocabulary.learning_track_id == learning_track_id)
    rows = db.execute(
        select(Vocabulary.topic, func.count(Vocabulary.id))
        .where(*conditions)
        .group_by(Vocabulary.topic)
    ).all()

    grouped: dict[str, dict[str, int]] = {}
    for raw_topic, count in rows:
        if not raw_topic or not (display_topic := clean_topic(raw_topic)):
            continue
        normalized = normalize_topic(display_topic)
        variants = grouped.setdefault(normalized, {})
        variants[display_topic] = variants.get(display_topic, 0) + int(count)

    requested = normalize_topic(query) if query and clean_topic(query) else ""
    topics: list[PersonalTopic] = []
    for normalized, variants in grouped.items():
        if requested and requested not in normalized:
            continue
        display_name = sorted(
            variants,
            key=lambda name: (-variants[name], name.casefold(), name),
        )[0]
        topics.append(
            PersonalTopic(
                name=display_name,
                vocabulary_count=sum(variants.values()),
            )
        )

    topics.sort(
        key=lambda item: (
            0 if requested and normalize_topic(item.name).startswith(requested) else 1,
            item.name.casefold(),
        )
    )
    return topics[:limit]


def rename_personal_topic(
    db: Session,
    user_id: uuid.UUID,
    *,
    old_topic: str,
    new_topic: str,
    learning_track_id: uuid.UUID | None = None,
) -> int:
    requested = normalize_topic(old_topic)
    replacement = clean_topic(new_topic)
    if replacement is None:
        raise ValueError("topic must not be blank")
    conditions = [Vocabulary.user_id == user_id, Vocabulary.topic.is_not(None)]
    if learning_track_id is not None:
        conditions.append(Vocabulary.learning_track_id == learning_track_id)
    items = list(
        db.scalars(
            select(Vocabulary).where(*conditions)
        )
    )
    matching = [item for item in items if normalize_topic(item.topic or "") == requested]
    if not matching:
        raise TopicNotFoundError
    for item in matching:
        item.topic = replacement
    db.commit()
    return len(matching)


def remove_personal_topic(
    db: Session,
    user_id: uuid.UUID,
    *,
    topic: str,
    learning_track_id: uuid.UUID | None = None,
) -> int:
    requested = normalize_topic(topic)
    conditions = [Vocabulary.user_id == user_id, Vocabulary.topic.is_not(None)]
    if learning_track_id is not None:
        conditions.append(Vocabulary.learning_track_id == learning_track_id)
    items = list(
        db.scalars(
            select(Vocabulary).where(*conditions)
        )
    )
    matching = [item for item in items if normalize_topic(item.topic or "") == requested]
    if not matching:
        raise TopicNotFoundError
    for item in matching:
        item.topic = None
    db.commit()
    return len(matching)
