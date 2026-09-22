"""Read-only CC-CEDICT sense selection audit for canonical HSK words."""
from __future__ import annotations

import argparse
import csv
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any


def norm(value: str) -> str:
    return unicodedata.normalize("NFKC", value).strip()


def pin_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", norm(value).casefold())


def load_ivankra(path: Path) -> dict[str, list[dict[str, str]]]:
    result: dict[str, list[dict[str, str]]] = defaultdict(list)
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            for word in norm(row.get("Simplified", "")).split("|"):
                if word:
                    result[word].append({k: (v or "").strip() for k, v in row.items()})
    return result


def load_cedict(path: Path) -> dict[str, list[dict[str, str]]]:
    result: dict[str, list[dict[str, str]]] = defaultdict(list)
    pattern = re.compile(r"^(\S+) (\S+) \[([^\]]+)\] /(.+)/$")
    for line in path.read_text(encoding="utf-8").splitlines():
        match = pattern.match(line)
        if match:
            result[norm(match.group(2))].append({"traditional": match.group(1), "pinyin": match.group(3), "gloss": match.group(4)})
    return result


def pointer_words(row: dict[str, str]) -> set[str]:
    pointer = row.get("CEDICT", "")
    return {norm(part.split("[", 1)[0]) for part in pointer.split("|") if part and "[" in part}


def resolve_references(gloss: str, cedict: dict[str, list[dict[str, str]]]) -> list[dict[str, str]]:
    refs = re.findall(r"(?:variant of|see)\s+([^;/]+)", gloss, re.I)
    resolved: list[dict[str, str]] = []
    for ref in refs:
        word = norm(ref.strip(" []"))
        for candidate in cedict.get(word, []):
            resolved.append({"word": word, "pinyin": candidate["pinyin"], "gloss": candidate["gloss"]})
    return resolved


def select_meaning(record: dict[str, Any], iv_rows: list[dict[str, str]], candidates: list[dict[str, str]], cedict: dict[str, list[dict[str, str]]]) -> dict[str, Any]:
    word, pinyin, pos = record["word"], record.get("ipa"), record.get("part_of_speech", "unknown")
    iv_pointer = set().union(*(pointer_words(row) for row in iv_rows)) if iv_rows else set()
    compatible = [c for c in candidates if pinyin and pin_key(c["pinyin"]) == pin_key(pinyin)]
    if not compatible and len(candidates) == 1:
        compatible = candidates
    pointer_pinyin = {pin_key(match) for row in iv_rows for match in re.findall(r"\[([^\]]+)\]", row.get("CEDICT", ""))}
    pointer_matches = [c for c in candidates if word in iv_pointer and pin_key(c["pinyin"]) in pointer_pinyin]
    if pointer_matches:
        compatible = pointer_matches
    variant = any(re.search(r"\b(?:variant of|erhua variant|see)\b", c["gloss"], re.I) for c in compatible or candidates)
    reasons: list[str] = []
    if len(candidates) > 1:
        reasons.append("multiple_cedict_candidates")
    if len({c["pinyin"] for c in candidates}) > 1:
        reasons.append("multiple_pronunciations")
    if variant:
        reasons.append("variant_or_reference_definition")
    if pos == "unknown":
        reasons.append("pos_unknown")
    chosen = compatible if compatible else candidates
    high = len(chosen) == 1 and not variant and bool(pinyin) and bool(candidates)
    if high:
        return {"normalized_english_meaning": chosen[0]["gloss"], "confidence": "high_confidence", "reason": "unique_exact_pinyin_match", "candidates": candidates, "resolved_candidates": []}
    if chosen:
        return {"normalized_english_meaning": None, "confidence": "needs_review", "reason": ";".join(reasons) or "multiple_or_insufficient_evidence", "candidates": candidates, "resolved_candidates": sum((resolve_references(c["gloss"], cedict) for c in chosen), [])}
    return {"normalized_english_meaning": None, "confidence": "unresolved", "reason": "missing_cedict_meaning", "candidates": [], "resolved_candidates": []}


def build_meaning_audit(canonical_path: Path, ivankra_path: Path, cedict_path: Path) -> dict[str, Any]:
    records = json.loads(canonical_path.read_text(encoding="utf-8"))
    ivankra, cedict = load_ivankra(ivankra_path), load_cedict(cedict_path)
    normalized, review, unresolved = [], [], []
    for record in sorted(records, key=lambda r: r["word"]):
        candidates = cedict.get(record["word"], [])
        selection = select_meaning(record, ivankra.get(record["word"], []), candidates, cedict)
        output = {"word": record["word"], "level_code": record["level_code"], "pinyin": record.get("ipa"), "part_of_speech": record.get("part_of_speech"), "current_english_meaning": record.get("meaning"), **selection}
        if selection["confidence"] == "high_confidence": normalized.append(output)
        elif selection["confidence"] == "needs_review": review.append(output)
        else: unresolved.append(output)
    counts = {"canonical_count": len(records), "high_confidence": len(normalized), "needs_review": len(review), "unresolved": len(unresolved), "meaning_coverage_percent": round(100 * len(normalized) / len(records), 2), "multiple_sense_words": sum("multiple_cedict_candidates" in r["reason"] for r in review), "multiple_pronunciation_words": sum("multiple_pronunciations" in r["reason"] for r in review), "variant_reference_definitions": sum("variant_or_reference_definition" in r["reason"] for r in review), "missing_meanings": len(unresolved), "ivankra_pointer_rows": sum(bool(pointer_words(row)) for rows in ivankra.values() for row in rows)}
    pilot_words = {r["word"] for r in records[:20]}
    pilot = [r for r in normalized + review + unresolved if r["word"] in pilot_words]
    return {"normalized_meanings": normalized, "meaning_review_queue": review, "meaning_unresolved": unresolved, "meaning_coverage_report": counts, "pilot20_meaning_review": pilot}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--canonical", type=Path, required=True)
    parser.add_argument("--ivankra", type=Path, required=True)
    parser.add_argument("--cedict", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("tmp/hsk31_meaning_audit"))
    args = parser.parse_args()
    audit = build_meaning_audit(args.canonical, args.ivankra, args.cedict)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, payload in audit.items():
        (args.output_dir / f"{name}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(audit["meaning_coverage_report"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
