import csv
import importlib.util
import json
import inspect
import sys
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "ai_hsk31_meaning_review.py"
spec = importlib.util.spec_from_file_location("ai_meaning_review", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(module)


def row(word, level="HSK1", reason="variant_or_reference_definition"):
    return {"word": word, "level_code": level, "pinyin": "yi1", "part_of_speech": "noun", "candidate_meanings": "variant of x", "reference_or_variant_info": "variant of x", "reason": reason}


def test_representative_pilot_selection():
    rows = [row(f"甲{i}", "HSK1") for i in range(15)] + [row(f"乙{i}", "HSK2", "multiple_pronunciations") for i in range(10)] + [row(f"丙{i}", "HSK3", "multiple_cedict_candidates") for i in range(5)]
    selected = module.select_pilot(rows)
    assert len(selected) == 30
    assert [module.bucket(r) for r in selected].count("variant/reference") == 15
    assert [module.bucket(r) for r in selected].count("multiple pronunciation") == 10
    assert [module.bucket(r) for r in selected].count("multiple senses") == 5


def test_schema_validation_and_low_confidence_empty_allowed():
    rows = [row("甲"), row("乙", reason="multiple_pronunciations")]
    result = module.validate_suggestions(rows, {"suggestions": [{"word": "甲", "suggested_english_meaning": "", "confidence": "low", "review_note": "unclear"}, {"word": "乙", "suggested_english_meaning": "together", "confidence": "medium", "review_note": "pinyin"}]})
    assert result[0]["confidence"] == "low"


def test_reference_target_extraction_and_evidence_in_prompt(tmp_path):
    assert module.extract_reference_targets("erhua variant of 一點|一点[yi1 dian3]") == ["一點", "一点"]
    rows = [dict(row("一点儿"), candidate_meanings="erhua variant of 一點|一点[yi1 dian3]", reference_or_variant_info="erhua variant of 一點|一点[yi1 dian3]")]
    enriched = module.add_reference_evidence(rows, {"一点": [{"pinyin": "yi1 dian3", "gloss": "a little", "traditional": "一點"}]})
    assert "a little" in module.request_messages(enriched)[1]["content"]


def test_high_confidence_requires_meaning_and_no_auto_approval(tmp_path):
    rows = [row("甲")]
    try:
        module.validate_suggestions(rows, {"suggestions": [{"word": "甲", "suggested_english_meaning": "", "confidence": "high", "review_note": "x"}]})
        assert False
    except ValueError:
        pass
    review = tmp_path / "review.csv"
    with review.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=module.OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerow({"word": "甲", "level_code": "HSK1", "reason": "variant_or_reference_definition"})
    def fake(batch):
        return {"suggestions": [{"word": r["word"], "suggested_english_meaning": "one", "confidence": "high", "review_note": "evidence"} for r in batch]}, None
    # use a complete synthetic 30-row input for the no-approval invariant
    rows = [row(f"a{i}") for i in range(15)] + [row(f"b{i}", reason="multiple_pronunciations") for i in range(10)] + [row(f"c{i}", reason="multiple_cedict_candidates") for i in range(5)]
    input_file = tmp_path / "input.csv"
    with input_file.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=module.OUTPUT_FIELDS); writer.writeheader()
        for r in rows: writer.writerow(r)
    output = tmp_path / "out.csv"
    module.run(input_file, output, fake)
    saved = list(csv.DictReader(output.open(encoding="utf-8-sig", newline="")))
    assert all(r["human_decision"] == "" and r["final_english_meaning"] == "" for r in saved)


def _write_review(path, words):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=module.OUTPUT_FIELDS)
        writer.writeheader()
        for word in words:
            writer.writerow(row(word))


def test_run_all_defaults_to_five_and_resumes_without_duplicate_processing(tmp_path, monkeypatch):
    assert inspect.signature(module.run_all).parameters["batch_size"].default == 5
    review = tmp_path / "review.csv"
    _write_review(review, [f"词{i}" for i in range(10)])
    cedict = tmp_path / "cedict.txt"
    cedict.write_text("", encoding="utf-8")
    output = tmp_path / "suggestions.csv"
    calls = []

    def fake(batch):
        calls.append([r["word"] for r in batch])
        return {"suggestions": [{"word": r["word"], "suggested_english_meaning": "meaning", "confidence": "medium", "review_note": "evidence"} for r in batch]}, None

    monkeypatch.setattr(module.time, "sleep", lambda _: None)
    first = module.run_all(review, output, cedict, translator=fake)
    assert first["processed_count"] == 10
    assert [len(batch) for batch in calls] == [5, 5]
    calls.clear()
    second = module.run_all(review, output, cedict, translator=fake)
    assert second["processed_count"] == 10
    assert calls == []


def test_run_all_splits_413_without_repeating_oversized_batch(tmp_path, monkeypatch):
    review = tmp_path / "review.csv"
    _write_review(review, [f"词{i}" for i in range(5)])
    cedict = tmp_path / "cedict.txt"
    cedict.write_text("", encoding="utf-8")
    output = tmp_path / "suggestions.csv"
    sizes = []

    class TooLarge(Exception):
        status_code = 413

    def fake(batch):
        sizes.append(len(batch))
        if len(batch) > 2:
            raise TooLarge("request too large")
        return {"suggestions": [{"word": r["word"], "suggested_english_meaning": "meaning", "confidence": "low", "review_note": "evidence"} for r in batch]}, None

    monkeypatch.setattr(module.time, "sleep", lambda _: None)
    result = module.run_all(review, output, cedict, translator=fake)
    assert result["processed_count"] == 5
    assert result["413_count"] == 2
    assert result["batch_split_count"] == 2
    assert sizes[0] == 5 and 5 not in sizes[1:]


def test_run_all_keeps_429_retry_separate_from_413(tmp_path, monkeypatch):
    review = tmp_path / "review.csv"
    _write_review(review, ["词0"])
    cedict = tmp_path / "cedict.txt"
    cedict.write_text("", encoding="utf-8")
    output = tmp_path / "suggestions.csv"
    attempts = 0

    class RateLimited(Exception):
        status_code = 429

    def fake(batch):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RateLimited("rate limit")
        return {"suggestions": [{"word": "词0", "suggested_english_meaning": "meaning", "confidence": "low", "review_note": "evidence"}]}, None

    monkeypatch.setattr(module.time, "sleep", lambda _: None)
    result = module.run_all(review, output, cedict, translator=fake, max_retries=1)
    assert result["processed_count"] == 1
    assert result["429_count"] == 1
    assert result["413_count"] == 0
    assert result["transient_retry_count"] == 1


def test_json_validate_failed_splits_without_repeating_oversized_batch(tmp_path, monkeypatch):
    review = tmp_path / "review.csv"
    _write_review(review, [f"词{i}" for i in range(5)])
    cedict = tmp_path / "cedict.txt"
    cedict.write_text("", encoding="utf-8")
    output = tmp_path / "suggestions.csv"
    sizes = []

    class JsonFailure(Exception):
        status_code = 400
        body = {"code": "json_validate_failed"}

    def fake(batch):
        sizes.append(len(batch))
        if len(batch) > 1:
            raise JsonFailure("partial failed_generation")
        return {"suggestions": [{"word": batch[0]["word"], "suggested_english_meaning": "meaning", "confidence": "low", "review_note": "evidence"}]}, None

    monkeypatch.setattr(module.time, "sleep", lambda _: None)
    result = module.run_all(review, output, cedict, translator=fake)
    assert result["processed_count"] == 5
    assert result["json_validate_failed_count"] == 4
    assert result["json_batch_split_count"] == 4
    assert result["json_single_record_failures"] == 0
    assert sizes[0] == 5 and 5 not in sizes[1:]
    assert sizes == [5, 2, 1, 1, 3, 1, 2, 1, 1]


def test_single_json_validate_failed_is_quarantined_and_not_cached(tmp_path, monkeypatch):
    review = tmp_path / "review.csv"
    _write_review(review, ["词0"])
    cedict = tmp_path / "cedict.txt"
    cedict.write_text("", encoding="utf-8")
    output = tmp_path / "suggestions.csv"

    class JsonFailure(Exception):
        status_code = 400
        body = {"error": {"code": "json_validate_failed"}}

    def fake(_batch):
        raise JsonFailure('failed_generation={"suggestions": []}')

    monkeypatch.setattr(module.time, "sleep", lambda _: None)
    result = module.run_all(review, output, cedict, translator=fake)
    assert result["processed_count"] == 0
    assert result["json_single_record_failures"] == 1
    assert list(csv.DictReader(output.open(encoding="utf-8-sig", newline=""))) == []
    failures = json.loads(output.with_name("ai_review_semantic_failures.json").read_text(encoding="utf-8"))
    assert failures[-1]["failure_type"] == "json_validate_failed"
    assert "词0" in failures[-1]["words"]


def test_rate_limit_code_is_retryable_even_when_provider_uses_http_400():
    class RateLimited(Exception):
        status_code = 400
        body = {"error": {"code": "rate_limit_exceeded"}}

    error = RateLimited("rate_limit_exceeded")
    assert "rate_limit_exceeded" in str(error)
    assert not module.is_json_validate_failed(error)


def test_real_openai_bad_request_json_failure_is_caught_and_split(tmp_path, monkeypatch):
    import httpx
    from openai import BadRequestError

    review = tmp_path / "review.csv"
    _write_review(review, [f"词{i}" for i in range(5)])
    cedict = tmp_path / "cedict.txt"
    cedict.write_text("", encoding="utf-8")
    output = tmp_path / "suggestions.csv"
    sizes = []

    def fake(batch):
        sizes.append(len(batch))
        if len(batch) > 1:
            response = httpx.Response(400, request=httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions"), json={"error": {"code": "json_validate_failed"}})
            raise BadRequestError("json_validate_failed", response=response, body={"error": {"code": "json_validate_failed"}})
        return {"suggestions": [{"word": batch[0]["word"], "suggested_english_meaning": "meaning", "confidence": "low", "review_note": "evidence"}]}, None

    monkeypatch.setattr(module.time, "sleep", lambda _: None)
    result = module.run_all(review, output, cedict, translator=fake)
    assert result["processed_count"] == 5
    assert result["json_validate_failed_count"] == 4
    assert result["json_single_record_failures"] == 0
    assert sizes[0] == 5 and 5 not in sizes[1:]


def test_default_cli_uses_full_cache_not_pilot(monkeypatch, capsys):
    seen = {}

    def fake_run_all(review_csv, output_csv, cedict_path, batch_size):
        seen.update({"review": review_csv, "output": output_csv, "cedict": cedict_path, "batch_size": batch_size})
        return {"processed_count": 0}

    monkeypatch.setattr(module, "run_all", fake_run_all)
    monkeypatch.setattr(sys, "argv", ["ai_hsk31_meaning_review.py"])
    module.main()
    assert seen["output"] == module.FULL_OUTPUT_CSV
    assert seen["batch_size"] == 5
    assert json.loads(capsys.readouterr().out)["processed_count"] == 0
