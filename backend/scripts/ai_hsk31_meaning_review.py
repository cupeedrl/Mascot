"""Advisory AI suggestions for HSK meaning review; never edits human decisions."""
from __future__ import annotations

import argparse
import csv
import json
import re
import time
from pathlib import Path
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict, Field

VALID_CONFIDENCE = {"high", "medium", "low"}
OUTPUT_FIELDS = ["word", "level_code", "pinyin", "part_of_speech", "reason", "candidate_meanings", "reference_or_variant_info", "reference_evidence", "suggested_english_meaning", "ai_confidence", "ai_review_note", "human_decision", "final_english_meaning", "human_note"]
FULL_OUTPUT_CSV = Path("tmp/hsk31_meaning_audit/ai_review_suggestions_all.csv")
PILOT_OUTPUT_CSV = Path("tmp/hsk31_meaning_audit/ai_review_suggestions.csv")


class Suggestion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    word: str = Field(min_length=1)
    suggested_english_meaning: str = ""
    confidence: str
    review_note: str = ""


class SuggestionBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    suggestions: list[Suggestion]


SuggestionBatch.model_rebuild(_types_namespace={"Suggestion": Suggestion})


SCHEMA = {"type": "object", "properties": {"suggestions": {"type": "array", "items": {"type": "object", "properties": {"word": {"type": "string"}, "suggested_english_meaning": {"type": "string"}, "confidence": {"type": "string", "enum": ["high", "medium", "low"]}, "review_note": {"type": "string"}}, "required": ["word", "suggested_english_meaning", "confidence", "review_note"], "additionalProperties": False}}}, "required": ["suggestions"], "additionalProperties": False}


def bucket(row: dict[str, str]) -> str:
    reason = row.get("reason", "")
    if "variant_or_reference" in reason:
        return "variant/reference"
    if "multiple_pronunciations" in reason:
        return "multiple pronunciation"
    if "multiple_cedict_candidates" in reason:
        return "multiple senses"
    return "other"


def select_pilot(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped = {name: [] for name in ("variant/reference", "multiple pronunciation", "multiple senses")}
    for row in rows:
        if bucket(row) in grouped:
            grouped[bucket(row)].append(row)
    for values in grouped.values():
        values.sort(key=lambda r: (int(r["level_code"].replace("HSK", "")), r["word"]))
    return grouped["variant/reference"][:15] + grouped["multiple pronunciation"][:10] + grouped["multiple senses"][:5]


def load_cedict(path: Path) -> dict[str, list[dict[str, str]]]:
    result: dict[str, list[dict[str, str]]] = {}
    pattern = re.compile(r"^(\S+) (\S+) \[([^\]]+)\] /(.+)/$")
    for line in path.read_text(encoding="utf-8").splitlines():
        match = pattern.match(line)
        if match:
            result.setdefault(match.group(2), []).append({"pinyin": match.group(3), "gloss": match.group(4), "traditional": match.group(1)})
    return result


def extract_reference_targets(text: str) -> list[str]:
    targets: list[str] = []
    for match in re.finditer(r"(?:variant of|erhua variant of|see|also written)\s+([^;/]+)", text, re.I):
        fragment = match.group(1)
        for value in re.findall(r"[\u4e00-\u9fff]+", fragment):
            if value not in targets:
                targets.append(value)
    return targets


def add_reference_evidence(rows: list[dict[str, str]], cedict: dict[str, list[dict[str, str]]]) -> list[dict[str, str]]:
    enriched = []
    for row in rows:
        targets = extract_reference_targets(row.get("candidate_meanings", "") + " " + row.get("reference_or_variant_info", ""))
        evidence = []
        for target in targets:
            for candidate in cedict.get(target, []):
                evidence.append({"word": target, "pinyin": candidate["pinyin"], "meaning": candidate["gloss"]})
        enriched.append({**row, "reference_evidence": json.dumps(evidence, ensure_ascii=False)})
    return enriched


def validate_suggestions(requested: list[dict[str, str]], payload: Any) -> list[dict[str, str]]:
    data = SuggestionBatch.model_validate(payload)
    requested_words = [r["word"] for r in requested]
    seen = [item.word for item in data.suggestions]
    if len(seen) != len(requested_words) or set(seen) != set(requested_words) or len(set(seen)) != len(seen):
        raise ValueError("suggestion words must match requested words exactly once")
    result = []
    for item in data.suggestions:
        if item.confidence not in VALID_CONFIDENCE:
            raise ValueError("invalid confidence")
        if item.confidence == "high" and not item.suggested_english_meaning.strip():
            raise ValueError("high-confidence suggestion must be non-empty")
        if re.search(r"[à-ỹĐđ]|[\u4e00-\u9fff]|```|\*\*", item.suggested_english_meaning):
            raise ValueError("suggestion contains Vietnamese, Chinese, or markdown")
        result.append(item.model_dump())
    by_word = {item["word"]: item for item in result}
    return [by_word[word] for word in requested_words]


def _has_error_code(value: Any, code: str) -> bool:
    if isinstance(value, dict):
        return value.get("code") == code or any(_has_error_code(item, code) for item in value.values())
    if isinstance(value, list):
        return any(_has_error_code(item, code) for item in value)
    return False


def is_json_validate_failed(exc: Exception) -> bool:
    """Recognize Groq's incomplete strict-JSON response without trusting it."""
    status = getattr(exc, "status_code", None) or getattr(getattr(exc, "response", None), "status_code", None)
    if status != 400:
        return False
    body = getattr(exc, "body", None)
    if _has_error_code(body, "json_validate_failed"):
        return True
    response = getattr(exc, "response", None)
    try:
        response_body = response.json() if response is not None and hasattr(response, "json") else None
    except (TypeError, ValueError):
        response_body = None
    if _has_error_code(response_body, "json_validate_failed"):
        return True
    return "json_validate_failed" in str(exc).lower()


def request_messages(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    evidence = []
    for r in rows:
        candidate_meanings = r.get("candidate_meanings", "")
        reference_info = r.get("reference_or_variant_info", "")
        item = {"word": r["word"], "level_code": r["level_code"], "pinyin": r.get("pinyin", ""), "part_of_speech": r.get("part_of_speech", ""), "candidate_meanings": candidate_meanings, "reference_evidence": json.loads(r.get("reference_evidence", "[]")), "reason": r.get("reason", "")}
        if reference_info and reference_info != candidate_meanings:
            item["reference_or_variant_info"] = reference_info
        evidence.append(item)
    return [{"role": "system", "content": "Provide advisory English dictionary-meaning suggestions using ONLY the supplied candidate meanings and reference_evidence. Do not use general HSK or Chinese knowledge to fill gaps. For variants/references, select or normalize only meanings explicitly present in the supplied target evidence. Prefer supplied Pinyin for pronunciation conflicts. Preserve multiple supported related senses; do not combine unrelated senses. If evidence is insufficient, use confidence low and an empty suggestion. Output only the requested JSON schema, no Vietnamese, Chinese, Markdown, examples, or explanations. Human review remains authoritative."}, {"role": "user", "content": json.dumps(evidence, ensure_ascii=False)}]


def call_ai(rows: list[dict[str, str]], settings: Any) -> tuple[Any, Any]:
    from openai import OpenAI
    options = {"api_key": settings.api_key, "base_url": settings.base_url, "timeout": settings.timeout_seconds, "max_retries": 0}
    client = OpenAI(**{k: v for k, v in options.items() if v is not None})
    response = client.chat.completions.create(model=settings.model, messages=request_messages(rows), response_format={"type": "json_schema", "json_schema": {"name": "hsk31_meaning_review_suggestions", "strict": True, "schema": SCHEMA}}, max_tokens=2000)
    return json.loads(response.choices[0].message.content or ""), getattr(response, "usage", None)


def run(review_csv: Path, output_csv: Path, cedict_path: Path | Callable[[list[dict[str, str]]], tuple[Any, Any]] | None = None, previous_csv: Path | None = None, translator: Callable[[list[dict[str, str]]], tuple[Any, Any]] | None = None) -> dict[str, Any]:
    with review_csv.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if callable(cedict_path) and translator is None:
        translator, cedict_path = cedict_path, None
    pilot = add_reference_evidence(select_pilot(rows), load_cedict(cedict_path) if isinstance(cedict_path, Path) else {})
    if len(pilot) != 30:
        raise ValueError(f"expected 30 pilot rows, got {len(pilot)}")
    payload, usage = translator(pilot) if translator else call_ai(pilot, __import__("enrich_hsk31_vietnamese", fromlist=["load_translation_settings"]).load_translation_settings())
    suggestions = validate_suggestions(pilot, payload)
    suggestion_map = {s["word"]: s for s in suggestions}
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        for row in pilot:
            suggestion = suggestion_map[row["word"]]
            writer.writerow({**{key: row.get(key, "") for key in OUTPUT_FIELDS[:8]}, "suggested_english_meaning": suggestion["suggested_english_meaning"], "ai_confidence": suggestion["confidence"], "ai_review_note": suggestion["review_note"], "human_decision": "", "final_english_meaning": "", "human_note": ""})
    tokens = int(getattr(usage, "total_tokens", 0) or (usage.get("total_tokens", 0) if isinstance(usage, dict) else 0)) if usage else 0
    result = {"requested_count": 30, "returned_count": len(suggestions), "high": sum(s["confidence"] == "high" for s in suggestions), "medium": sum(s["confidence"] == "medium" for s in suggestions), "low": sum(s["confidence"] == "low" for s in suggestions), "usage_total_tokens": tokens, "failed_records": 0}
    if previous_csv:
        with previous_csv.open(encoding="utf-8-sig", newline="") as handle:
            old = {r["word"]: r for r in csv.DictReader(handle)}
        comparison = [{"word": r["word"], "reason": r.get("reason", ""), "original_candidates": r.get("candidate_meanings", ""), "reference_evidence": r.get("reference_evidence", "[]"), "old_suggestion": old.get(r["word"], {}).get("suggested_english_meaning", ""), "new_suggestion": suggestion_map[r["word"]]["suggested_english_meaning"], "old_confidence": old.get(r["word"], {}).get("ai_confidence", ""), "new_confidence": suggestion_map[r["word"]]["confidence"], "review_note": suggestion_map[r["word"]]["review_note"]} for r in pilot]
        output_csv.with_name("ai_review_comparison.json").write_text(json.dumps(comparison, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def run_all(review_csv: Path, output_csv: Path, cedict_path: Path, batch_size: int = 5, max_retries: int = 2, translator: Callable[[list[dict[str, str]]], tuple[Any, Any]] | None = None) -> dict[str, Any]:
    with review_csv.open(encoding="utf-8-sig", newline="") as handle:
        source_rows = list(csv.DictReader(handle))
    rows = sorted(add_reference_evidence(source_rows, load_cedict(cedict_path)), key=lambda r: (r["word"]))
    cached: dict[str, dict[str, str]] = {}
    if output_csv.exists():
        with output_csv.open(encoding="utf-8-sig", newline="") as handle:
            cached = {r["word"]: r for r in csv.DictReader(handle) if r.get("word")}
    semantic_path = output_csv.with_name("ai_review_semantic_failures.json")
    semantic_failures = json.loads(semantic_path.read_text(encoding="utf-8")) if semantic_path.exists() else []
    semantic_words = {word for item in semantic_failures for word in item.get("words", [])}
    pending = [r for r in rows if r["word"] not in cached and r["word"] not in semantic_words]
    batches = [pending[i:i + batch_size] for i in range(0, len(pending), batch_size)]
    total_tokens, retries_used, rate_limit_count, semantic_failure_count, too_large_count, split_count, json_failure_count, json_split_count, single_record_failures, total_wait_seconds = 0, 0, 0, 0, 0, 0, 0, 0, 0, 0.0
    failed = []
    successful_batches = 0
    batch_index = 0
    while batch_index < len(batches):
        batch = batches[batch_index]
        last_error = None
        split_happened = False
        for attempt in range(max_retries + 1):
            try:
                payload, usage = translator(batch) if translator else call_ai(batch, __import__("enrich_hsk31_vietnamese", fromlist=["load_translation_settings"]).load_translation_settings())
                suggestions = validate_suggestions(batch, payload)
                suggestion_map = {s["word"]: s for s in suggestions}
                for row in batch:
                    suggestion = suggestion_map[row["word"]]
                    cached[row["word"]] = {**{key: row.get(key, "") for key in OUTPUT_FIELDS[:8]}, "suggested_english_meaning": suggestion["suggested_english_meaning"], "ai_confidence": suggestion["confidence"], "ai_review_note": suggestion["review_note"], "human_decision": "", "final_english_meaning": "", "human_note": ""}
                total_tokens += int(getattr(usage, "total_tokens", 0) or (usage.get("total_tokens", 0) if isinstance(usage, dict) else 0)) if usage else 0
                successful_batches += 1
                if batch_index < len(batches) - 1:
                    time.sleep(35)
                    total_wait_seconds += 35
                break
            except Exception as exc:
                last_error = str(exc)
                status = getattr(exc, "status_code", None) or getattr(getattr(exc, "response", None), "status_code", None)
                is_too_large = status == 413 or ("413" in str(exc) and "tokens" in str(exc).lower())
                is_rate_limit = not is_too_large and (status == 429 or type(exc).__name__ == "RateLimitError" or "rate_limit" in str(exc).lower())
                is_json_failure = is_json_validate_failed(exc)
                if is_too_large:
                    too_large_count += 1
                    if len(batch) > 1:
                        midpoint = max(1, len(batch) // 2)
                        batches[batch_index:batch_index + 1] = [batch[:midpoint], batch[midpoint:]]
                        split_count += 1
                        last_error = None
                        split_happened = True
                        break
                    failed.append({"batch_index": batch_index, "words": [r["word"] for r in batch], "error": last_error, "failure_type": "request_too_large"})
                    last_error = None
                    break
                if is_json_failure:
                    json_failure_count += 1
                    if len(batch) > 1:
                        midpoint = max(1, len(batch) // 2)
                        batches[batch_index:batch_index + 1] = [batch[:midpoint], batch[midpoint:]]
                        split_count += 1
                        json_split_count += 1
                        last_error = None
                        split_happened = True
                        break
                    single_record_failures += 1
                    semantic_failure_count += 1
                    semantic_failures.append({"batch_index": batch_index, "words": [batch[0]["word"]], "error": last_error, "failure_type": "json_validate_failed"})
                    failed.append({"batch_index": batch_index, "words": [batch[0]["word"]], "error": last_error, "failure_type": "json_validate_failed"})
                    last_error = None
                    break
                retryable = is_rate_limit or type(exc).__name__ in {"APIConnectionError", "APITimeoutError", "AIProviderTimeoutError"} or status in {500, 502, 503, 504}
                if is_rate_limit:
                    rate_limit_count += 1
                if not retryable:
                    semantic_failure_count += 1
                    semantic_failures.append({"batch_index": batch_index, "words": [r["word"] for r in batch], "error": last_error})
                    break
                if attempt < max_retries:
                    wait = 35.0
                    headers = getattr(getattr(exc, "response", None), "headers", {}) or {}
                    retry_after = headers.get("retry-after") if hasattr(headers, "get") else None
                    if retry_after:
                        try:
                            wait = min(120.0, max(1.0, float(retry_after)))
                        except ValueError:
                            pass
                    time.sleep(wait)
                    total_wait_seconds += wait
                    retries_used += 1
        else:
            pass
        if split_happened:
            continue
        if last_error and len(cached) < len(rows) and not all(r["word"] in cached for r in batch) and not any(f.get("words") == [r["word"] for r in batch] for f in failed):
            failed.append({"batch_index": batch_index, "words": [r["word"] for r in batch], "error": last_error})
        ordered = sorted(cached.values(), key=lambda r: ({"high": 0, "medium": 1, "low": 2}.get(r.get("ai_confidence", "low"), 3), int(r.get("level_code", "HSK999").replace("HSK", "")), r.get("reason", ""), r.get("word", "")))
        output_csv.parent.mkdir(parents=True, exist_ok=True)
        with output_csv.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS); writer.writeheader(); writer.writerows(ordered)
        progress = {"requested_count": len(rows), "processed_count": len(cached), "remaining_count": len(rows) - len(cached), "successful_batches": successful_batches, "413_count": too_large_count, "batch_split_count": split_count, "json_validate_failed_count": json_failure_count, "json_batch_split_count": json_split_count, "json_single_record_failures": single_record_failures, "429_count": rate_limit_count, "semantic_failure_count": semantic_failure_count, "transient_retry_count": retries_used, "usage_total_tokens": total_tokens, "total_wait_seconds": total_wait_seconds}
        output_csv.with_name("ai_review_suggestions_all_progress.json").write_text(json.dumps(progress, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        batch_index += 1
    summary = {"requested_count": len(rows), "processed_count": len(cached), "remaining_count": len(rows) - len(cached), "failed_count": sum(len(f["words"]) for f in failed), "batch_count": len(batches), "successful_batches": successful_batches, "413_count": too_large_count, "batch_split_count": split_count, "json_validate_failed_count": json_failure_count, "json_batch_split_count": json_split_count, "json_single_record_failures": single_record_failures, "429_count": rate_limit_count, "semantic_failure_count": semantic_failure_count, "transient_retry_count": retries_used, "retry_count": retries_used, "usage_total_tokens": total_tokens, "total_wait_seconds": total_wait_seconds, "failed_batches": failed}
    semantic_path.write_text(json.dumps(semantic_failures, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    output_csv.with_name("ai_review_suggestions_all_report.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--review-csv", type=Path, default=Path("tmp/hsk31_meaning_audit/meaning_review.csv"))
    parser.add_argument("--output-csv", type=Path, default=None, help="Override the pilot/full output path")
    parser.add_argument("--cedict", type=Path, default=Path("C:/Users/Dat/AppData/Local/Temp/cc-cedict-audit/cedict.txt"))
    parser.add_argument("--previous-csv", type=Path, default=PILOT_OUTPUT_CSV)
    parser.add_argument("--pilot", action="store_true", help="Run the fixed 30-record pilot; normal execution resumes the full advisory run")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--batch-size", type=int, default=5)
    args = parser.parse_args()
    if args.pilot:
        output_csv = args.output_csv or PILOT_OUTPUT_CSV
        result = run(args.review_csv, output_csv, args.cedict, args.previous_csv if args.previous_csv != output_csv else None)
    else:
        output_csv = args.output_csv or FULL_OUTPUT_CSV
        result = run_all(args.review_csv, output_csv, args.cedict, args.batch_size)
    # Keep artifacts Unicode, but make the one-line CLI summary safe for
    # Windows consoles that still use a legacy code page.
    print(json.dumps(result, ensure_ascii=True))


if __name__ == "__main__":
    main()
