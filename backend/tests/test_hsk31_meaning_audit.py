import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "audit_hsk31_meanings.py"
spec = importlib.util.spec_from_file_location("meaning_audit", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(module)


def rec(word="一一", pinyin="yīyī", pos="adverb"):
    return {"word": word, "ipa": pinyin, "part_of_speech": pos, "meaning": "old"}


def test_pronunciation_filter_and_high_confidence():
    result = module.select_meaning(rec(), [], [{"pinyin": "yīyī", "gloss": "one by one"}], {})
    assert result["confidence"] == "high_confidence"
    assert result["normalized_english_meaning"] == "one by one"


def test_multiple_pronunciations_need_review():
    result = module.select_meaning(rec(), [], [{"pinyin": "yīyī", "gloss": "one by one"}, {"pinyin": "yíyí", "gloss": "different"}], {})
    assert result["confidence"] == "needs_review"
    assert "multiple_pronunciations" in result["reason"]


def test_variant_reference_is_resolved_without_guessing():
    cedict = {"一块": [{"pinyin": "yī kuài", "gloss": "a piece"}]}
    result = module.select_meaning(rec("一块儿", "yīkuàir"), [{"CEDICT": "一块儿|一块儿[yī kuài r5]"}], [{"pinyin": "yī kuài r5", "gloss": "erhua variant of 一块"}], cedict)
    assert result["confidence"] == "needs_review"
    assert result["resolved_candidates"][0]["word"] == "一块"


def test_missing_candidate_is_unresolved_and_script_is_read_only():
    result = module.select_meaning(rec("不存在"), [], [], {})
    assert result["confidence"] == "unresolved"
    source = SCRIPT.read_text(encoding="utf-8").lower()
    assert "sqlalchemy" not in source and "app.catalog.data" not in source
