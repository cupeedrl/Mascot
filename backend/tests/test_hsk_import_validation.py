"""Database-free tests for the HSK release validator (synthetic data only)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.catalog import hsk_import
from app.catalog.hsk_import import DatasetError, load_dataset, parse_level_name, validate_dataset
from tests.hsk_fixtures import PERMISSIONS_FIXTURE, build_dataset


def _validate(tmp_path: Path, **kwargs):
    return validate_dataset(load_dataset(build_dataset(tmp_path / "ds", **kwargs)))


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("一级", ["HSK1"]),
        ("六级", ["HSK6"]),
        ("七-九级", ["HSK7-9"]),
        ("一级（三级）", ["HSK1", "HSK3"]),
        ("一级（二级）（四级）", ["HSK1", "HSK2", "HSK4"]),
        ("三级（四级）（七-九级）", ["HSK3", "HSK4", "HSK7-9"]),
    ],
)
def test_parse_level_name(name: str, expected: list[str]) -> None:
    assert parse_level_name(name) == expected


@pytest.mark.parametrize("name", ["", "十级", "一级（十级）", "一级 extra", "一级（一级）"])
def test_parse_level_name_rejects(name: str) -> None:
    with pytest.raises(ValueError):
        parse_level_name(name)


def test_counts_by_level_are_actual(tmp_path: Path) -> None:
    result = _validate(tmp_path)
    report = hsk_import.finalize_report(result)
    assert report["records_in_file"] == 16
    assert report["excluded_out_of_scope_by_primary_level"] == {"HSK7-9": 1}
    assert [gap["serial"] for gap in report["serial_gaps"]] == [6]
    levels = report["per_level"]
    assert levels["HSK1"]["source_rows"] == 3
    assert levels["HSK1"]["accepted"] == 2
    assert levels["HSK1"]["duplicate"] == 1
    assert levels["HSK1"]["mapped"] == 2
    assert levels["HSK2"]["rejected"] == 1  # blank word
    assert levels["HSK2"]["flag:multiple_readings"] == 1
    assert levels["HSK2"]["flag:homograph_suffix"] == 1
    assert levels["HSK3"]["missing_pos"] == 1  # cixing key absent
    assert levels["HSK3"]["missing_serial_within_level"] == 1
    assert levels["HSK5"]["awaiting_review"] == 1
    assert levels["HSK6"]["ambiguous"] == 1  # 谁 shéi/shuí, no human mapping
    assert levels["HSK6"]["missing_pos"] == 1  # cixing blank
    assert sum(level.get("publicly_eligible", 0) for level in levels.values()) == 10
    assert report["issue_counts"]["rejected:unknown_level"] == 1
    assert report["issue_counts"]["review_duplicate:duplicate_mapping"] == 1
    assert report["review"]["topics_accepted"] == 7
    assert report["review"]["entry_topics_accepted"] == 3
    assert levels["HSK1"]["with_topic"] == 2
    assert levels["HSK2"]["with_topic"] == 1
    for reason in (
        "review_rejected:topic_parent_missing",
        "review_rejected:topic_level_out_of_scope",
        "review_rejected:entry_topic_unknown_topic",
        "review_rejected:entry_topic_not_primary_level",
        "review_duplicate:duplicate_entry_topic",
    ):
        assert report["issue_counts"][reason] == 1, reason


def test_api_id_and_serial_are_kept_independent(tmp_path: Path) -> None:
    result = _validate(tmp_path)
    row = next(r for r in result.rows if r.record_id == "101")
    assert row.serial == 1  # never derived from id "101"


def test_missing_pos_is_not_fabricated(tmp_path: Path) -> None:
    result = _validate(tmp_path)
    rows = {r.record_id: r for r in result.rows}
    assert rows["106"].raw_pos is None and "pos_absent" in rows["106"].flags
    assert rows["110"].raw_pos is None and "pos_blank" in rows["110"].flags


def test_review_problems_are_rejected_not_guessed(tmp_path: Path) -> None:
    result = _validate(tmp_path)
    reasons = {(i.kind, i.reason) for i in result.issues}
    assert ("review_rejected", "sense_pronunciation_not_in_lexical_entry") in reasons
    assert ("review_rejected", "sense_invalid_pos") in reasons
    assert ("review_rejected", "mapping_pronunciation_not_in_lexical_entry") in reasons
    assert ("review_rejected", "mapping_unknown_or_unaccepted_source") in reasons
    assert ("review_rejected", "mapping_sense_pronunciation_not_linked") in reasons
    keys = {item["lexical_key"] for item in result.lexical_entries}
    assert "zh:坏" not in keys and "zh:好" not in keys


def test_source_hash_mismatch_is_fatal(tmp_path: Path) -> None:
    directory = build_dataset(tmp_path / "ds")
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    manifest["source_sha256"] = "0" * 64
    (directory / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(DatasetError, match="SHA-256 mismatch"):
        load_dataset(directory)


def test_approved_permission_needs_evidence(tmp_path: Path) -> None:
    permissions = {k: dict(v) for k, v in PERMISSIONS_FIXTURE.items()}
    permissions["redistribution"] = {"status": "approved"}
    with pytest.raises(DatasetError, match="without evidence"):
        load_dataset(build_dataset(tmp_path / "ds", permissions=permissions))


def test_third_party_without_permission_is_not_publicly_eligible(tmp_path: Path) -> None:
    permissions = {k: {"status": "unknown"} for k in PERMISSIONS_FIXTURE}
    result = _validate(tmp_path, data_origin="third_party", permissions=permissions)
    report = hsk_import.finalize_report(result)
    assert report["publication_permission_gate_open"] is False
    assert all(not level.get("publicly_eligible") for level in report["per_level"].values())
