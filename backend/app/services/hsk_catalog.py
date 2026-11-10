"""Release-aware read and save services for the normalized HSK catalog.

Visibility rule: ordinary users see only the single ``published`` release of
an HSK track. There is no fallback to drafts or legacy sets. Admins may
preview a specific release by id.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from math import ceil
from typing import Any

from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.catalog.hsk_import import toneless_pinyin
from app.models.hsk_catalog import (
    CatalogRelease,
    CatalogSourceEntry,
    CatalogSourceEntryLevel,
    CatalogSourceMapping,
    LexicalEntry,
    LexicalPronunciation,
    LexicalSense,
)
from app.models.language import Language
from app.models.learning_track import LearningTrack
from app.models.user import User
from app.models.vocabulary import Vocabulary
from app.services.normalization import normalize_word
from app.services.vocabulary import vocabulary_senses_overlap

BROWSE_LEVELS = ("HSK1", "HSK2", "HSK3", "HSK4", "HSK5", "HSK6")
POS_UNSPECIFIED = "unspecified"


class HskTrackNotFoundError(Exception):
    pass


class HskReleaseNotFoundError(Exception):
    pass


class HskEntryNotFoundError(Exception):
    pass


class HskSaveRejectedError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


@dataclass(frozen=True)
class SaveResult:
    created: bool
    vocabulary_id: uuid.UUID
    reason: str | None = None


def _load_track(db: Session, track_id: uuid.UUID) -> LearningTrack:
    track = db.scalar(
        select(LearningTrack)
        .join(LearningTrack.language)
        .where(
            LearningTrack.id == track_id,
            LearningTrack.is_active.is_(True),
            Language.is_active.is_(True),
        )
    )
    if track is None or track.level_framework.strip().upper() != "HSK":
        raise HskTrackNotFoundError
    return track


def resolve_release(
    db: Session, user: User, track_id: uuid.UUID, release_id: uuid.UUID | None = None
) -> CatalogRelease | None:
    """Return the release a request may read, or ``None`` when none is published."""
    _load_track(db, track_id)
    if release_id is not None:
        if user.role != "admin":
            raise HskReleaseNotFoundError
        release = db.scalar(
            select(CatalogRelease).where(
                CatalogRelease.id == release_id, CatalogRelease.learning_track_id == track_id
            )
        )
        if release is None:
            raise HskReleaseNotFoundError
        return release
    return db.scalar(
        select(CatalogRelease).where(
            CatalogRelease.learning_track_id == track_id, CatalogRelease.status == "published"
        )
    )


def release_summary(release: CatalogRelease | None) -> dict[str, Any] | None:
    if release is None:
        return None
    return {
        "id": release.id,
        "code": release.code,
        "title": release.title,
        "status": release.status,
        "source_name": release.source_name,
        "source_version": release.source_version,
        "data_origin": release.data_origin,
        "published_at": release.published_at,
    }


def _primary_level_join(release_id: uuid.UUID):
    return and_(
        CatalogSourceEntryLevel.source_entry_id == CatalogSourceEntry.id,
        CatalogSourceEntryLevel.catalog_release_id == release_id,
        CatalogSourceEntryLevel.role == "primary",
    )


def list_levels(
    db: Session, user: User, track_id: uuid.UUID, release_id: uuid.UUID | None = None
) -> dict[str, Any]:
    release = resolve_release(db, user, track_id, release_id)
    counts: dict[str, dict[str, int]] = {
        level: {"entry_count": 0, "reviewed_count": 0, "awaiting_review_count": 0}
        for level in BROWSE_LEVELS
    }
    if release is not None:
        rows = db.execute(
            select(
                CatalogSourceEntryLevel.level_code,
                CatalogSourceEntry.review_status,
                func.count(),
            )
            .join(CatalogSourceEntry, _primary_level_join(release.id))
            .where(
                CatalogSourceEntry.catalog_release_id == release.id,
                CatalogSourceEntry.review_status != "retired",
            )
            .group_by(CatalogSourceEntryLevel.level_code, CatalogSourceEntry.review_status)
        ).all()
        for level_code, review_status, count in rows:
            if level_code not in counts:
                continue
            counts[level_code]["entry_count"] += count
            key = "reviewed_count" if review_status == "accepted" else "awaiting_review_count"
            counts[level_code][key] += count
    return {
        "release": release_summary(release),
        "levels": [{"level_code": level, **counts[level]} for level in BROWSE_LEVELS],
    }


def _approved_sense_counts(db: Session, entry_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    if not entry_ids:
        return {}
    return dict(
        db.execute(
            select(CatalogSourceMapping.source_entry_id, func.count(LexicalSense.id))
            .join(LexicalSense, LexicalSense.id == CatalogSourceMapping.sense_id)
            .where(
                CatalogSourceMapping.source_entry_id.in_(entry_ids),
                CatalogSourceMapping.review_status == "approved",
                LexicalSense.review_status == "approved",
                LexicalSense.status == "active",
            )
            .group_by(CatalogSourceMapping.source_entry_id)
        ).all()
    )


def _saved_counts(
    db: Session, user_id: uuid.UUID, entry_ids: list[uuid.UUID]
) -> dict[uuid.UUID, int]:
    if not entry_ids:
        return {}
    return dict(
        db.execute(
            select(Vocabulary.catalog_source_entry_id, func.count(Vocabulary.id))
            .where(
                Vocabulary.user_id == user_id,
                Vocabulary.catalog_source_entry_id.in_(entry_ids),
            )
            .group_by(Vocabulary.catalog_source_entry_id)
        ).all()
    )


def list_entries(
    db: Session,
    user: User,
    track_id: uuid.UUID,
    *,
    level: str | None,
    query: str | None,
    page: int,
    page_size: int,
    release_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    release = resolve_release(db, user, track_id, release_id)
    empty = {
        "release": release_summary(release),
        "items": [],
        "page": page,
        "page_size": page_size,
        "total": 0,
        "total_pages": 0,
    }
    if release is None:
        return empty
    conditions = [
        CatalogSourceEntry.catalog_release_id == release.id,
        CatalogSourceEntry.review_status != "retired",
    ]
    if level:
        conditions.append(CatalogSourceEntryLevel.level_code == level)
    else:
        conditions.append(CatalogSourceEntryLevel.level_code.in_(BROWSE_LEVELS))
    if query and (term := query.strip()):
        like = f"%{term.lower()}%"
        pinyin_term = toneless_pinyin(term)
        gloss_match = exists(
            select(CatalogSourceMapping.id)
            .join(LexicalSense, LexicalSense.id == CatalogSourceMapping.sense_id)
            .where(
                CatalogSourceMapping.source_entry_id == CatalogSourceEntry.id,
                CatalogSourceMapping.review_status == "approved",
                LexicalSense.review_status == "approved",
                LexicalSense.status == "active",
                or_(
                    func.lower(LexicalSense.gloss_en).like(like),
                    func.lower(LexicalSense.gloss_vi).like(like),
                ),
            )
        )
        options = [func.lower(CatalogSourceEntry.raw_word).like(like), gloss_match]
        if pinyin_term:
            options.append(CatalogSourceEntry.search_pinyin.like(f"{pinyin_term}%"))
        conditions.append(or_(*options))

    base = select(CatalogSourceEntry, CatalogSourceEntryLevel.level_code).join(
        CatalogSourceEntryLevel, _primary_level_join(release.id)
    ).where(*conditions)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = db.execute(
        base.order_by(
            CatalogSourceEntryLevel.level_code,
            CatalogSourceEntry.official_serial.is_(None),
            CatalogSourceEntry.official_serial,
            CatalogSourceEntry.source_record_id_value,
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    entry_ids = [entry.id for entry, _level in rows]
    sense_counts = _approved_sense_counts(db, entry_ids)
    saved_counts = _saved_counts(db, user.id, entry_ids)
    return {
        **empty,
        "items": [
            {
                "id": entry.id,
                "raw_word": entry.raw_word,
                "raw_pinyin": entry.raw_pinyin,
                "raw_pos": entry.raw_pos,
                "official_serial": entry.official_serial,
                "level_code": level_code,
                "review_status": entry.review_status,
                "sense_count": sense_counts.get(entry.id, 0),
                "saved_count": saved_counts.get(entry.id, 0),
            }
            for entry, level_code in rows
        ],
        "total": total,
        "total_pages": ceil(total / page_size) if total else 0,
    }


def _load_entry(db: Session, release: CatalogRelease, entry_id: uuid.UUID) -> CatalogSourceEntry:
    entry = db.scalar(
        select(CatalogSourceEntry)
        .options(selectinload(CatalogSourceEntry.levels))
        .where(
            CatalogSourceEntry.id == entry_id,
            CatalogSourceEntry.catalog_release_id == release.id,
        )
    )
    if entry is None:
        raise HskEntryNotFoundError
    return entry


def _sense_is_visible(sense: LexicalSense | None) -> bool:
    return sense is not None and sense.review_status == "approved" and sense.status == "active"


def get_entry(
    db: Session,
    user: User,
    track_id: uuid.UUID,
    entry_id: uuid.UUID,
    release_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    release = resolve_release(db, user, track_id, release_id)
    if release is None:
        raise HskEntryNotFoundError
    entry = _load_entry(db, release, entry_id)
    mappings = list(
        db.scalars(
            select(CatalogSourceMapping)
            .where(
                CatalogSourceMapping.source_entry_id == entry.id,
                CatalogSourceMapping.review_status == "approved",
            )
            .order_by(CatalogSourceMapping.order_index, CatalogSourceMapping.id)
        )
    )
    lexical_ids = list(dict.fromkeys(m.lexical_entry_id for m in mappings))
    lexicals = {
        lexical.id: lexical
        for lexical in db.scalars(
            select(LexicalEntry)
            .options(
                selectinload(LexicalEntry.pronunciations),
                selectinload(LexicalEntry.variants),
                selectinload(LexicalEntry.senses).selectinload(LexicalSense.pos),
                selectinload(LexicalEntry.senses).selectinload(LexicalSense.examples),
                selectinload(LexicalEntry.senses).selectinload(LexicalSense.pronunciation_links),
            )
            .where(LexicalEntry.id.in_(lexical_ids))
        )
    }
    # Sense identity is release-independent, so a sense saved from an earlier
    # release still counts as saved here.
    mapped_sense_ids = [m.sense_id for m in mappings if m.sense_id is not None]
    saved = {
        vocabulary.catalog_sense_id: vocabulary.id
        for vocabulary in db.scalars(
            select(Vocabulary).where(
                Vocabulary.user_id == user.id, Vocabulary.catalog_sense_id.in_(mapped_sense_ids)
            )
        )
    }
    saveable_release = release.status == "published" and entry.review_status != "retired"

    interpretations: list[dict[str, Any]] = []
    by_lexical: dict[uuid.UUID, dict[str, Any]] = {}
    for mapping in mappings:
        lexical = lexicals[mapping.lexical_entry_id]
        readings = {p.id: p.pinyin for p in lexical.pronunciations}
        group = by_lexical.get(lexical.id)
        if group is None:
            group = {
                "lexical_entry_id": lexical.id,
                "headword": lexical.headword,
                "lexical_key": lexical.lexical_key,
                "pronunciations": [],
                "variants": [
                    {
                        "form": v.variant_form,
                        "type": v.variant_type,
                        "pinyin": readings.get(v.pronunciation_id),
                        "source": v.variant_source,
                    }
                    for v in lexical.variants
                ],
                "senses": [],
                "awaiting_sense_review": False,
            }
            by_lexical[lexical.id] = group
            interpretations.append(group)
        if mapping.pronunciation_id and readings[mapping.pronunciation_id] not in group["pronunciations"]:
            group["pronunciations"].append(readings[mapping.pronunciation_id])
        sense = next((s for s in lexical.senses if s.id == mapping.sense_id), None)
        if mapping.sense_id is None or not _sense_is_visible(sense):
            group["awaiting_sense_review"] = True
            continue
        sense_readings = [readings[link.pronunciation_id] for link in sense.pronunciation_links]
        if mapping.pronunciation_id:
            sense_readings = [readings[mapping.pronunciation_id]]
        for reading in sense_readings:
            if reading not in group["pronunciations"]:
                group["pronunciations"].append(reading)
        missing_gloss = not (sense.gloss_en and sense.gloss_vi)
        group["senses"].append(
            {
                "mapping_id": mapping.id,
                "sense_id": sense.id,
                "sense_key": sense.sense_key,
                "gloss_en": sense.gloss_en,
                "gloss_vi": sense.gloss_vi,
                "gloss_source": sense.gloss_source,
                "pos": [
                    {"code": p.pos_code, "origin": p.pos_origin, "source_label": p.source_label}
                    for p in sorted(sense.pos, key=lambda item: item.pos_code)
                ],
                "pos_missing": not sense.pos,
                "pronunciations": sense_readings,
                "examples": [
                    {
                        "text_zh": e.text_zh,
                        "pinyin": e.pinyin,
                        "translation_vi": e.translation_vi,
                        "source": e.example_source,
                    }
                    for e in sense.examples
                ],
                "saveable": saveable_release and not missing_gloss,
                "saved_vocabulary_id": saved.get(sense.id),
            }
        )
    levels = sorted(entry.levels, key=lambda level: level.order_index)
    return {
        "release": release_summary(release),
        "source": {
            "id": entry.id,
            "record_id_type": entry.source_record_id_type,
            "record_id": entry.source_record_id_value,
            "official_serial": entry.official_serial,
            "raw_word": entry.raw_word,
            "raw_pinyin": entry.raw_pinyin,
            "raw_pos": entry.raw_pos,
            "raw_level_name": entry.raw_level_name,
            "levels": [{"level_code": level.level_code, "role": level.role} for level in levels],
            "review_status": entry.review_status,
            "review_flags": list(entry.review_flags or []),
        },
        "interpretations": interpretations,
    }


def save_sense(
    db: Session,
    user: User,
    track_id: uuid.UUID,
    entry_id: uuid.UUID,
    mapping_id: uuid.UUID,
    *,
    allow_retry: bool = True,
) -> SaveResult:
    """Copy one approved catalog interpretation into the user's vocabulary.

    Duplicate rule: one personal row per (user, sense). Saving the same sense
    again, from this or any later release, returns the existing row
    (``created=False``); the database enforces (user, source record, sense).
    A mapping without a sense (NULL / unspecialized) is never saveable because
    the snapshot would need a fabricated meaning.
    """
    release = resolve_release(db, user, track_id)
    if release is None:
        raise HskEntryNotFoundError
    entry = _load_entry(db, release, entry_id)
    if entry.review_status == "retired":
        raise HskSaveRejectedError("entry_retired", "Từ này đã ngừng sử dụng trong danh mục.")
    mapping = db.scalar(
        select(CatalogSourceMapping).where(
            CatalogSourceMapping.id == mapping_id,
            CatalogSourceMapping.source_entry_id == entry.id,
            CatalogSourceMapping.review_status == "approved",
        )
    )
    if mapping is None:
        raise HskEntryNotFoundError
    if mapping.sense_id is None:
        raise HskSaveRejectedError(
            "sense_required", "Nghĩa của từ này đang chờ biên tập, chưa thể lưu."
        )
    sense = db.scalar(
        select(LexicalSense)
        .options(
            selectinload(LexicalSense.pos),
            selectinload(LexicalSense.examples),
            selectinload(LexicalSense.pronunciation_links),
        )
        .where(LexicalSense.id == mapping.sense_id)
    )
    if not _sense_is_visible(sense) or not (sense.gloss_en and sense.gloss_vi):
        raise HskSaveRejectedError(
            "sense_not_saveable", "Nghĩa này chưa được duyệt đầy đủ, chưa thể lưu."
        )

    # DB guarantees one row per (user, source record, sense); the service also
    # treats the same sense saved from an earlier release as already saved.
    existing = db.scalar(
        select(Vocabulary)
        .where(Vocabulary.user_id == user.id, Vocabulary.catalog_sense_id == sense.id)
        .order_by(Vocabulary.created_at)
        .limit(1)
    )
    if existing is not None:
        return SaveResult(False, existing.id, "already_saved")

    lexical = db.get(LexicalEntry, mapping.lexical_entry_id)
    readings = {
        p.id: p.pinyin
        for p in db.scalars(
            select(LexicalPronunciation).where(
                LexicalPronunciation.lexical_entry_id == lexical.id
            )
        )
    }
    pronunciation_id = mapping.pronunciation_id
    linked = [link.pronunciation_id for link in sense.pronunciation_links]
    if pronunciation_id is None and len(linked) == 1:
        pronunciation_id = linked[0]
    if pronunciation_id is not None and pronunciation_id not in linked:
        pronunciation_id = None  # never store a pairing the catalog does not assert
    pinyin_display = (
        readings[pronunciation_id]
        if pronunciation_id is not None
        else (" / ".join(readings[p] for p in linked) or None)
    )
    pos_codes = sorted(p.pos_code for p in sense.pos)
    primary_level = next(
        (level.level_code for level in entry.levels if level.role == "primary"), None
    )
    if primary_level not in BROWSE_LEVELS:
        raise HskSaveRejectedError("level_out_of_scope", "Cấp độ HSK của từ này chưa được hỗ trợ.")

    for candidate in db.scalars(
        select(Vocabulary).where(
            Vocabulary.user_id == user.id, Vocabulary.learning_track_id == track_id
        )
    ):
        if vocabulary_senses_overlap(
            candidate, word=lexical.headword, meaning=sense.gloss_en, translation=sense.gloss_vi
        ):
            return SaveResult(False, candidate.id, "overlapping_personal_word")

    examples = [e.text_zh for e in sense.examples]
    snapshot = {
        "schema_version": 1,
        "saved_at": datetime.now(UTC).isoformat(),
        "release": {
            "id": str(release.id),
            "code": release.code,
            "title": release.title,
            "source_name": release.source_name,
            "source_version": release.source_version,
            "data_origin": release.data_origin,
        },
        "source": {
            "id": str(entry.id),
            "record_id_type": entry.source_record_id_type,
            "record_id": entry.source_record_id_value,
            "official_serial": entry.official_serial,
            "raw_word": entry.raw_word,
            "raw_pinyin": entry.raw_pinyin,
            "raw_pos": entry.raw_pos,
            "raw_level_name": entry.raw_level_name,
            "levels": [
                {"level_code": level.level_code, "role": level.role}
                for level in sorted(entry.levels, key=lambda item: item.order_index)
            ],
        },
        "lexical": {
            "id": str(lexical.id),
            "lexical_key": lexical.lexical_key,
            "headword": lexical.headword,
        },
        "sense": {
            "id": str(sense.id),
            "sense_key": sense.sense_key,
            "gloss_en": sense.gloss_en,
            "gloss_vi": sense.gloss_vi,
            "gloss_source": sense.gloss_source,
            "pos": pos_codes,
            "pos_missing": not pos_codes,
        },
        "pronunciation": {
            "id": str(pronunciation_id) if pronunciation_id else None,
            "pinyin": pinyin_display,
        },
        "examples": examples,
    }
    vocabulary = Vocabulary(
        user_id=user.id,
        learning_track_id=track_id,
        catalog_source_entry_id=entry.id,
        catalog_mapping_id=mapping.id,
        catalog_sense_id=sense.id,
        catalog_pronunciation_id=pronunciation_id,
        catalog_snapshot=snapshot,
        word=lexical.headword,
        normalized_word=normalize_word(lexical.headword),
        ipa=pinyin_display,
        part_of_speech=", ".join(pos_codes) if pos_codes else POS_UNSPECIFIED,
        meaning=sense.gloss_en,
        translation=sense.gloss_vi,
        translation_language_code="vi",
        example_sentences=examples[:1],
        level_code=primary_level,
        topic=None,
        learning_status="new",
    )
    db.add(vocabulary)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        if allow_retry:
            return save_sense(db, user, track_id, entry_id, mapping_id, allow_retry=False)
        raise
    return SaveResult(True, vocabulary.id)
