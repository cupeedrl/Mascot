from __future__ import annotations

import json
import pathlib
import unicodedata
from app.catalog.schema import CatalogEntrySeed, CatalogSetSeed
from app.catalog.validator import validate_catalog_dataset

DATA_DIR = pathlib.Path(__file__).parent.parent / "data"

def save_level_file(level_code: str, sets_data: list[dict[str, object]]) -> int:
    validated_sets: list[CatalogSetSeed] = []
    for s in sets_data:
        entries = [
            CatalogEntrySeed(
                word=e[0],
                part_of_speech=e[1],
                ipa=e[2],
                meaning=e[3],
                translation=e[4],
                example_sentences=[e[5]],
            )
            for e in s["entries"]
        ]
        validated_sets.append(
            CatalogSetSeed(
                code=s["code"],
                level_code=s["level_code"],
                topic=s["topic"],
                name=s.get("name", s["topic"]),
                description=s.get("description"),
                entries=entries,
            )
        )
    
    # Validate entire level dataset
    val_res = validate_catalog_dataset(validated_sets, raise_on_error=True)
    
    target_file = DATA_DIR / f"{level_code.lower()}.json"
    with open(target_file, "w", encoding="utf-8") as f:
        json.dump([s.model_dump() for s in validated_sets], f, ensure_ascii=False, indent=2)
    
    print(f"Saved {level_code}: {val_res.total_sets} sets, {val_res.total_entries} entries to {target_file.name}")
    return val_res.total_entries
