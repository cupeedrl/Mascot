from __future__ import annotations

import uuid
from dataclasses import dataclass
from math import ceil

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.language import Language
from app.models.learning_track import LearningTrack
from app.models.vocabulary import Vocabulary
from app.models.vocabulary_entry import VocabularyEntry
from app.models.vocabulary_set import VocabularySet


class VocabularySetNotFoundError(Exception):
    pass


class VocabularyEntryNotFoundError(Exception):
    pass


@dataclass(frozen=True)
class VocabularySetPage:
    items: list[dict[str, object]]
    page: int
    page_size: int
    total: int
    total_pages: int


@dataclass(frozen=True)
class VocabularyImportResult:
    created_count: int
    skipped_count: int
    imported_entry_ids: list[uuid.UUID]


def _track_filter(value: str):
    try:
        return LearningTrack.id == uuid.UUID(value)
    except ValueError:
        return LearningTrack.code == value.strip().lower()


def _set_counts(
    db: Session, user_id: uuid.UUID, set_ids: list[uuid.UUID]
) -> tuple[dict[uuid.UUID, int], dict[uuid.UUID, int]]:
    if not set_ids:
        return {}, {}
    entry_counts = dict(
        db.execute(
            select(VocabularyEntry.vocabulary_set_id, func.count(VocabularyEntry.id))
            .where(VocabularyEntry.vocabulary_set_id.in_(set_ids))
            .group_by(VocabularyEntry.vocabulary_set_id)
        ).all()
    )
    added_counts = dict(
        db.execute(
            select(VocabularyEntry.vocabulary_set_id, func.count(Vocabulary.id))
            .join(
                Vocabulary,
                Vocabulary.source_vocabulary_entry_id == VocabularyEntry.id,
            )
            .where(
                Vocabulary.user_id == user_id,
                VocabularyEntry.vocabulary_set_id.in_(set_ids),
            )
            .group_by(VocabularyEntry.vocabulary_set_id)
        ).all()
    )
    return entry_counts, added_counts


def _set_item(
    item: VocabularySet, entry_count: int, added_count: int
) -> dict[str, object]:
    if added_count == 0:
        import_status = "none"
    elif added_count >= entry_count:
        import_status = "all"
    else:
        import_status = "partial"
    return {
        "id": item.id,
        "name": item.name,
        "description": item.description,
        "level_code": item.level_code,
        "topic": item.topic,
        "order_index": item.order_index,
        "learning_track": item.learning_track,
        "entry_count": entry_count,
        "added_count": added_count,
        "import_status": import_status,
    }


def list_vocabulary_sets(
    db: Session,
    user_id: uuid.UUID,
    *,
    page: int,
    page_size: int,
    language: str | None = None,
    learning_track: str | None = None,
    level: str | None = None,
    topic: str | None = None,
) -> VocabularySetPage:
    conditions = [
        VocabularySet.is_active.is_(True),
        LearningTrack.is_active.is_(True),
        Language.is_active.is_(True),
    ]
    if language:
        conditions.append(Language.code == language.strip().lower())
    if learning_track:
        conditions.append(_track_filter(learning_track))
    if level:
        conditions.append(VocabularySet.level_code == level)
    if topic and (clean_topic := topic.strip()):
        conditions.append(func.lower(VocabularySet.topic) == clean_topic.lower())

    base = (
        select(VocabularySet)
        .join(VocabularySet.learning_track)
        .join(LearningTrack.language)
        .where(*conditions)
    )
    total = db.scalar(
        select(func.count())
        .select_from(VocabularySet)
        .join(VocabularySet.learning_track)
        .join(LearningTrack.language)
        .where(*conditions)
    ) or 0
    sets = list(
        db.scalars(
            base.options(
                joinedload(VocabularySet.learning_track).joinedload(
                    LearningTrack.language
                )
            )
            .order_by(VocabularySet.level_code, VocabularySet.order_index, VocabularySet.name)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    entry_counts, added_counts = _set_counts(db, user_id, [item.id for item in sets])
    return VocabularySetPage(
        items=[
            _set_item(item, entry_counts.get(item.id, 0), added_counts.get(item.id, 0))
            for item in sets
        ],
        page=page,
        page_size=page_size,
        total=total,
        total_pages=ceil(total / page_size) if total else 0,
    )


def get_vocabulary_set(
    db: Session, user_id: uuid.UUID, vocabulary_set_id: uuid.UUID
) -> dict[str, object]:
    item = db.scalar(
        select(VocabularySet)
        .join(VocabularySet.learning_track)
        .join(LearningTrack.language)
        .options(
            joinedload(VocabularySet.learning_track).joinedload(LearningTrack.language),
            selectinload(VocabularySet.entries),
        )
        .where(
            VocabularySet.id == vocabulary_set_id,
            VocabularySet.is_active.is_(True),
            LearningTrack.is_active.is_(True),
            Language.is_active.is_(True),
        )
    )
    if item is None:
        raise VocabularySetNotFoundError

    entry_ids = [entry.id for entry in item.entries]
    added_ids = set(
        db.scalars(
            select(Vocabulary.source_vocabulary_entry_id).where(
                Vocabulary.user_id == user_id,
                Vocabulary.source_vocabulary_entry_id.in_(entry_ids),
            )
        )
    )
    result = _set_item(item, len(item.entries), len(added_ids))
    result["entries"] = [
        {
            "id": entry.id,
            "word": entry.word,
            "normalized_word": entry.normalized_word,
            "part_of_speech": entry.part_of_speech,
            "meaning": entry.meaning,
            "translation": entry.translation,
            "translation_language_code": entry.translation_language_code,
            "example_sentences": entry.example_sentences,
            "order_index": entry.order_index,
            "is_added": entry.id in added_ids,
        }
        for entry in item.entries
    ]
    return result


def import_vocabulary_entries(
    db: Session,
    user_id: uuid.UUID,
    entry_ids: list[uuid.UUID],
    *,
    allow_retry: bool = True,
) -> VocabularyImportResult:
    unique_ids = list(dict.fromkeys(entry_ids))
    entries = list(
        db.scalars(
            select(VocabularyEntry)
            .join(VocabularyEntry.vocabulary_set)
            .join(VocabularySet.learning_track)
            .join(LearningTrack.language)
            .options(
                joinedload(VocabularyEntry.vocabulary_set)
                .joinedload(VocabularySet.learning_track)
                .joinedload(LearningTrack.language)
            )
            .where(
                VocabularyEntry.id.in_(unique_ids),
                VocabularySet.is_active.is_(True),
                LearningTrack.is_active.is_(True),
                Language.is_active.is_(True),
            )
        )
    )
    if len(entries) != len(unique_ids):
        raise VocabularyEntryNotFoundError

    existing_ids = set(
        db.scalars(
            select(Vocabulary.source_vocabulary_entry_id).where(
                Vocabulary.user_id == user_id,
                Vocabulary.source_vocabulary_entry_id.in_(unique_ids),
            )
        )
    )
    to_create = [entry for entry in entries if entry.id not in existing_ids]
    for entry in to_create:
        source_set = entry.vocabulary_set
        db.add(
            Vocabulary(
                user_id=user_id,
                learning_track_id=source_set.learning_track_id,
                source_vocabulary_entry_id=entry.id,
                word=entry.word,
                normalized_word=entry.normalized_word,
                part_of_speech=entry.part_of_speech,
                meaning=entry.meaning,
                translation=entry.translation,
                translation_language_code=entry.translation_language_code,
                example_sentences=list(entry.example_sentences),
                level_code=source_set.level_code,
                topic=source_set.topic,
                learning_status="new",
            )
        )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        if allow_retry:
            return import_vocabulary_entries(
                db, user_id, unique_ids, allow_retry=False
            )
        raise

    return VocabularyImportResult(
        created_count=len(to_create),
        skipped_count=len(unique_ids) - len(to_create),
        imported_entry_ids=[entry.id for entry in to_create],
    )


def import_vocabulary_set(
    db: Session, user_id: uuid.UUID, vocabulary_set_id: uuid.UUID
) -> VocabularyImportResult:
    detail = get_vocabulary_set(db, user_id, vocabulary_set_id)
    entry_ids = [entry["id"] for entry in detail["entries"]]
    return import_vocabulary_entries(db, user_id, entry_ids)
