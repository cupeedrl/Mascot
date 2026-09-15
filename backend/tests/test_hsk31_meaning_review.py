import csv
import json
from pathlib import Path

import pytest

from scripts.hsk31_meaning_review import export_review, validate_review


def row(word, level="HSK1", reason="variant_or_reference_definition", status="pending", final=""):
    return {"word": word, "level_code": level, "pinyin": "yi1", "part_of_speech": "noun", "reason": reason, "candidates": [{"gloss": "variant of x"}], "review_status": status, "final_english_meaning": final, "reviewer_note": ""}


def test_export_includes_all_rows_and_sorts_buckets(tmp_path):
    queue = tmp_path / "queue.json"
    queue.write_text(json.dumps([row("乙", "HSK2", "multiple_cedict_candidates"), row("甲")]), encoding="utf-8")
    output = tmp_path / "review.csv"
    counts = export_review(queue, output)
    with output.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 2 and rows[0]["word"] == "甲"
    assert counts["variant/reference"] == 1


def test_validation_rejects_level_change_duplicate_and_missing_meaning(tmp_path):
    canonical = tmp_path / "canonical.json"
    canonical.write_text(json.dumps([{"word": "甲", "level_code": "HSK1"}]), encoding="utf-8")
    review = tmp_path / "review.csv"
    with review.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["word", "level_code", "review_status", "final_english_meaning"])
        writer.writeheader()
        writer.writerow({"word": "甲", "level_code": "HSK2", "review_status": "resolved", "final_english_meaning": ""})
        writer.writerow({"word": "甲", "level_code": "HSK1", "review_status": "bad", "final_english_meaning": ""})
    report = validate_review(review, canonical, tmp_path / "out")
    assert report["valid"] is False
    assert {e["error"] for e in report["errors"]} >= {"level_changed", "duplicate_word", "final_meaning_required", "invalid_status"}


def test_valid_resolved_and_deferred_outputs_without_db_or_catalog_writes(tmp_path):
    canonical = tmp_path / "canonical.json"
    canonical.write_text(json.dumps([{"word": "甲", "level_code": "HSK1"}, {"word": "乙", "level_code": "HSK2"}]), encoding="utf-8")
    review = tmp_path / "review.csv"
    with review.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["word", "level_code", "review_status", "final_english_meaning", "reviewer_note"])
        writer.writeheader()
        writer.writerow({"word": "甲", "level_code": "HSK1", "review_status": "resolved", "final_english_meaning": "one", "reviewer_note": "ok"})
        writer.writerow({"word": "乙", "level_code": "HSK2", "review_status": "deferred", "final_english_meaning": "", "reviewer_note": "review later"})
    report = validate_review(review, canonical, tmp_path / "out")
    assert report["valid"] and report["resolved_count"] == 1 and report["deferred_count"] == 1
    source = (Path(__file__).parents[1] / "scripts/hsk31_meaning_review.py").read_text(encoding="utf-8").lower()
    assert "sqlalchemy" not in source and "app.catalog.data" not in source
