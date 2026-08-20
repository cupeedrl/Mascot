from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.catalog.constants import GENERAL_ENGLISH_TRACK_ID, SEED_NAMESPACE
from app.catalog.schema import CatalogSetSeed
from app.catalog.validator import validate_catalog_dataset
from app.models.vocabulary_entry import VocabularyEntry
from app.models.vocabulary_set import VocabularySet
from app.services.normalization import normalize_word

DATA_DIR = Path(__file__).parent / "data"


def seed_set_id(code: str) -> uuid.UUID:
    return uuid.uuid5(SEED_NAMESPACE, f"set:{code}")


def seed_entry_id(set_code: str, word: str, part_of_speech: str) -> uuid.UUID:
    return uuid.uuid5(SEED_NAMESPACE, f"entry:{set_code}:{word}:{part_of_speech}")


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
) -> CatalogLoadResult:
    if validate_first:
        validate_catalog_dataset(sets, raise_on_error=True)

    result = CatalogLoadResult()

    for set_index, set_seed in enumerate(sets):
        s_id = seed_set_id(set_seed.code)
        db_set = db.get(VocabularySet, s_id)
        if db_set is None:
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
            db.add(db_set)
            result.sets_created += 1
        else:
            db_set.name = set_seed.display_name
            db_set.description = set_seed.display_description
            db_set.level_code = set_seed.level_code
            db_set.topic = set_seed.topic
            db_set.order_index = set_index
            result.sets_updated += 1

        db.flush()

        for entry_index, entry_seed in enumerate(set_seed.entries):
            e_id = seed_entry_id(set_seed.code, entry_seed.word, entry_seed.part_of_speech)
            db_entry = db.get(VocabularyEntry, e_id)
            if db_entry is None:
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
                db.add(db_entry)
                result.entries_created += 1
            else:
                db_entry.ipa = entry_seed.ipa
                db_entry.meaning = entry_seed.meaning
                db_entry.translation = entry_seed.translation
                db_entry.example_sentences = entry_seed.example_sentences
                db_entry.order_index = entry_index
                result.entries_updated += 1

    db.commit()
    return result
