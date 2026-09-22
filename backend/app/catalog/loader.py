from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.catalog.constants import GENERAL_ENGLISH_TRACK_ID, SEED_NAMESPACE
from app.catalog.schema import CatalogEntrySeed, CatalogSetSeed
from app.catalog.validator import validate_catalog_dataset
from app.models.learning_track import LearningTrack
from app.models.vocabulary_entry import VocabularyEntry
from app.models.vocabulary_set import VocabularySet
from app.services.normalization import normalize_word

DATA_DIR = Path(__file__).parent / "data"


def seed_set_id(
    code: str, track_id: uuid.UUID = GENERAL_ENGLISH_TRACK_ID
) -> uuid.UUID:
    key = f"set:{code}" if track_id == GENERAL_ENGLISH_TRACK_ID else f"set:{track_id}:{code}"
    return uuid.uuid5(SEED_NAMESPACE, key)


def seed_entry_id(
    set_code: str,
    word: str,
    part_of_speech: str,
    track_id: uuid.UUID = GENERAL_ENGLISH_TRACK_ID,
) -> uuid.UUID:
    prefix = "entry" if track_id == GENERAL_ENGLISH_TRACK_ID else f"entry:{track_id}"
    return uuid.uuid5(SEED_NAMESPACE, f"{prefix}:{set_code}:{word}:{part_of_speech}")


@dataclass
class CatalogLoadResult:
    sets_created: int = 0
    sets_updated: int = 0
    entries_created: int = 0
    entries_updated: int = 0


def load_catalog_from_dir(data_dir: Path) -> list[CatalogSetSeed]:
    sets: list[CatalogSetSeed] = []
    for file_path in sorted(data_dir.glob("*.json")):
        with open(file_path, "r", encoding="utf-8-sig") as f:
            raw = json.load(f)
            if isinstance(raw, list):
                for item in raw:
                    sets.append(CatalogSetSeed.model_validate(item))
            elif isinstance(raw, dict):
                sets.append(CatalogSetSeed.model_validate(raw))
    return sets


def load_catalog_into_db(
    db: Session,
    sets: Sequence[CatalogSetSeed],
    track_id: uuid.UUID = GENERAL_ENGLISH_TRACK_ID,
    *,
    validate_first: bool = True,
    batch_size: int = 500,
) -> CatalogLoadResult:
    """Load catalog datasets into the database with bulk prefetching and batching.

    Eliminates N+1 per-entry SELECT queries so remote database migrations
    (such as Neon PostgreSQL) complete in seconds rather than hanging on network round trips.
    """
    if validate_first:
        validate_catalog_dataset(sets, raise_on_error=True)
    track = db.get(LearningTrack, track_id)
    if track is None or any(
        item.level_framework != track.level_framework.upper() for item in sets
    ):
        raise ValueError("Catalog framework does not match the target learning track")

    result = CatalogLoadResult()

    # 1. Collect all target set IDs and entry IDs upfront
    set_plan: list[tuple[uuid.UUID, CatalogSetSeed]] = []
    entry_plan: list[tuple[uuid.UUID, uuid.UUID, CatalogEntrySeed, int]] = []

    for set_index, set_seed in enumerate(sets):
        s_id = seed_set_id(set_seed.code, track_id)
        set_plan.append((s_id, set_seed))
        for entry_index, entry_seed in enumerate(set_seed.entries):
            e_id = seed_entry_id(
                set_seed.code, entry_seed.word, entry_seed.part_of_speech, track_id
            )
            entry_plan.append((e_id, s_id, entry_seed, entry_index))

    # 2. Bulk prefetch existing VocabularySet rows
    all_set_ids = [s_id for s_id, _ in set_plan]
    existing_sets: dict[uuid.UUID, VocabularySet] = {}
    for i in range(0, len(all_set_ids), batch_size):
        chunk_ids = all_set_ids[i : i + batch_size]
        rows = db.scalars(select(VocabularySet).where(VocabularySet.id.in_(chunk_ids)))
        for s in rows:
            existing_sets[s.id] = s

    # 3. Bulk prefetch existing VocabularyEntry rows
    all_entry_ids = [e_id for e_id, _, _, _ in entry_plan]
    existing_entries: dict[uuid.UUID, VocabularyEntry] = {}
    for i in range(0, len(all_entry_ids), batch_size):
        chunk_ids = all_entry_ids[i : i + batch_size]
        rows = db.scalars(select(VocabularyEntry).where(VocabularyEntry.id.in_(chunk_ids)))
        for e in rows:
            existing_entries[e.id] = e

    # 4. Upsert VocabularySets in memory & stage additions
    new_sets: list[VocabularySet] = []
    for set_index, (s_id, set_seed) in enumerate(set_plan):
        if s_id in existing_sets:
            db_set = existing_sets[s_id]
            db_set.name = set_seed.display_name
            db_set.description = set_seed.display_description
            db_set.level_code = set_seed.level_code
            db_set.topic = set_seed.topic
            db_set.order_index = set_index
            result.sets_updated += 1
        else:
            db_set = VocabularySet(
                id=s_id,
                learning_track_id=track_id,
                name=set_seed.display_name,
                description=set_seed.display_description,
                level_code=set_seed.level_code,
                topic=set_seed.topic,
                order_index=set_index,
                is_active=True,
            )
            new_sets.append(db_set)
            existing_sets[s_id] = db_set
            result.sets_created += 1

    if new_sets:
        db.add_all(new_sets)
        # Flush sets so foreign key references are available for new entries
        db.flush()

    # 5. Upsert VocabularyEntries in memory & stage additions
    new_entries: list[VocabularyEntry] = []
    for e_id, s_id, entry_seed, entry_index in entry_plan:
        if e_id in existing_entries:
            db_entry = existing_entries[e_id]
            db_entry.ipa = entry_seed.ipa
            db_entry.meaning = entry_seed.meaning
            db_entry.translation = entry_seed.translation
            db_entry.example_sentences = entry_seed.example_sentences
            db_entry.order_index = entry_index
            result.entries_updated += 1
        else:
            db_entry = VocabularyEntry(
                id=e_id,
                vocabulary_set_id=s_id,
                word=entry_seed.word,
                normalized_word=normalize_word(entry_seed.word),
                ipa=entry_seed.ipa,
                part_of_speech=entry_seed.part_of_speech,
                meaning=entry_seed.meaning,
                translation=entry_seed.translation,
                translation_language_code=entry_seed.translation_language_code,
                example_sentences=entry_seed.example_sentences,
                order_index=entry_index,
            )
            new_entries.append(db_entry)
            existing_entries[e_id] = db_entry
            result.entries_created += 1

    if new_entries:
        for i in range(0, len(new_entries), batch_size):
            chunk = new_entries[i : i + batch_size]
            db.add_all(chunk)

    db.commit()
    return result
