"""Deterministically reduce the HSK meaning review queue; no model or DB calls."""
from __future__ import annotations

import argparse
import csv
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any


def pinyin_key(value: str) -> str:
    value = unicodedata.normalize("NFD", value.casefold())
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    # Numbered/diacritic pinyin, including erhua tone 5, compare by syllable text.
    return re.sub(r"[^a-z]", "", value)


def is_reference(gloss: str) -> bool:
    return bool(re.search(r"\b(?:variant of|erhua variant|see|also written|used in)\b", gloss, re.I))


def reason_bucket(reason: str) -> str:
    if "variant_or_reference" in reason:
        return "variant/reference only"
    if "multiple_pronunciations" in reason:
        return "multiple pronunciation"
    if "multiple_cedict_candidates" in reason:
        return "multiple compatible dictionary senses"
    if "pos" in reason:
        return "POS mismatch/unknown"
    if "missing" in reason:
        return "missing meaning"
    return "other"


def resolve_record(record: dict[str, Any]) -> dict[str, Any]:
    candidates = record.get("candidates", [])
    pinyin = record.get("pinyin") or ""
    compatible = [c for c in candidates if pinyin and pinyin_key(c.get("pinyin", "")) == pinyin_key(pinyin)]
    reasons = []
    if len(candidates) > 1:
        reasons.append("multiple_cedict_candidates")
    if len({c.get("pinyin") for c in candidates}) > 1:
        reasons.append("multiple_pronunciations")
    usable = compatible if compatible else []
    reference = any(is_reference(c.get("gloss", "")) for c in candidates)
    if reference:
        reasons.append("variant_or_reference_definition")
    if record.get("part_of_speech") == "unknown":
        reasons.append("pos_unknown")
    # Only a unique exact pronunciation candidate can be promoted automatically.
    safe = len(usable) == 1 and not reference and not re.search(r"\b(?:surname|used in)\b", usable[0].get("gloss", ""), re.I)
    if safe:
        return {**record, "normalized_english_meaning": usable[0]["gloss"], "confidence": "high_confidence", "resolution_reason": "unique_exact_pinyin_candidate", "evidence": {"pinyin_match": True, "exact_word": True, "candidate_count": len(candidates)}}
    if not candidates:
        return {**record, "confidence": "unresolved", "resolution_reason": "missing_cedict_meaning", "evidence": {"exact_word": True, "candidate_count": 0}}
    return {**record, "confidence": "needs_review", "resolution_reason": ";".join(reasons) or "insufficient_evidence", "evidence": {"pinyin_match": len(compatible) == 1, "exact_word": True, "candidate_count": len(candidates)}}


def run(queue_path: Path, output_dir: Path) -> dict[str, Any]:
    queue = json.loads(queue_path.read_text(encoding="utf-8"))
    results = [resolve_record(record) for record in sorted(queue, key=lambda r: r["word"])]
    newly = [r for r in results if r["confidence"] == "high_confidence"]
    remaining = [r for r in results if r["confidence"] == "needs_review"]
    unresolved = [r for r in results if r["confidence"] == "unresolved"]
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "newly_resolved.json").write_text(json.dumps(newly, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output_dir / "remaining_review_queue.json").write_text(json.dumps(remaining, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output_dir / "meaning_unresolved.json").write_text(json.dumps(unresolved, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output_dir / "resolution_audit.json").write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with (output_dir / "remaining_review_queue.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["word", "level_code", "pinyin", "part_of_speech", "current_english_meaning", "reason", "candidate_meanings"])
        writer.writeheader()
        for row in remaining:
            writer.writerow({"word": row["word"], "level_code": row["level_code"], "pinyin": row.get("pinyin"), "part_of_speech": row.get("part_of_speech"), "current_english_meaning": row.get("current_english_meaning"), "reason": row.get("reason"), "candidate_meanings": " | ".join(c.get("gloss", "") for c in row.get("candidates", []))})
    report = {"original_review_count": len(queue), "newly_resolved": len(newly), "remaining_review": len(remaining), "unresolved": len(unresolved), "reason_buckets": dict(Counter(reason_bucket(r.get("reason", "")) for r in queue)), "original_high_confidence_unchanged": True}
    (output_dir / "updated_coverage_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", type=Path, default=Path("tmp/hsk31_meaning_audit/meaning_review_queue.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("tmp/hsk31_meaning_audit"))
    args = parser.parse_args()
    print(json.dumps(run(args.queue, args.output_dir), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
