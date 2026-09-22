from __future__ import annotations

import csv
import json
from pathlib import Path

from scripts.audit_hsk31_enrichment import build_audit


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    hsk = tmp_path / "hsk"
    hsk.mkdir()
    for level in range(1, 7):
        words = ["学习"] if level == 1 else (["重复"] if level == 2 else [])
        if level == 3:
            words = ["重复", "仅中"]
        if level == 4:
            words = ["多义"]
        if level == 5:
            words = ["有时（候）"]
        (hsk / f"HSK3.1_words_level{level}.json").write_text(json.dumps(words, ensure_ascii=False), encoding="utf-8")
    iv = tmp_path / "iv.csv"
    with iv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["Simplified", "Pinyin", "POS"])
        writer.writeheader()
        writer.writerow({"Simplified": "学习", "Pinyin": "xuéxí", "POS": "V"})
        writer.writerow({"Simplified": "重复", "Pinyin": "chóngfù", "POS": "V"})
    ce = tmp_path / "cedict.u8"
    ce.write_text("重复 重复 [chong2 fu4] /to repeat/\n仅中 仅中 [jin3 zhong1] /only middle/\n多义 多义 [duo1 yi4] /sense one/\n多义 多义 [duo1 yi4] /sense two/\n", encoding="utf-8")
    return hsk, iv, ce


def test_canonical_earliest_level_and_exact_dedup(tmp_path: Path) -> None:
    audit = build_audit(*_fixture(tmp_path))
    records = {row["word"]: row for row in audit["canonical_words"]}
    assert records["重复"]["level_code"] == "HSK2"
    assert len(records) == 5
    assert audit["duplicate_levels"] == [{"word": "重复", "source_levels": ["HSK2", "HSK3"], "canonical_level": "HSK2"}]


def test_ivankra_precedence_and_cedict_fallback(tmp_path: Path) -> None:
    audit = build_audit(*_fixture(tmp_path))
    records = {row["word"]: row for row in audit["canonical_words"]}
    assert records["学习"]["ipa"] == "xuéxí"
    assert records["仅中"]["ipa"] == "jin3 zhong1"
    assert records["仅中"]["part_of_speech"] == "unknown"


def test_outputs_are_read_only_intermediate_and_ambiguous_is_reported(tmp_path: Path) -> None:
    audit = build_audit(*_fixture(tmp_path))
    study = next(row for row in audit["canonical_words"] if row["word"] == "学习")
    assert study["translation"] is None
    assert study["example_sentences"] == []
    assert study["topic"] == "General"
    assert audit["ambiguous_cedict"][0]["word"] == "多义"


def test_source_forms_are_queued_for_explicit_normalization_review(tmp_path: Path) -> None:
    audit = build_audit(*_fixture(tmp_path))
    review = next(row for row in audit["normalization_review"] if row["source_word"] == "有时(候)")
    assert {candidate["word"] for candidate in review["possible_candidates"]} == {"有时候", "有时"}


def test_adapter_is_read_only_and_does_not_reference_production_catalog_or_db() -> None:
    script = Path(__file__).parents[1] / "scripts" / "audit_hsk31_enrichment.py"
    text = script.read_text(encoding="utf-8")
    assert "sqlalchemy" not in text
    assert "app.catalog.data" not in text
