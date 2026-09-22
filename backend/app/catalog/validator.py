from __future__ import annotations

import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass, field

from app.catalog.schema import CatalogEntrySeed, CatalogSetSeed
from app.services.normalization import normalize_word


class CatalogValidationError(Exception):
    def __init__(self, errors: list[str]) -> None:
        super().__init__(f"Catalog validation failed with {len(errors)} error(s):\n" + "\n".join(f"- {e}" for e in errors))
        self.errors = errors


@dataclass
class CatalogValidationResult:
    is_valid: bool
    total_sets: int = 0
    total_entries: int = 0
    sets_by_level: dict[str, int] = field(default_factory=dict)
    entries_by_level: dict[str, int] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


def _sense_key(entry: CatalogEntrySeed) -> tuple[str, str, str]:
    norm_w = normalize_word(entry.word)
    norm_trans = unicodedata.normalize("NFKC", entry.translation.strip()).casefold()
    return (norm_w, entry.part_of_speech, norm_trans)


def validate_catalog_dataset(
    sets: Iterable[CatalogSetSeed],
    *,
    raise_on_error: bool = False,
) -> CatalogValidationResult:
    result = CatalogValidationResult(is_valid=True)
    seen_set_codes: set[str] = set()
    seen_set_topics_by_level: set[tuple[str, str]] = set()
    seen_senses: dict[tuple[str, str, str], str] = {}  # key -> set_code:word

    for set_seed in sets:
        result.total_sets += 1
        lvl = set_seed.level_code
        result.sets_by_level[lvl] = result.sets_by_level.get(lvl, 0) + 1

        # Check set code uniqueness
        if set_seed.code in seen_set_codes:
            result.errors.append(f"Duplicate set code: '{set_seed.code}'.")
        seen_set_codes.add(set_seed.code)

        # Check (level, topic) uniqueness
        level_topic = (lvl, set_seed.topic.lower())
        if level_topic in seen_set_topics_by_level:
            result.errors.append(
                f"Duplicate set topic '{set_seed.topic}' in level '{lvl}'."
            )
        seen_set_topics_by_level.add(level_topic)

        # Validate entries in this set
        for idx, entry in enumerate(set_seed.entries):
            result.total_entries += 1
            result.entries_by_level[lvl] = result.entries_by_level.get(lvl, 0) + 1

            s_key = _sense_key(entry)
            if s_key in seen_senses:
                prev_loc = seen_senses[s_key]
                result.errors.append(
                    f"Duplicate entry sense '{entry.word}' ({entry.part_of_speech}, '{entry.translation}') "
                    f"in set '{set_seed.code}' (previously seen in '{prev_loc}')."
                )
            else:
                seen_senses[s_key] = f"{set_seed.code}:{entry.word}"

    if result.errors:
        result.is_valid = False
        if raise_on_error:
            raise CatalogValidationError(result.errors)

    return result
