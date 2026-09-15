import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "resolve_hsk31_meanings.py"
spec = importlib.util.spec_from_file_location("meaning_resolution", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(module)


def item(word="甲", pinyin="jia3", gloss="a meaning"):
    return {"word": word, "level_code": "HSK1", "pinyin": pinyin, "part_of_speech": "noun", "current_english_meaning": None, "reason": "multiple_cedict_candidates", "candidates": [{"pinyin": pinyin, "gloss": gloss}]}


def test_exact_pinyin_candidate_resolves():
    result = module.resolve_record(item())
    assert result["confidence"] == "high_confidence"
    assert result["evidence"]["pinyin_match"] is True


def test_ambiguous_reference_stays_review():
    result = module.resolve_record(item(word="一块儿", pinyin="yi1 kuai4 r5", gloss="erhua variant of 一块"))
    assert result["confidence"] == "needs_review"


def test_multiple_compatible_senses_stay_review():
    row = item()
    row["candidates"] = [{"pinyin": "jia3", "gloss": "sense one"}, {"pinyin": "jia3", "gloss": "sense two"}]
    result = module.resolve_record(row)
    assert result["confidence"] == "needs_review"


def test_missing_candidate_is_unresolved_and_read_only():
    row = item()
    row["candidates"] = []
    assert module.resolve_record(row)["confidence"] == "unresolved"
    source = SCRIPT.read_text(encoding="utf-8").lower()
    assert "sqlalchemy" not in source and "app.catalog.data" not in source
