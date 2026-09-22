"""Build a read-only HSK 3.1 enrichment audit.

The command only reads the three source datasets and writes JSON QA artifacts. It
does not import catalog data or open a database connection.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

POS_MAP = {
    "N": "noun", "V": "verb", "Adj": "adjective", "Adv": "adverb",
    "Pron": "pronoun", "Prep": "preposition", "Conj": "conjunction",
    "Aux": "other", "Int": "interjection", "M": "other", "Num": "other",
    "Prefix": "other", "Suffix": "other", "Phonetic": "other",
}
SOURCE_FORMS = ("凡(是)", "差(一)点儿", "有(一)点儿", "有时(候)", "没(有)", "要不(然)")


def _norm(value: str) -> str:
    return unicodedata.normalize("NFKC", value).strip()


def _pinyin_key(value: str) -> str:
    value = unicodedata.normalize("NFD", value.casefold())
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]", "", value)


def _load_hsk_words(hsk_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for level in range(1, 7):
        path = hsk_dir / f"HSK3.1_words_level{level}.json"
        words = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(words, list) or not all(isinstance(word, str) for word in words):
            raise ValueError(f"Expected a string array in {path}")
        rows.extend({"word": _norm(word), "source_level": level, "source_index": index}
                    for index, word in enumerate(words))
    return rows


def _load_ivankra(path: Path) -> dict[str, list[dict[str, str]]]:
    result: dict[str, list[dict[str, str]]] = defaultdict(list)
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            word = _norm(row.get("Simplified", ""))
            if word:
                result[word].append({key: (value or "").strip() for key, value in row.items()})
    return result


def _load_cedict(path: Path) -> dict[str, list[dict[str, str]]]:
    result: dict[str, list[dict[str, str]]] = defaultdict(list)
    pattern = re.compile(r"^(\S+) (\S+) \[([^\]]+)\] /(.+)/$")
    for line in path.read_text(encoding="utf-8").splitlines():
        match = pattern.match(line)
        if match:
            result[_norm(match.group(2))].append({
                "traditional": match.group(1), "pinyin": match.group(3), "gloss": match.group(4),
            })
    return result


def _canonical_rows(raw_rows: Iterable[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in raw_rows:
        grouped[row["word"]].append(row)
    canonical: list[dict[str, Any]] = []
    level_duplicates: list[dict[str, Any]] = []
    same_level_duplicates: list[dict[str, Any]] = []
    for word in sorted(grouped):
        occurrences = grouped[word]
        levels = sorted({row["source_level"] for row in occurrences})
        canonical_level = levels[0]
        canonical.append({"word": word, "level_code": f"HSK{canonical_level}", "source_level": canonical_level})
        if len(levels) > 1:
            level_duplicates.append({"word": word, "source_levels": [f"HSK{level}" for level in levels], "canonical_level": f"HSK{canonical_level}"})
        for level in levels:
            count = sum(row["source_level"] == level for row in occurrences)
            if count > 1:
                same_level_duplicates.append({"word": word, "source_level": f"HSK{level}", "occurrences": count})
    return canonical, level_duplicates, same_level_duplicates


def _possible_source_forms(word: str) -> list[str]:
    match = re.fullmatch(r"(.*?)[（(]([^（）()]+)[）)](.*)", word)
    if not match:
        return []
    prefix, optional, suffix = match.groups()
    return [_norm(prefix + optional + suffix), _norm(prefix + suffix)]


def build_audit(hsk_dir: Path, ivankra_csv: Path, cedict_file: Path) -> dict[str, Any]:
    raw = _load_hsk_words(hsk_dir)
    canonical, level_duplicates, same_level_duplicates = _canonical_rows(raw)
    ivankra = _load_ivankra(ivankra_csv)
    cedict = _load_cedict(cedict_file)
    records: list[dict[str, Any]] = []
    ambiguous: list[dict[str, Any]] = []
    missing_pinyin: list[dict[str, Any]] = []
    missing_meaning: list[dict[str, Any]] = []
    normalization_review: list[dict[str, Any]] = []
    counts = {f"HSK{level}": {"canonical": 0, "ivankra_pinyin": 0, "cedict_pinyin": 0, "pinyin": 0, "pos": 0, "unknown_pos": 0, "meaning": 0} for level in range(1, 7)}

    for item in canonical:
        word = item["word"]
        iv_matches = ivankra.get(word, [])
        ce_matches = cedict.get(word, [])
        iv_pinyin = next((row.get("Pinyin", "") for row in iv_matches if row.get("Pinyin")), "")
        cedict_pinyin = next((row.get("pinyin", "") for row in ce_matches if row.get("pinyin")), "")
        preferred_pinyin = iv_pinyin or cedict_pinyin
        matching_ce = [row for row in ce_matches if _pinyin_key(row["pinyin"]) == _pinyin_key(iv_pinyin)] if iv_pinyin else ce_matches
        selected_ce = matching_ce[0] if len(matching_ce) == 1 else (ce_matches[0] if len(ce_matches) == 1 else None)
        is_ambiguous = len(ce_matches) > 1 and selected_ce is None
        meaning = selected_ce["gloss"] if selected_ce else None
        pos_code = next((row.get("POS", "") for row in iv_matches if row.get("POS")), "")
        pos = POS_MAP.get(pos_code.split("/")[0], "unknown") if pos_code else "unknown"
        level_counts = counts[item["level_code"]]
        level_counts["canonical"] += 1
        if iv_pinyin: level_counts["ivankra_pinyin"] += 1
        elif cedict_pinyin: level_counts["cedict_pinyin"] += 1
        if preferred_pinyin: level_counts["pinyin"] += 1
        if pos != "unknown": level_counts["pos"] += 1
        else: level_counts["unknown_pos"] += 1
        if meaning: level_counts["meaning"] += 1
        record = {
            "word": word, "level_code": item["level_code"], "ipa": preferred_pinyin or None,
            "meaning": meaning, "translation": None, "part_of_speech": pos,
            "example_sentences": [], "topic": "General",
            "sources": {"level": "@leonsilicon/hsk3.1", "pinyin": "ivankra/hsk30" if iv_pinyin else ("CC-CEDICT" if cedict_pinyin else None), "meaning": "CC-CEDICT" if meaning else None},
            "qa": {"ambiguous": is_ambiguous, "missing_pinyin": not bool(preferred_pinyin), "missing_meaning": not bool(meaning)},
        }
        records.append(record)
        if is_ambiguous:
            ambiguous.append({"word": word, "candidate_pinyin": [row["pinyin"] for row in ce_matches], "candidate_glosses": [row["gloss"] for row in ce_matches], "match_count": len(ce_matches)})
        if not preferred_pinyin: missing_pinyin.append({"word": word, "level_code": item["level_code"]})
        if not meaning: missing_meaning.append({"word": word, "level_code": item["level_code"]})
        candidates = _possible_source_forms(word)
        if word in SOURCE_FORMS or candidates:
            normalization_review.append({"source_word": word, "possible_candidates": [{"word": candidate, "in_cc_cedict": candidate in cedict, "in_ivankra": candidate in ivankra} for candidate in candidates]})

    report = {"raw_hsk31_rows": len(raw), "canonical_unique_rows": len(canonical), "per_level": counts, "pinyin_from_ivankra": sum(v["ivankra_pinyin"] for v in counts.values()), "pinyin_from_cedict_fallback": sum(v["cedict_pinyin"] for v in counts.values()), "pinyin_total": sum(v["pinyin"] for v in counts.values()), "pos_from_ivankra": sum(v["pos"] for v in counts.values()), "pos_unknown_fallback": sum(v["unknown_pos"] for v in counts.values()), "meaning_coverage": sum(v["meaning"] for v in counts.values()), "ambiguous_rows": len(ambiguous), "normalization_review_rows": len(normalization_review), "missing_pinyin": len(missing_pinyin), "missing_meaning": len(missing_meaning)}
    return {"canonical_words": records, "duplicate_levels": level_duplicates, "same_level_duplicates": same_level_duplicates, "missing_pinyin": missing_pinyin, "missing_meaning": missing_meaning, "ambiguous_cedict": ambiguous, "normalization_review": normalization_review, "coverage_report": report}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hsk31-dir", type=Path, required=True)
    parser.add_argument("--ivankra-csv", type=Path, required=True)
    parser.add_argument("--cedict-file", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("backend/tmp/hsk31_audit"))
    args = parser.parse_args()
    audit = build_audit(args.hsk31_dir, args.ivankra_csv, args.cedict_file)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, payload in audit.items():
        (args.output_dir / f"{name}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(audit["coverage_report"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
