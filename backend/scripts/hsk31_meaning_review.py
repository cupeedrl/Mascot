"""Export and validate human review of HSK meaning candidates."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

VALID_STATUSES = {"pending", "approved", "resolved", "deferred", "rejected"}
BUCKET_ORDER = {"variant/reference": 0, "multiple pronunciation": 1, "multiple senses": 2, "other": 3}
FIELDS = ["word", "level_code", "pinyin", "part_of_speech", "candidate_meanings", "reference_or_variant_info", "reason", "suggested_target_if_any", "review_status", "final_english_meaning", "reviewer_note"]


def bucket(row: dict[str, Any]) -> str:
    reason = row.get("reason", "")
    if "variant_or_reference" in reason:
        return "variant/reference"
    if "multiple_pronunciations" in reason:
        return "multiple pronunciation"
    if "multiple_cedict_candidates" in reason:
        return "multiple senses"
    return "other"


def export_review(queue_path: Path, output_path: Path) -> dict[str, int]:
    rows = json.loads(queue_path.read_text(encoding="utf-8"))
    rows = sorted(rows, key=lambda r: (BUCKET_ORDER[bucket(r)], int(str(r.get("level_code", "HSK999")).replace("HSK", "")), r.get("word", "")))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        for row in rows:
            candidates = row.get("candidates", [])
            refs = [c.get("gloss", "") for c in candidates if "variant" in c.get("gloss", "").lower() or "see " in c.get("gloss", "").lower()]
            writer.writerow({
                "word": row.get("word", ""), "level_code": row.get("level_code", ""), "pinyin": row.get("pinyin") or "", "part_of_speech": row.get("part_of_speech") or "", "candidate_meanings": " | ".join(c.get("gloss", "") for c in candidates), "reference_or_variant_info": " | ".join(refs), "reason": row.get("reason", ""), "suggested_target_if_any": "", "review_status": "pending", "final_english_meaning": "", "reviewer_note": "",
            })
    counts: dict[str, int] = {}
    for row in rows:
        counts[bucket(row)] = counts.get(bucket(row), 0) + 1
    return counts


def validate_review(review_path: Path, canonical_path: Path, output_dir: Path) -> dict[str, Any]:
    canonical = {r["word"]: r for r in json.loads(canonical_path.read_text(encoding="utf-8"))}
    with review_path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    errors: list[dict[str, Any]] = []
    seen: set[str] = set()
    resolved, deferred = [], []
    for index, row in enumerate(rows, start=2):
        word, status = row.get("word", "").strip(), row.get("review_status", "").strip().lower()
        if word in seen:
            errors.append({"row": index, "error": "duplicate_word", "word": word})
        seen.add(word)
        source = canonical.get(word)
        if source is None:
            errors.append({"row": index, "error": "unknown_word", "word": word})
            continue
        if row.get("level_code", "").strip() != source.get("level_code"):
            errors.append({"row": index, "error": "level_changed", "word": word})
        if status not in VALID_STATUSES:
            errors.append({"row": index, "error": "invalid_status", "word": word})
        final = row.get("final_english_meaning", "").strip()
        if status in {"approved", "resolved"} and not final:
            errors.append({"row": index, "error": "final_meaning_required", "word": word})
        item = {"word": word, "level_code": source["level_code"], "normalized_english_meaning": final, "review_status": status, "reviewer_note": row.get("reviewer_note", "").strip()}
        if status in {"approved", "resolved"} and final:
            resolved.append(item)
        elif status == "deferred":
            deferred.append(item)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "reviewed_resolved.json").write_text(json.dumps(resolved, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output_dir / "reviewed_deferred.json").write_text(json.dumps(deferred, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = {"input_rows": len(rows), "resolved_count": len(resolved), "deferred_count": len(deferred), "error_count": len(errors), "errors": errors, "valid": not errors}
    (output_dir / "review_validation_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    export = sub.add_parser("export")
    export.add_argument("--queue", type=Path, default=Path("tmp/hsk31_meaning_audit/remaining_review_queue.json"))
    export.add_argument("--output", type=Path, default=Path("tmp/hsk31_meaning_audit/meaning_review.csv"))
    validate = sub.add_parser("validate")
    validate.add_argument("--review", type=Path, required=True)
    validate.add_argument("--canonical", type=Path, default=Path("tmp/hsk31_audit/canonical_words.json"))
    validate.add_argument("--output-dir", type=Path, default=Path("tmp/hsk31_meaning_audit/review_results"))
    args = parser.parse_args()
    if args.command == "export":
        print(json.dumps(export_review(args.queue, args.output), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(validate_review(args.review, args.canonical, args.output_dir), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
