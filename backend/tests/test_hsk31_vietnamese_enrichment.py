import importlib.util
import json
from pathlib import Path

import pytest


SCRIPT = Path(__file__).parents[1] / "scripts" / "enrich_hsk31_vietnamese.py"
spec = importlib.util.spec_from_file_location("hsk_translate", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(module)


def record(word, meaning="meaning", **extra):
    return {"word": word, "level_code": "HSK1", "meaning": meaning, "ipa": "x", "part_of_speech": "noun", "qa": {}, **extra}


def test_eligible_selection_excludes_ambiguous_and_normalization():
    rows = [record("甲"), record("乙", qa={"ambiguous": True}), record("丙", meaning=None)]
    assert [r["word"] for r in module.select_eligible_records(rows, {"甲"})] == []


def test_batching_and_structured_validation_are_deterministic():
    rows = [record("乙"), record("甲")]
    batches = module.build_batches(module.select_eligible_records(rows), 1)
    assert [[r["word"] for r in b] for b in batches] == [["乙"], ["甲"]]
    assert module.validate_translation_batch([record("甲")], {"translations": [{"word": "甲", "translation": "học"}]}) == {"甲": "học"}


@pytest.mark.parametrize("payload", [
    {"translations": []},
    {"translations": [{"word": "乙", "translation": "x"}]},
    {"translations": [{"word": "甲", "translation": "x"}, {"word": "甲", "translation": "y"}]},
])
def test_invalid_batch_is_rejected(payload):
    with pytest.raises(module.TranslationBatchError):
        module.validate_translation_batch([record("甲")], payload)


def test_quality_flags_and_no_database_or_catalog_imports():
    flags = module.translation_flags(record("甲", meaning="study"), "study")
    assert "identical_to_english" in flags
    assert "mostly_english" in flags
    assert "mostly_english" not in module.translation_flags(record("乙", meaning="middle school"), "trường trung học cơ sở")
    source = SCRIPT.read_text(encoding="utf-8")
    assert "sqlalchemy" not in source.lower()
    assert "app.catalog.data" not in source


def test_prompt_requires_normalized_meaning_and_distinct_sense_preservation():
    messages = module._prompt([record("上", meaning="up; attend class; directional complement", part_of_speech="other")])
    prompt = messages[0]["content"]
    assert "semantic authority" in prompt
    assert "distinct senses" in prompt
    assert "function words" in prompt
    assert "semicolon-separated" in prompt
    assert "Chinese characters literally" in prompt


def test_semantic_short_only_flags_multi_sense_compression():
    multi = record("上", meaning="up; attend class; directional complement")
    assert "semantically_short" in module.translation_flags(multi, "trên")
    assert "semantically_short" not in module.translation_flags(multi, "trên; đi học; bổ ngữ chỉ hướng")
    related = record("一带", meaning="region; area")
    assert "semantically_short" not in module.translation_flags(related, "khu vực")


def test_clean_pilot_comparison_preserves_old_and_new_outputs(tmp_path):
    records = tmp_path / "pilot_records.json"
    records.write_text(json.dumps([record("甲", meaning="one; first")], ensure_ascii=False), encoding="utf-8")
    old_dir = tmp_path / "old"
    new_dir = tmp_path / "new"
    old_dir.mkdir()
    new_dir.mkdir()
    (old_dir / "translations.json").write_text(json.dumps({"甲": {"translation": "một"}}, ensure_ascii=False), encoding="utf-8")
    (old_dir / "translation_qa.json").write_text(json.dumps({"甲": {"flags": ["semantically_short"]}}), encoding="utf-8")
    (new_dir / "translations.json").write_text(json.dumps({"甲": {"translation": "một; đầu tiên"}}, ensure_ascii=False), encoding="utf-8")
    (new_dir / "translation_qa.json").write_text(json.dumps({"甲": {"flags": []}}), encoding="utf-8")
    output = tmp_path / "comparison.json"
    module.write_clean_pilot_comparison(old_dir, new_dir, records, output)
    comparison = json.loads(output.read_text(encoding="utf-8"))
    assert comparison == [{"word": "甲", "normalized_english_meaning": "one; first", "old_translation": "một", "new_translation": "một; đầu tiên", "old_qa": ["semantically_short"], "new_qa": []}]


def test_pilot_comparison_uses_fixed_isolated_paths():
    assert module.CLEAN_PILOT_RECORDS.as_posix().endswith("hsk31_clean_catalog/pilot_records.json")
    assert module.CLEAN_PILOT2_DIR.as_posix().endswith("hsk31_clean_translation_pilot2")


def test_strict_semantic_boundary_flags_known_unsupported_senses():
    source = record("一边", meaning="one side; either side; on the one hand; doing while")
    assert "unsupported_sense_review" in module.translation_flags(source, "một bên; hai mặt; một khi")
    supported = record("一边", meaning="one side; either side; on the one hand; doing while")
    assert "unsupported_sense_review" not in module.translation_flags(supported, "một bên; một mặt; vừa... vừa...")


def test_prompt_makes_normalized_meaning_an_absolute_boundary():
    prompt = module._prompt([record("上", meaning="up; directional complement")])[0]["content"]
    assert "absolute semantic boundary" in prompt
    assert "Every Vietnamese sense must be directly justified" in prompt
    assert "external knowledge" in prompt
    assert "grammatical labels" in prompt
    assert "[bổ ngữ chỉ hướng]" in prompt


def test_pilot3_comparison_keeps_pilot1_and_pilot2_separate(tmp_path):
    records = tmp_path / "pilot.json"
    records.write_text(json.dumps([record("甲", meaning="one; first")], ensure_ascii=False), encoding="utf-8")
    dirs = [tmp_path / name for name in ("pilot1", "pilot2", "pilot3")]
    for directory in dirs:
        directory.mkdir()
    (dirs[0] / "translations.json").write_text(json.dumps({"甲": {"translation": "một"}}), encoding="utf-8")
    (dirs[1] / "translations.json").write_text(json.dumps({"甲": {"translation": "một; đầu tiên"}}), encoding="utf-8")
    (dirs[2] / "translations.json").write_text(json.dumps({"甲": {"translation": "một; đầu tiên"}}), encoding="utf-8")
    (dirs[2] / "translation_qa.json").write_text(json.dumps({"甲": {"flags": []}}), encoding="utf-8")
    output = tmp_path / "comparison.json"
    module.write_clean_pilot3_comparison(records, dirs[0], dirs[1], dirs[2], output)
    item = json.loads(output.read_text(encoding="utf-8"))[0]
    assert item["pilot1_translation"] == "một"
    assert item["pilot2_translation"] == "một; đầu tiên"
    assert item["pilot3_translation"] == "một; đầu tiên"


def test_pipeline_persists_and_resumes_without_production_writes(tmp_path):
    audit = tmp_path / "audit"
    audit.mkdir()
    (audit / "canonical.json").write_text(json.dumps([record("甲"), record("乙", qa={"ambiguous": True})]), encoding="utf-8")
    (audit / "normalization.json").write_text("[]", encoding="utf-8")
    (audit / "missing.json").write_text(json.dumps([{"word": "乙"}]), encoding="utf-8")
    (audit / "ambiguous.json").write_text(json.dumps([{"word": "乙", "candidate_glosses": ["x"]}]), encoding="utf-8")
    calls = []
    def translate(batch):
        calls.append([r["word"] for r in batch])
        return {"translations": [{"word": r["word"], "translation": "học"} for r in batch]}, None
    out = module.run_pipeline(audit / "canonical.json", tmp_path / "out", audit / "normalization.json", audit / "missing.json", audit / "ambiguous.json", translator=translate)
    assert out["eligible_count"] == 1 and calls == [["甲"]]
    module.run_pipeline(audit / "canonical.json", tmp_path / "out", audit / "normalization.json", audit / "missing.json", audit / "ambiguous.json", translator=translate)
    assert calls == [["甲"]]
    assert json.loads((tmp_path / "out" / "deferred_records.json").read_text(encoding="utf-8"))[0]["candidate_meanings"] == ["x"]


class APIConnectionError(Exception):
    pass


class RateLimitError(Exception):
    status_code = 429


def audit_files(tmp_path, rows):
    audit = tmp_path / "audit"
    audit.mkdir()
    (audit / "canonical.json").write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    for name in ("normalization", "missing", "ambiguous"):
        (audit / f"{name}.json").write_text("[]", encoding="utf-8")
    return audit


def test_connection_failure_circuit_breaker_stops_and_leaves_rows_resumable(tmp_path):
    audit = audit_files(tmp_path, [record("甲"), record("乙")])
    calls = []

    def unavailable(batch):
        calls.append([item["word"] for item in batch])
        raise APIConnectionError("Connection error: [WinError 10013]")

    out = module.run_pipeline(
        audit / "canonical.json", tmp_path / "out", audit / "normalization.json",
        audit / "missing.json", audit / "ambiguous.json", batch_size=1,
        translator=unavailable, retries=10, connection_failure_threshold=3,
    )

    assert len(calls) == 3
    assert out["circuit_breaker_triggered"] is True
    assert out["consecutive_connection_failures"] == 3
    assert out["stop_reason"] == "provider_connection_unavailable"
    assert out["translated_count"] == 0
    assert json.loads((tmp_path / "out" / "translation_failures.json").read_text(encoding="utf-8")) == []
    progress = json.loads((tmp_path / "out" / "translation_progress.json").read_text(encoding="utf-8"))
    assert progress["remaining"] == 2
    assert progress["record_translation_failures"] == 0


def test_circuit_breaker_preserves_successful_cache(tmp_path):
    audit = audit_files(tmp_path, [record("甲"), record("乙")])
    attempts = 0

    def one_success_then_unavailable(batch):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return {"translations": [{"word": batch[0]["word"], "translation": "học"}]}, None
        raise APIConnectionError("Connection error")

    out = module.run_pipeline(
        audit / "canonical.json", tmp_path / "out", audit / "normalization.json",
        audit / "missing.json", audit / "ambiguous.json", batch_size=1,
        translator=one_success_then_unavailable, retries=5, connection_failure_threshold=3,
    )
    cache = json.loads((tmp_path / "out" / "translations.json").read_text(encoding="utf-8"))
    assert list(cache) == ["乙"]  # eligible records are sorted by Unicode code point
    assert out["translated_count"] == 1
    assert out["circuit_breaker_triggered"] is True


def test_http_429_and_semantic_failures_do_not_trigger_connection_breaker(tmp_path):
    audit = audit_files(tmp_path, [record("甲")])

    def quota(_batch):
        raise RateLimitError("HTTP 429 rate_limit_exceeded daily token quota")

    quota_result = module.run_pipeline(
        audit / "canonical.json", tmp_path / "quota", audit / "normalization.json",
        audit / "missing.json", audit / "ambiguous.json", translator=quota,
    )
    assert quota_result["quota_exhausted"] is True
    assert quota_result["http_429_count"] == 1
    assert quota_result["circuit_breaker_triggered"] is False

    def invalid(_batch):
        return {"translations": []}, None

    semantic_result = module.run_pipeline(
        audit / "canonical.json", tmp_path / "semantic", audit / "normalization.json",
        audit / "missing.json", audit / "ambiguous.json", translator=invalid, retries=0,
    )
    assert semantic_result["schema_failure_count"] == 1
    assert semantic_result["circuit_breaker_triggered"] is False
    assert len(json.loads((tmp_path / "semantic" / "translation_failures.json").read_text(encoding="utf-8"))) == 1


def test_reconciliation_removes_only_temporary_failures_and_preserves_cache(tmp_path):
    audit = audit_files(tmp_path, [record("甲"), record("乙"), record("丙")])
    output = tmp_path / "out"
    output.mkdir()
    (output / "translations.json").write_text(json.dumps({"甲": {**record("甲"), "translation": "học"}}, ensure_ascii=False), encoding="utf-8")
    (output / "translation_qa.json").write_text(json.dumps({"甲": {"word": "甲", "flags": []}}, ensure_ascii=False), encoding="utf-8")
    (output / "translation_failures.json").write_text(json.dumps([
        {"words": ["乙"], "error": "Connection error."},
        {"words": ["丙"], "error": "response is missing requested words"},
    ], ensure_ascii=False), encoding="utf-8")

    result = module.reconcile_temporary_failures(audit / "canonical.json", output, audit / "normalization.json")

    assert result["cached"] == 1
    assert result["remaining"] == 2
    assert result["reconciled_temporary_failure_count"] == 1
    assert json.loads((output / "translations.json").read_text(encoding="utf-8"))["甲"]["translation"] == "học"
    failures = json.loads((output / "translation_failures.json").read_text(encoding="utf-8"))
    assert failures == [{"words": ["丙"], "error": "response is missing requested words"}]


def test_clean_full_reporting_ignores_stale_legacy_deferred_references(tmp_path):
    rows = [record(f"词{index:04d}") for index in range(4876)]
    audit = audit_files(tmp_path, rows)
    stale_missing = [{"word": item["word"]} for item in rows[:197]]
    (audit / "missing.json").write_text(json.dumps(stale_missing, ensure_ascii=False), encoding="utf-8")
    output = tmp_path / "out"
    output.mkdir()
    cached = {
        item["word"]: {**item, "translation": "nghĩa"}
        for item in rows[:25]
    }
    (output / "translations.json").write_text(json.dumps(cached, ensure_ascii=False), encoding="utf-8")

    result = module.run_pipeline(
        audit / "canonical.json",
        output,
        audit / "normalization.json",
        audit / "missing.json",
        audit / "ambiguous.json",
        pilot_count=0,
        translator=lambda _batch: pytest.fail("provider must not be called"),
    )

    assert result["eligible_count"] == 4876
    assert result["deferred_count"] == 0
    assert result["stale_legacy_deferred_reference_count"] == 197
    assert result["cached_count"] == 25
    assert result["remaining_count"] == 4851
    assert json.loads((output / "deferred_records.json").read_text(encoding="utf-8")) == []


def test_gemini_provider_settings_use_dedicated_key_and_default_model(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-test-secret")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
    settings = module.load_translation_settings("gemini")
    assert settings.provider == "gemini"
    assert settings.api_key == "gemini-test-secret"
    assert settings.model == "gemini-3.1-flash-lite"
    assert settings.base_url == "https://generativelanguage.googleapis.com/v1beta"


def test_gemini_structured_response_parsing_and_secret_safety(monkeypatch):
    import httpx

    secret = "gemini-test-secret"
    seen = {}

    def handler(request):
        seen["body"] = json.loads(request.content)
        assert request.headers["x-goog-api-key"] == secret
        return httpx.Response(200, json={
            "candidates": [{
                "finishReason": "STOP",
                "content": {"parts": [{"text": json.dumps({"translations": [{"word": "甲", "translation": "học"}]}, ensure_ascii=False)}]},
            }],
            "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 4, "totalTokenCount": 14},
        })

    settings = module.TranslationSettings("gemini", secret, "gemini-3.1-flash-lite", "https://generativelanguage.googleapis.com/v1beta", 5, 2000)
    payload, usage = module.gemini_translate([record("甲")], settings, transport=httpx.MockTransport(handler))
    assert module.validate_translation_batch([record("甲")], payload) == {"甲": "học"}
    assert usage["total_tokens"] == 14
    assert seen["body"]["generationConfig"]["responseMimeType"] == "application/json"
    assert seen["body"]["generationConfig"]["responseJsonSchema"] == module.TRANSLATION_JSON_SCHEMA
    assert secret not in json.dumps(seen["body"])


def test_gemini_http_error_is_sanitized_and_classified(monkeypatch):
    import httpx

    secret = "gemini-test-secret"

    def handler(_request):
        return httpx.Response(429, headers={"retry-after": "60"}, json={"error": {"status": "RESOURCE_EXHAUSTED", "message": "Quota exhausted"}})

    settings = module.TranslationSettings("gemini", secret, "gemini-3.1-flash-lite", "https://generativelanguage.googleapis.com/v1beta", 5, 2000)
    with pytest.raises(module.OfflineProviderError) as caught:
        module.gemini_translate([record("甲")], settings, transport=httpx.MockTransport(handler))
    assert caught.value.status_code == 429
    assert caught.value.code == "RESOURCE_EXHAUSTED"
    assert caught.value.retry_after == "60"
    assert secret not in str(caught.value)
    assert module.is_provider_connection_error(caught.value) is False


def test_gemini_resume_reuses_55_cached_groq_records_and_adds_provenance(tmp_path, monkeypatch):
    rows = [record(f"词{index:02d}") for index in range(65)]
    audit = audit_files(tmp_path, rows)
    output = tmp_path / "out"
    output.mkdir()
    cached = {item["word"]: {**item, "translation": "cũ"} for item in rows[:55]}
    (output / "translations.json").write_text(json.dumps(cached, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-test-secret")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
    requested = []

    def fake_translate(batch, settings):
        requested.extend(item["word"] for item in batch)
        assert settings.provider == "gemini"
        return {"translations": [{"word": item["word"], "translation": "nghĩa"} for item in batch]}, {"total_tokens": 20}

    monkeypatch.setattr(module, "translate_batch", fake_translate)
    result = module.run_pipeline(
        audit / "canonical.json", output, audit / "normalization.json",
        audit / "missing.json", audit / "ambiguous.json", batch_size=10,
        pilot_count=10, retries=0, provider="gemini",
    )

    final_cache = json.loads((output / "translations.json").read_text(encoding="utf-8"))
    assert len(final_cache) == 65
    assert final_cache[rows[0]["word"]]["translation"] == "cũ"
    assert requested == [item["word"] for item in rows[55:]]
    assert final_cache[rows[55]["word"]]["sources"]["vietnamese_translation_provider"] == "gemini"
    assert final_cache[rows[55]["word"]]["sources"]["vietnamese_translation_model"] == "gemini-3.1-flash-lite"
    assert result["cached_count"] == 65
    assert result["remaining_count"] == 0


def test_provider_dispatch_keeps_groq_path(monkeypatch):
    expected = ({"translations": []}, {"total_tokens": 0})
    monkeypatch.setattr(module, "openai_translate", lambda batch, settings: expected)
    settings = module.TranslationSettings("groq", "secret", "openai/gpt-oss-20b", "https://api.groq.com/openai/v1", 5, 2000)
    assert module.translate_batch([], settings) == expected
