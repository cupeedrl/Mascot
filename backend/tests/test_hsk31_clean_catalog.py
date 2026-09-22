import importlib.util
import json
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "prepare_hsk31_clean_catalog.py"
spec = importlib.util.spec_from_file_location("hsk31_clean_catalog", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(module)


def record(word, level="HSK1", pos="noun", meaning="a meaning"):
    return {"word": word, "level_code": level, "pinyin": "yi1", "part_of_speech": pos, "normalized_english_meaning": meaning}


def test_clean_pool_merges_only_records_with_normalized_meaning():
    clean = module.build_clean_records([record("甲")], [record("乙", "HSK2", "verb")])
    assert [r["word"] for r in clean] == ["甲", "乙"]
    assert all(r["meaning"] == r["normalized_english_meaning"] for r in clean)
    assert clean[0]["sources"]["word_level"] == "@leonsilicon/hsk3.1"


def test_missing_meaning_and_duplicates_are_not_silently_imported():
    clean = module.build_clean_records([record("甲"), {"word": "无义", "level_code": "HSK1", "normalized_english_meaning": ""}], [])
    assert [r["word"] for r in clean] == ["甲"]
    try:
        module.build_clean_records([record("甲")], [record("甲")])
        assert False
    except ValueError as exc:
        assert "duplicate" in str(exc)


def test_representative_pilot_is_deterministic_and_has_requested_size():
    records = []
    for level in range(1, 7):
        for index, pos in enumerate(("noun", "verb", "adjective", "adverb", "particle", "noun")):
            records.append(record(f"{level}-{index}", f"HSK{level}", pos, "idiom; related sense" if index == 5 else "meaning"))
    first = module.select_representative_pilot(records, 30)
    second = module.select_representative_pilot(records, 30)
    assert len(first) == 30
    assert [r["word"] for r in first] == [r["word"] for r in second]
    assert {r["level_code"] for r in first} == {f"HSK{i}" for i in range(1, 7)}


def test_build_artifacts_report_and_pilot(tmp_path):
    normalized = tmp_path / "normalized.json"
    newly = tmp_path / "newly.json"
    normalized.write_text(json.dumps([record(f"词{i}", f"HSK{(i % 6) + 1}") for i in range(30)]), encoding="utf-8")
    newly.write_text("[]", encoding="utf-8")
    report = module.build_artifacts(normalized, newly, tmp_path / "out", expected_count=30)
    assert report["total_count"] == 30
    assert len(json.loads((tmp_path / "out" / "clean_records.json").read_text(encoding="utf-8"))) == 30
    assert len(json.loads((tmp_path / "out" / "pilot_records.json").read_text(encoding="utf-8"))) == 30
