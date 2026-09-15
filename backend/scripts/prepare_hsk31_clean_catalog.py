"""Build a read-only clean HSK31 translation input and representative pilot."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _level_number(record: dict[str, Any]) -> int:
    return int(str(record.get("level_code", "HSK999")).replace("HSK", ""))


def _is_function_word(record: dict[str, Any]) -> bool:
    pos = str(record.get("part_of_speech", "")).lower()
    return any(token in pos for token in ("particle", "measure", "classifier", "pronoun", "preposition", "conjunction", "adverbial"))


def _is_idiom_or_multi_sense(record: dict[str, Any]) -> bool:
    meaning = str(record.get("normalized_english_meaning", ""))
    return any(token in meaning.lower() for token in ("idiom", "chengyu")) or meaning.count(";") >= 2


def build_clean_records(normalized: list[dict[str, Any]], newly_resolved: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for source_name, records in (("meaning_audit", normalized), ("deterministic_resolution", newly_resolved)):
        for source in records:
            word = str(source.get("word", "")).strip()
            meaning = str(source.get("normalized_english_meaning", "")).strip()
            if not word or not source.get("level_code") or not meaning:
                continue
            if word in merged:
                raise ValueError(f"duplicate clean word across sources: {word}")
            record = {
                "word": word,
                "level_code": source["level_code"],
                "pinyin": source.get("pinyin") or source.get("ipa"),
                "part_of_speech": source.get("part_of_speech") or "unknown",
                "normalized_english_meaning": meaning,
                # The existing translation pipeline consumes `meaning`.
                "meaning": meaning,
                "sources": {
                    "word_level": "@leonsilicon/hsk3.1",
                    "pinyin_pos": "ivankra/hsk30 / meaning audit" if source_name == "meaning_audit" else "meaning audit resolution",
                    "english_meaning": "CC-CEDICT via Mascot meaning audit",
                },
            }
            merged[word] = record
    return sorted(merged.values(), key=lambda r: (_level_number(r), r["word"]))


def select_representative_pilot(records: list[dict[str, Any]], count: int = 30) -> list[dict[str, Any]]:
    ordered = sorted(records, key=lambda r: (_level_number(r), r["word"]))
    predicates = [
        lambda r: "noun" in str(r.get("part_of_speech", "")).lower(),
        lambda r: "verb" in str(r.get("part_of_speech", "")).lower(),
        lambda r: "adjective" in str(r.get("part_of_speech", "")).lower(),
        lambda r: "adverb" in str(r.get("part_of_speech", "")).lower(),
        _is_function_word,
        _is_idiom_or_multi_sense,
    ]
    selected: list[dict[str, Any]] = []
    used: set[str] = set()
    for predicate in predicates:
        candidates = [r for r in ordered if r["word"] not in used and predicate(r)]
        # Cycle through levels first so the pilot is not concentrated in HSK1.
        for level in range(1, 7):
            for record in candidates:
                if _level_number(record) == level:
                    selected.append(record)
                    used.add(record["word"])
                    break
            if len(selected) >= count:
                return selected[:count]
        for record in candidates:
            if len(selected) >= count:
                break
            if record["word"] not in used:
                selected.append(record)
                used.add(record["word"])
    if len(selected) < count:
        for record in ordered:
            if record["word"] not in used:
                selected.append(record)
                used.add(record["word"])
                if len(selected) == count:
                    break
    if len(selected) < count:
        raise ValueError(f"only {len(selected)} representative records available")
    return selected[:count]


def build_artifacts(normalized_path: Path, newly_path: Path, output_dir: Path, expected_count: int = 4876) -> dict[str, Any]:
    records = build_clean_records(load_json(normalized_path), load_json(newly_path))
    if len(records) != expected_count:
        raise ValueError(f"expected {expected_count} clean records, got {len(records)}")
    output_dir.mkdir(parents=True, exist_ok=True)
    pilot = select_representative_pilot(records)
    (output_dir / "clean_records.json").write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output_dir / "pilot_records.json").write_text(json.dumps(pilot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = {
        "total_count": len(records),
        "per_level_count": dict(sorted(Counter(r["level_code"] for r in records).items())),
        "missing_pinyin_count": sum(not r.get("pinyin") for r in records),
        "pos_unknown_count": sum(str(r.get("part_of_speech", "")).lower() == "unknown" for r in records),
        "pilot_count": len(pilot),
    }
    (output_dir / "clean_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--normalized", type=Path, default=Path("tmp/hsk31_meaning_audit/normalized_meanings.json"))
    parser.add_argument("--newly-resolved", type=Path, default=Path("tmp/hsk31_meaning_audit/newly_resolved.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("tmp/hsk31_clean_catalog"))
    args = parser.parse_args()
    print(json.dumps(build_artifacts(args.normalized, args.newly_resolved, args.output_dir), ensure_ascii=False))


if __name__ == "__main__":
    main()
