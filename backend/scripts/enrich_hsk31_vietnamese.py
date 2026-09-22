"""Offline, resumable Vietnamese enrichment for the HSK audit output.

This script is deliberately a data-preparation tool: it never imports the
database session or writes production catalog files.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import time
from pathlib import Path
from typing import Any, Callable, Iterable

from pydantic import BaseModel, ConfigDict, Field


class TranslationBatchError(ValueError):
    pass


class OfflineProviderError(RuntimeError):
    def __init__(self, message: str, *, status_code: int, code: str | None = None, retry_after: str | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.retry_after = retry_after


class TranslationItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    word: str = Field(min_length=1)
    translation: str = Field(min_length=1)


class TranslationBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    translations: list[TranslationItem]


CLEAN_PILOT_RECORDS = Path("tmp/hsk31_clean_catalog/pilot_records.json")
CLEAN_PILOT_OLD_DIR = Path("tmp/hsk31_clean_translation")
CLEAN_PILOT2_DIR = Path("tmp/hsk31_clean_translation_pilot2")
CLEAN_PILOT3_DIR = Path("tmp/hsk31_clean_translation_pilot3")
CLEAN_FULL_DIR = Path("tmp/hsk31_clean_translation_full")


TRANSLATION_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "translations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "word": {"type": "string"},
                    "translation": {"type": "string"},
                },
                "required": ["word", "translation"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["translations"],
    "additionalProperties": False,
}


class TranslationSettings:
    def __init__(self, provider: str, api_key: str, model: str, base_url: str | None, timeout_seconds: float, max_output_tokens: int) -> None:
        self.provider = provider
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds
        self.max_output_tokens = max_output_tokens


def _load_provider_env() -> None:
    """Load only provider variables; application-required secrets are irrelevant here."""
    candidates = [Path.cwd() / ".env", Path(__file__).resolve().parents[2] / ".env", Path(__file__).resolve().parents[1] / ".env"]
    for path in candidates:
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key, value = key.strip(), value.strip().strip('"').strip("'")
            if key in {"AI_PROVIDER", "GROQ_API_KEY", "GROQ_MODEL", "GROQ_BASE_URL", "OPENAI_API_KEY", "OPENAI_MODEL", "GEMINI_API_KEY", "GEMINI_MODEL", "GEMINI_BASE_URL", "AI_REQUEST_TIMEOUT_SECONDS", "AI_MAX_OUTPUT_TOKENS"}:
                os.environ.setdefault(key, value)


def load_translation_settings(provider_override: str | None = None) -> TranslationSettings:
    _load_provider_env()
    provider = (provider_override or os.getenv("AI_PROVIDER", "groq")).lower()
    if provider not in {"groq", "gemini"}:
        raise RuntimeError(f"Unsupported offline translation provider: {provider}")
    if provider == "gemini":
        key = os.getenv("GEMINI_API_KEY", "").strip()
        model = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
        base_url = os.getenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta")
    else:
        key = os.getenv("GROQ_API_KEY", "").strip()
        model = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
        base_url = os.getenv("GROQ_BASE_URL")
    if not key:
        raise RuntimeError(f"Configured {provider} API key is missing")
    return TranslationSettings(
        provider=provider,
        api_key=key,
        model=model,
        base_url=base_url,
        timeout_seconds=float(os.getenv("AI_REQUEST_TIMEOUT_SECONDS", "20")),
        # Twenty concise dictionary rows need more room than the app's chat default.
        max_output_tokens=int(os.getenv("HSK_TRANSLATION_MAX_OUTPUT_TOKENS", "2000")),
    )


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def select_eligible_records(
    records: list[dict[str, Any]], normalization_words: set[str] | None = None
) -> list[dict[str, Any]]:
    blocked = normalization_words or set()
    return sorted(
        [
            r for r in records
            if r.get("word") and r.get("level_code") and r.get("meaning")
            and not r.get("qa", {}).get("ambiguous", False)
            and not r.get("qa", {}).get("missing_meaning", False)
            and r["word"] not in blocked
        ],
        key=lambda r: r["word"],
    )


def build_batches(records: list[dict[str, Any]], batch_size: int = 20) -> list[list[dict[str, Any]]]:
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    return [records[i : i + batch_size] for i in range(0, len(records), batch_size)]


def validate_translation_batch(
    requested: list[dict[str, Any]], payload: Any
) -> dict[str, str]:
    items = payload.get("translations") if isinstance(payload, dict) else payload
    if not isinstance(items, list):
        raise TranslationBatchError("response must be a JSON array or translations object")
    requested_words = [r["word"] for r in requested]
    seen: list[str] = []
    result: dict[str, str] = {}
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("word"), str):
            raise TranslationBatchError("each item must contain a word")
        word = item["word"]
        if word not in requested_words:
            raise TranslationBatchError("response contains an unknown word")
        if word in seen:
            raise TranslationBatchError("response contains a duplicate word")
        translation = item.get("translation")
        if not isinstance(translation, str) or not translation.strip():
            raise TranslationBatchError("translation must be non-empty")
        seen.append(word)
        result[word] = translation.strip()
    if set(seen) != set(requested_words) or len(seen) != len(requested_words):
        raise TranslationBatchError("response is missing requested words")
    return {word: result[word] for word in requested_words}


def incomplete_batch_diagnostics(requested: list[dict[str, Any]], payload: Any, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    requested_words = [r["word"] for r in requested]
    items = payload.get("translations") if isinstance(payload, dict) else payload
    returned_words = [item.get("word") for item in items if isinstance(item, dict)] if isinstance(items, list) else []
    return {
        **(metadata or {}),
        "requested_count": len(requested_words),
        "returned_count": len(returned_words),
        "missing_words": [word for word in requested_words if word not in returned_words],
        "extra_words": [word for word in returned_words if word not in requested_words],
    }


def translation_flags(record: dict[str, Any], translation: str) -> list[str]:
    flags: list[str] = []
    meaning = str(record.get("meaning") or "")
    if translation.strip().lower() == meaning.strip().lower():
        flags.append("identical_to_english")
    if re.search(r"```|^\s*[-*] |\*\*|#{1,6}\s", translation, re.MULTILINE):
        flags.append("unexpected_markdown")
    if len(translation) > 120:
        flags.append("too_long")
    vietnamese_marks = re.search(r"[ăâđêôơưàáảãạằắẳẵặầấẩẫậèéẻẽẹềếểễệìíỉĩịòóỏõọồốổỗộờớởỡợùúủũụừứửữựỳýỷỹỵ]", translation.lower())
    english_markers = {"a", "an", "and", "as", "at", "be", "before", "china", "class", "company", "down", "everything", "front", "he", "high", "middle", "now", "one", "person", "school", "side", "son", "study", "taxi", "the", "they", "thing", "today", "up", "what", "when", "whole", "you"}
    translation_words = re.findall(r"[A-Za-z]+", translation.lower())
    if not vietnamese_marks and translation_words and any(word in english_markers for word in translation_words):
        flags.append("mostly_english")
    pos = str(record.get("part_of_speech") or "")
    if pos == "unknown":
        flags.append("pos_unknown")
    if meaning.count(";") + meaning.count(",") + meaning.count("/") >= 4:
        flags.append("many_senses")
    source_senses = [part.strip() for part in re.split(r"[;/]", meaning) if part.strip()]
    translated_senses = [part.strip() for part in translation.split(";") if part.strip()]
    if len(source_senses) >= 3 and len(translated_senses) == 1:
        flags.append("semantically_short")
    if any(token in meaning.lower() for token in ("idiom", "chengyu", "in one breath", "without stopping")):
        flags.append("idiom_review")
    literal_pairs = {"一一": "một một", "一口气": "cả một lần", "一定": "định", "一旦": "khi", "一块儿": "một khối"}
    if literal_pairs.get(record.get("word")) == translation.strip().lower():
        flags.append("suspiciously_literal")
    if re.search(r"\b(person|place|surname|proper noun)\b", meaning, re.I):
        flags.append("proper_name_review")
    if pos.lower() in {"particle", "measure word", "classifier", "pronoun", "preposition"}:
        flags.append("function_word_review")
    unsupported_hints = {
        "hai mặt": ("one side", "either side", "on the one hand", "on the other hand"),
        "một khi": ("once", "in case", "as soon as"),
        "đầu tiên": ("first",),
        "thứ hai": ("second",),
        "từ chối": ("decline",),
        "đạt": ("arrive at", "decision", "conclusion"),
        "bác sĩ": ("doctor",),
    }
    meaning_lower = meaning.lower()
    if any(phrase in translation.lower() and not any(source_hint in meaning_lower for source_hint in source_hints) for phrase, source_hints in unsupported_hints.items()):
        flags.append("unsupported_sense_review")
    return flags


RISK_FLAGS = {
    "many_senses",
    "semantically_short",
    "function_word_review",
    "unsupported_sense_review",
    "too_long",
    "proper_name_review",
    "idiom_review",
    "suspiciously_literal",
    "mostly_english",
    "unexpected_markdown",
    "identical_to_english",
    "pos_unknown",
}


def classify_translation(record: dict[str, Any], flags: list[str]) -> str:
    """Classify a successful translation without changing its content."""
    return "REVIEW_REQUIRED" if RISK_FLAGS.intersection(flags) else "AUTO_ACCEPT"


def _is_daily_quota_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return ("429" in text or "rate_limit" in text or "rate limit" in text) and any(
        token in text for token in ("daily", "tpm", "tpd", "quota", "token")
    )


def _exception_chain(exc: BaseException) -> list[BaseException]:
    chain: list[BaseException] = []
    current: BaseException | None = exc
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        chain.append(current)
        current = current.__cause__ or current.__context__
    return chain


def is_provider_connection_error(exc: BaseException) -> bool:
    """Return true only for failures that occurred before an HTTP response."""
    if getattr(exc, "status_code", None) is not None:
        return False
    connection_types = {
        "APIConnectionError",
        "ConnectError",
        "ConnectTimeout",
        "ConnectionError",
        "TimeoutException",
    }
    for item in _exception_chain(exc):
        text = str(item).lower()
        if type(item).__name__ in connection_types:
            return True
        if any(marker in text for marker in ("winerror 10013", "connection error", "failed to establish a new connection", "connection refused")):
            return True
    return False


def _failure_is_temporary_connection(failure: dict[str, Any]) -> bool:
    text = str(failure.get("error", "")).lower()
    return any(marker in text for marker in ("connection error", "winerror 10013", "connecterror", "apiconnectionerror", "connection refused"))


def _write_full_artifacts(output_dir: Path, eligible: list[dict[str, Any]], cache: dict[str, Any], qa: dict[str, Any], failures: list[dict[str, Any]], metrics: dict[str, Any]) -> None:
    auto_accept = {word: value for word, value in cache.items() if not qa.get(word, {}).get("flags")}
    review_required = {word: value for word, value in cache.items() if qa.get(word, {}).get("flags")}
    (output_dir / "auto_accept.json").write_text(json.dumps(dict(sorted(auto_accept.items())), ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "review_required.json").write_text(json.dumps(dict(sorted(review_required.items())), ensure_ascii=False, indent=2), encoding="utf-8")
    by_level: dict[str, int] = {}
    for record in cache.values():
        level = str(record.get("level_code", ""))
        by_level[level] = by_level.get(level, 0) + 1
    flags = {}
    for item in qa.values():
        for flag in item.get("flags", []):
            flags[flag] = flags.get(flag, 0) + 1
    report = {
        "requested_count": len(eligible),
        "translated_count": len(cache),
        "remaining_count": max(0, len(eligible) - len(cache)),
        "failed_count": len({word for failure in failures for word in failure.get("words", [])}),
        "auto_accept_count": len(auto_accept),
        "review_required_count": len(review_required),
        "per_level_translated_counts": dict(sorted(by_level.items())),
        "qa_flag_distribution": dict(sorted(flags.items())),
        **metrics,
    }
    (output_dir / "translation_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def deferred_records(records: list[dict[str, Any]], missing_words: set[str], normalization_words: set[str], ambiguity: dict[str, Any]) -> list[dict[str, Any]]:
    output = []
    for record in sorted(records, key=lambda r: r.get("word", "")):
        word = record.get("word")
        if not word or (word not in missing_words and word not in normalization_words):
            continue
        output.append({
            "word": word,
            "level_code": record.get("level_code"),
            "ipa": record.get("ipa"),
            "part_of_speech": record.get("part_of_speech"),
            "candidate_meanings": ambiguity.get(word, {}).get("candidate_glosses", []),
            "reason": "normalization_review" if word in normalization_words else "missing_or_ambiguous_meaning",
        })
    return output


def current_deferred_records(
    records: list[dict[str, Any]],
    eligible: list[dict[str, Any]],
    normalization_words: set[str],
    ambiguity: dict[str, Any],
) -> list[dict[str, Any]]:
    """Describe only records excluded by the current eligibility policy."""
    eligible_words = {record["word"] for record in eligible}
    output = []
    for record in sorted(records, key=lambda item: item.get("word", "")):
        word = record.get("word")
        if word in eligible_words:
            continue
        if not word:
            reason = "missing_word"
        elif not record.get("level_code"):
            reason = "missing_level_code"
        elif not record.get("meaning"):
            reason = "missing_meaning"
        elif record.get("qa", {}).get("ambiguous", False):
            reason = "ambiguous_meaning"
        elif record.get("qa", {}).get("missing_meaning", False):
            reason = "missing_meaning"
        elif word in normalization_words:
            reason = "normalization_review"
        else:
            reason = "ineligible"
        output.append({
            "word": word,
            "level_code": record.get("level_code"),
            "ipa": record.get("ipa"),
            "part_of_speech": record.get("part_of_speech"),
            "candidate_meanings": ambiguity.get(word, {}).get("candidate_glosses", []),
            "reason": reason,
        })
    return output


def _prompt(batch: list[dict[str, Any]]) -> list[dict[str, str]]:
    payload = [{"word": r["word"], "pinyin": r.get("ipa"), "part_of_speech": r.get("part_of_speech"), "english_meaning": r["meaning"]} for r in batch]
    return [
        {"role": "system", "content": "Translate the supplied normalized English dictionary meaning into concise Vietnamese for each Chinese vocabulary item. The normalized English meaning is the semantic authority and absolute semantic boundary. Every Vietnamese sense must be directly justified by at least one supplied English meaning. Do not use external knowledge of the Chinese word to add meanings, dictionary senses, cultural meanings, or broader/narrower interpretations. Chinese word is lexical identity, POS is a disambiguation aid, and Pinyin is pronunciation only. Do not translate Chinese characters literally when the supplied meaning indicates a different lexical sense. Preserve important distinct senses in concise semicolon-separated Vietnamese; closely related synonyms may be collapsed, but do not silently drop grammatical, classifier, complement, idiomatic, or other distinct senses. For function words, preserve the grammatical function. For directional complements, measure words, classifiers, particles, and bound forms, use concise grammatical labels such as [bổ ngữ chỉ hướng], [lượng từ], [trợ từ], or [hình vị phụ thuộc] when useful. If a Vietnamese sense cannot be mapped back to a supplied English sense, omit it. Return only JSON object {translations:[{word,translation}]}; no markdown, explanations, examples, or invented senses. Return every word exactly once. Human QA will review the result."},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]


def openai_translate(batch: list[dict[str, Any]], settings: TranslationSettings) -> tuple[Any, dict[str, Any] | None]:
    # Groq requires the explicit strict Chat Completions JSON Schema contract
    # for this offline batch tool; production provider code remains untouched.
    from openai import OpenAI
    options: dict[str, Any] = {"api_key": settings.api_key, "timeout": settings.timeout_seconds, "max_retries": 0}
    if settings.base_url:
        options["base_url"] = settings.base_url
    response = OpenAI(**options).chat.completions.create(
        model=settings.model,
        messages=_prompt(batch),
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "hsk_vietnamese_translation_batch",
                "strict": True,
                "schema": TRANSLATION_JSON_SCHEMA,
            },
        },
        max_tokens=settings.max_output_tokens,
    )
    content = response.choices[0].message.content or ""
    usage = getattr(response, "usage", None)
    metadata = {
        "finish_reason": getattr(response.choices[0], "finish_reason", None),
        "prompt_tokens": getattr(usage, "prompt_tokens", None) if usage else None,
        "completion_tokens": getattr(usage, "completion_tokens", None) if usage else None,
        "total_tokens": getattr(usage, "total_tokens", None) if usage else None,
    }
    return json.loads(content), metadata


def gemini_translate(batch: list[dict[str, Any]], settings: TranslationSettings, transport: Any = None) -> tuple[Any, dict[str, Any] | None]:
    import httpx

    messages = _prompt(batch)
    endpoint = f"{(settings.base_url or '').rstrip('/')}/models/{settings.model}:generateContent"
    request_body = {
        "systemInstruction": {"parts": [{"text": messages[0]["content"]}]},
        "contents": [{"role": "user", "parts": [{"text": messages[1]["content"]}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseJsonSchema": TRANSLATION_JSON_SCHEMA,
            "maxOutputTokens": settings.max_output_tokens,
        },
    }
    client_options: dict[str, Any] = {"timeout": settings.timeout_seconds}
    if transport is not None:
        client_options["transport"] = transport
    try:
        with httpx.Client(**client_options) as client:
            response = client.post(endpoint, headers={"x-goog-api-key": settings.api_key}, json=request_body)
    except httpx.HTTPError:
        raise
    if response.status_code >= 400:
        try:
            error = response.json().get("error", {})
        except (ValueError, AttributeError):
            error = {}
        raise OfflineProviderError(
            str(error.get("message") or f"Gemini HTTP {response.status_code}"),
            status_code=response.status_code,
            code=str(error.get("status") or error.get("code") or "") or None,
            retry_after=response.headers.get("retry-after"),
        )
    data = response.json()
    try:
        candidate = data["candidates"][0]
        content = "".join(part.get("text", "") for part in candidate["content"]["parts"])
    except (KeyError, IndexError, TypeError) as exc:
        raise TranslationBatchError("Gemini response is missing structured content") from exc
    usage = data.get("usageMetadata", {})
    metadata = {
        "finish_reason": candidate.get("finishReason"),
        "prompt_tokens": usage.get("promptTokenCount"),
        "completion_tokens": usage.get("candidatesTokenCount"),
        "total_tokens": usage.get("totalTokenCount"),
    }
    try:
        return json.loads(content), metadata
    except json.JSONDecodeError as exc:
        raise TranslationBatchError("Gemini response content is not valid JSON") from exc


def translate_batch(batch: list[dict[str, Any]], settings: TranslationSettings) -> tuple[Any, dict[str, Any] | None]:
    if settings.provider == "gemini":
        return gemini_translate(batch, settings)
    return openai_translate(batch, settings)


def run_pipeline(input_path: Path, output_dir: Path, normalization_path: Path, missing_path: Path, ambiguity_path: Path, batch_size: int = 5, pilot_count: int | None = None, translator: Callable[[list[dict[str, Any]]], tuple[Any, Any]] | None = None, retries: int = 2, connection_failure_threshold: int = 3, provider: str | None = None) -> dict[str, Any]:
    if connection_failure_threshold < 1:
        raise ValueError("connection_failure_threshold must be positive")
    records = load_json(input_path)
    normalization = load_json(normalization_path)
    missing = load_json(missing_path)
    ambiguity_rows = load_json(ambiguity_path)
    normalization_words = {r.get("word", r.get("source_word")) for r in normalization}
    normalization_words.discard(None)
    missing_words = {r["word"] for r in missing}
    ambiguity = {r.get("word"): r for r in ambiguity_rows if r.get("word")}
    eligible = select_eligible_records(records, normalization_words)
    actual_deferred = current_deferred_records(records, eligible, normalization_words, ambiguity)
    eligible_words = {record["word"] for record in eligible}
    legacy_reference_words = missing_words | normalization_words
    stale_legacy_deferred_reference_count = len(eligible_words & legacy_reference_words)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "deferred_records.json").write_text(json.dumps(actual_deferred, ensure_ascii=False, indent=2), encoding="utf-8")
    cache_path = output_dir / "translations.json"
    cache = load_json(cache_path) if cache_path.exists() else {}
    if isinstance(cache, list):
        cache = {r["word"]: r for r in cache}
    work = [r for r in eligible if r["word"] not in cache]
    if pilot_count is not None:
        work = work[:pilot_count]
    batches = build_batches(work, batch_size)
    failures = []
    qa = load_json(output_dir / "translation_qa.json") if (output_dir / "translation_qa.json").exists() else {}
    usage_total = 0
    metrics: dict[str, Any] = {
        "provider": None,
        "model": None,
        "request_count": 0,
        "successful_batch_count": 0,
        "retry_count": 0,
        "http_429_count": 0,
        "connection_failure_count": 0,
        "schema_failure_count": 0,
        "quota_exhausted": False,
        "temporary_infrastructure_failure": False,
        "circuit_breaker_triggered": False,
        "consecutive_connection_failures": 0,
        "stop_reason": None,
        "deferred_count": len(actual_deferred),
        "stale_legacy_deferred_reference_count": stale_legacy_deferred_reference_count,
    }
    if not translator:
        settings = load_translation_settings(provider)
        metrics["provider"] = settings.provider
        metrics["model"] = settings.model
    else:
        settings = None
    (output_dir / "translation_failures.json").write_text(json.dumps(failures, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "translation_progress.json").write_text(json.dumps({"eligible_count": len(eligible), "cached": len(cache), "remaining": len(work), "translated_count": len(cache), "failed_batches": 0}, indent=2), encoding="utf-8")
    for index, batch in enumerate(batches):
        last_error = None
        last_diagnostics: dict[str, Any] = {}
        payload: Any = None
        usage: Any = None
        for attempt in range(retries + 1):
            try:
                metrics["request_count"] += 1
                payload, usage = (translator(batch) if translator else translate_batch(batch, settings))
                translations = validate_translation_batch(batch, payload)
                for record in batch:
                    word = record["word"]
                    provenance = {
                        "vietnamese_translation": "Mascot controlled translation pipeline",
                        "vietnamese_translation_provider": settings.provider if settings else "test",
                        "vietnamese_translation_model": settings.model if settings else "test",
                    }
                    cache[word] = {**record, "translation": translations[word], "sources": {**record.get("sources", {}), **provenance}}
                    qa[word] = {"word": word, "flags": translation_flags(record, translations[word])}
                if usage is not None:
                    usage_total += int(getattr(usage, "total_tokens", 0) or (usage.get("total_tokens", 0) if isinstance(usage, dict) else 0))
                metrics["successful_batch_count"] += 1
                metrics["consecutive_connection_failures"] = 0
                break
            except Exception as exc:
                last_error = str(exc)
                status_code = getattr(exc, "status_code", None)
                if status_code == 429 or (type(exc).__name__ in {"RateLimitError", "APIStatusError"} and ("429" in last_error or "rate_limit" in last_error.lower())):
                    metrics["http_429_count"] += 1
                connection_failure = is_provider_connection_error(exc)
                if connection_failure:
                    metrics["connection_failure_count"] += 1
                    metrics["consecutive_connection_failures"] += 1
                    if metrics["consecutive_connection_failures"] >= connection_failure_threshold:
                        metrics["temporary_infrastructure_failure"] = True
                        metrics["circuit_breaker_triggered"] = True
                        metrics["stop_reason"] = "provider_connection_unavailable"
                if isinstance(exc, TranslationBatchError) or "json_validate" in last_error.lower():
                    metrics["schema_failure_count"] += 1
                if payload is not None:
                    last_diagnostics = incomplete_batch_diagnostics(batch, payload, usage if isinstance(usage, dict) else None)
                details = getattr(exc, "details", None)
                if details:
                        last_error = json.dumps({"type": type(exc).__name__, **details}, ensure_ascii=False)
                if status_code == 429 or _is_daily_quota_error(exc):
                    metrics["quota_exhausted"] = True
                    metrics["stop_reason"] = "daily_quota_exhausted"
                    break
                if metrics["circuit_breaker_triggered"]:
                    break
                if not connection_failure:
                    metrics["consecutive_connection_failures"] = 0
                if attempt < retries:
                    metrics["retry_count"] += 1
                    time.sleep(0.5 * (2 ** attempt))
        else:
            failures.append({"batch_index": index, "words": [r["word"] for r in batch], "error": last_error, **last_diagnostics})
        cache_path.write_text(json.dumps(dict(sorted(cache.items())), ensure_ascii=False, indent=2), encoding="utf-8")
        (output_dir / "translation_qa.json").write_text(json.dumps(dict(sorted(qa.items())), ensure_ascii=False, indent=2), encoding="utf-8")
        (output_dir / "translation_failures.json").write_text(json.dumps(failures, ensure_ascii=False, indent=2), encoding="utf-8")
        (output_dir / "translation_progress.json").write_text(json.dumps({"eligible_count": len(eligible), "cached": len(cache), "remaining": max(0, len(eligible) - len(cache)), "processed_this_run": min(len(work), (index + 1) * batch_size), "translated_count": len(cache), "record_translation_failures": len(failures), "temporary_infrastructure_failure": metrics["temporary_infrastructure_failure"], "circuit_breaker_triggered": metrics["circuit_breaker_triggered"], "consecutive_connection_failures": metrics["consecutive_connection_failures"], "stop_reason": metrics["stop_reason"]}, indent=2), encoding="utf-8")
        _write_full_artifacts(output_dir, eligible, cache, qa, failures, {**metrics, "usage_total_tokens": usage_total})
        if metrics["quota_exhausted"] or metrics["circuit_breaker_triggered"]:
            break
    _write_full_artifacts(output_dir, eligible, cache, qa, failures, {**metrics, "usage_total_tokens": usage_total})
    return {"eligible_count": len(eligible), "deferred_count": len(actual_deferred), "stale_legacy_deferred_reference_count": stale_legacy_deferred_reference_count, "cached_count": len(cache), "remaining_count": max(0, len(eligible) - len(cache)), "pilot_count": len(work), "translated_count": len(cache), "failed_batches": len(failures), "usage_total_tokens": usage_total, **metrics}


def reconcile_temporary_failures(input_path: Path, output_dir: Path, normalization_path: Path) -> dict[str, Any]:
    """Remove legacy connection-only failures while preserving successful cache."""
    records = load_json(input_path)
    normalization = load_json(normalization_path)
    blocked = {r.get("word", r.get("source_word")) for r in normalization}
    blocked.discard(None)
    eligible = select_eligible_records(records, blocked)
    cache_path = output_dir / "translations.json"
    cache = load_json(cache_path) if cache_path.exists() else {}
    if isinstance(cache, list):
        cache = {r["word"]: r for r in cache}
    qa_path = output_dir / "translation_qa.json"
    qa = load_json(qa_path) if qa_path.exists() else {}
    failures_path = output_dir / "translation_failures.json"
    failures = load_json(failures_path) if failures_path.exists() else []
    temporary = [failure for failure in failures if _failure_is_temporary_connection(failure)]
    record_failures = [failure for failure in failures if not _failure_is_temporary_connection(failure)]
    failures_path.write_text(json.dumps(record_failures, ensure_ascii=False, indent=2), encoding="utf-8")
    cache_path.write_text(json.dumps(dict(sorted(cache.items())), ensure_ascii=False, indent=2), encoding="utf-8")
    qa_path.write_text(json.dumps(dict(sorted(qa.items())), ensure_ascii=False, indent=2), encoding="utf-8")
    temporary_words = {word for failure in temporary for word in failure.get("words", [])}
    metrics = {
        "provider": "groq",
        "model": "openai/gpt-oss-20b",
        "request_count": 0,
        "successful_batch_count": 0,
        "retry_count": 0,
        "http_429_count": 0,
        "connection_failure_count": 0,
        "schema_failure_count": 0,
        "quota_exhausted": False,
        "temporary_infrastructure_failure": False,
        "reconciled_temporary_failure_count": len(temporary_words),
        "circuit_breaker_triggered": False,
        "consecutive_connection_failures": 0,
        "stop_reason": "temporary_failures_reconciled",
        "usage_total_tokens": 0,
    }
    _write_full_artifacts(output_dir, eligible, cache, qa, record_failures, metrics)
    progress = {
        "eligible_count": len(eligible),
        "cached": len(cache),
        "remaining": max(0, len(eligible) - len(cache)),
        "record_translation_failures": len(record_failures),
        "reconciled_temporary_failure_count": len(temporary_words),
        "temporary_infrastructure_failure": False,
        "circuit_breaker_triggered": False,
        "consecutive_connection_failures": 0,
        "stop_reason": "temporary_failures_reconciled",
    }
    (output_dir / "translation_progress.json").write_text(json.dumps(progress, ensure_ascii=False, indent=2), encoding="utf-8")
    return progress


def write_pilot_comparison(old_path: Path, new_path: Path, records_path: Path, output_path: Path) -> None:
    old = load_json(old_path)
    new = load_json(new_path)
    records = {r["word"]: r for r in load_json(records_path)}
    words = list(new.keys())[:20]
    comparison = []
    for word in words:
        record = records[word]
        comparison.append({
            "word": word,
            "english_meaning": record.get("meaning"),
            "old_translation": old.get(word, {}).get("translation"),
            "new_translation": new[word].get("translation"),
            "qa_flags": load_json(new_path.parent / "translation_qa.json").get(word, {}).get("flags", []),
        })
    output_path.write_text(json.dumps(comparison, ensure_ascii=False, indent=2), encoding="utf-8")


def write_clean_pilot_comparison(old_dir: Path, new_dir: Path, records_path: Path, output_path: Path) -> None:
    """Compare the fixed clean pilot without mutating either pilot run."""
    records = {r["word"]: r for r in load_json(records_path)}
    old = load_json(old_dir / "translations.json") if (old_dir / "translations.json").exists() else {}
    new = load_json(new_dir / "translations.json") if (new_dir / "translations.json").exists() else {}
    old_qa = load_json(old_dir / "translation_qa.json") if (old_dir / "translation_qa.json").exists() else {}
    new_qa = load_json(new_dir / "translation_qa.json") if (new_dir / "translation_qa.json").exists() else {}
    comparison = []
    for record in [records[word] for word in sorted(records)]:
        word = record["word"]
        comparison.append({
            "word": word,
            "normalized_english_meaning": record.get("normalized_english_meaning", record.get("meaning")),
            "old_translation": old.get(word, {}).get("translation"),
            "new_translation": new.get(word, {}).get("translation"),
            "old_qa": old_qa.get(word, {}).get("flags", []),
            "new_qa": new_qa.get(word, {}).get("flags", []),
        })
    output_path.write_text(json.dumps(comparison, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_clean_pilot3_comparison(records_path: Path, pilot1_dir: Path, pilot2_dir: Path, pilot3_dir: Path, output_path: Path) -> None:
    records = {r["word"]: r for r in load_json(records_path)}

    def read_map(directory: Path, filename: str) -> dict[str, Any]:
        path = directory / filename
        return load_json(path) if path.exists() else {}

    pilot1 = read_map(pilot1_dir, "translations.json")
    pilot2 = read_map(pilot2_dir, "translations.json")
    pilot3 = read_map(pilot3_dir, "translations.json")
    pilot3_qa = read_map(pilot3_dir, "translation_qa.json")
    comparison = []
    for record in [records[word] for word in sorted(records)]:
        word = record["word"]
        comparison.append({
            "word": word,
            "normalized_english_meaning": record.get("normalized_english_meaning", record.get("meaning")),
            "pilot1_translation": pilot1.get(word, {}).get("translation"),
            "pilot2_translation": pilot2.get(word, {}).get("translation"),
            "pilot3_translation": pilot3.get(word, {}).get("translation"),
            "pilot3_qa": pilot3_qa.get(word, {}).get("flags", []),
        })
    output_path.write_text(json.dumps(comparison, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_clean_pilot3_comparison() -> dict[str, Any]:
    empty = CLEAN_PILOT_RECORDS.parent / "empty.json"
    result = run_pipeline(CLEAN_PILOT_RECORDS, CLEAN_PILOT3_DIR, empty, empty, empty, batch_size=5, pilot_count=30)
    write_clean_pilot3_comparison(CLEAN_PILOT_RECORDS, CLEAN_PILOT_OLD_DIR, CLEAN_PILOT2_DIR, CLEAN_PILOT3_DIR, CLEAN_PILOT3_DIR / "pilot_comparison.json")
    return result


def run_clean_pilot_comparison() -> dict[str, Any]:
    """Run only the preselected 30 clean records in an isolated directory."""
    empty = CLEAN_PILOT_RECORDS.parent / "empty.json"
    result = run_pipeline(
        CLEAN_PILOT_RECORDS,
        CLEAN_PILOT2_DIR,
        empty,
        empty,
        empty,
        batch_size=5,
        pilot_count=30,
    )
    write_clean_pilot_comparison(
        CLEAN_PILOT_OLD_DIR,
        CLEAN_PILOT2_DIR,
        CLEAN_PILOT_RECORDS,
        CLEAN_PILOT2_DIR / "pilot_comparison.json",
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path("tmp/hsk31_clean_catalog/clean_records.json"))
    parser.add_argument("--output-dir", type=Path, default=CLEAN_FULL_DIR)
    parser.add_argument("--normalization-input", type=Path, default=Path("tmp/hsk31_audit/normalization_review.json"))
    parser.add_argument("--missing-input", type=Path, default=Path("tmp/hsk31_audit/missing_meaning.json"))
    parser.add_argument("--ambiguity-input", type=Path, default=Path("tmp/hsk31_audit/ambiguous_cedict.json"))
    parser.add_argument("--batch-size", type=int, default=5)
    parser.add_argument("--pilot-count", type=int)
    parser.add_argument("--compare-old", type=Path)
    parser.add_argument("--records", type=Path, default=Path("tmp/hsk31_audit/canonical_words.json"))
    parser.add_argument("--pilot-comparison", action="store_true", help="Translate only the fixed clean 30-record pilot into an isolated pilot2 directory")
    parser.add_argument("--pilot3-comparison", action="store_true", help="Translate only the same fixed clean 30-record pilot into an isolated pilot3 directory")
    parser.add_argument("--connection-failure-threshold", type=int, default=3)
    parser.add_argument("--provider", choices=("groq", "gemini"))
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--reconcile-temporary-failures", action="store_true")
    args = parser.parse_args()
    if args.reconcile_temporary_failures:
        result = reconcile_temporary_failures(args.input, args.output_dir, args.normalization_input)
        print(json.dumps(result, ensure_ascii=False))
        return
    settings = load_translation_settings(args.provider)
    if args.pilot3_comparison:
        result = run_clean_pilot3_comparison()
    elif args.pilot_comparison:
        result = run_clean_pilot_comparison()
    else:
        result = run_pipeline(args.input, args.output_dir, args.normalization_input, args.missing_input, args.ambiguity_input, args.batch_size, args.pilot_count, retries=args.retries, connection_failure_threshold=args.connection_failure_threshold, provider=args.provider)
    print(json.dumps({"provider": settings.provider, "model": settings.model, **result}, ensure_ascii=False))
    if args.compare_old:
        write_pilot_comparison(args.compare_old, args.output_dir / "translations.json", args.records, args.output_dir / "pilot_comparison.json")


if __name__ == "__main__":
    main()
