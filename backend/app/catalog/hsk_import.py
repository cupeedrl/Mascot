"""Validate and load an HSK catalog release into the normalized catalog.

A dataset directory contains:

* ``manifest.json``: release metadata, the declared SHA-256 of the source file,
  data origin, the four permission decisions with evidence, and level scope.
* the source file named by the manifest, in CTI API shape
  (``{"data": {"records": [...]}}``) or as a bare list of records with the
  CTI fields ``id``, ``sort``, ``word``, ``pinyin``, ``cixing``, ``levelName``.
* an optional review file with explicit, human-reviewed lexical entries,
  readings, senses, POS, variants, examples and source mappings.

The importer never guesses. Ambiguous or invalid rows are reported for
humans; source records without an approved mapping stay "awaiting review".
Releases are always created as ``draft``. ``vocabularies`` is never touched.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.models.hsk_catalog import (
    CATALOG_LEVEL_CODES,
    DATA_ORIGINS,
    MAPPING_REVIEW_STATUSES,
    PERMISSION_STATUSES,
    POS_CODES,
    POS_ORIGINS,
    SENSE_REVIEW_STATUSES,
    SENSE_STATUSES,
    VARIANT_TYPES,
)

PERMISSION_KEYS = ("storage", "transformation", "redistribution", "publication")
SCOPE_LEVELS = ("HSK1", "HSK2", "HSK3", "HSK4", "HSK5", "HSK6")
LEVEL_NAMES = {
    "一级": "HSK1",
    "二级": "HSK2",
    "三级": "HSK3",
    "四级": "HSK4",
    "五级": "HSK5",
    "六级": "HSK6",
    "七-九级": "HSK7-9",
}
_LEVEL_PART = re.compile(r"（([^（）]+)）")
_HOMOGRAPH_SUFFIX = re.compile(r"^(.+?)(\d+)$")
# Flags that block automatic interpretation; a human mapping is required.
AMBIGUITY_FLAGS = frozenset(
    {"multiple_readings", "homograph_suffix", "repeated_surface", "pos_parenthesized"}
)


class DatasetError(ValueError):
    """The dataset as a whole is unusable (manifest/hash/shape)."""


class ReleaseStateError(RuntimeError):
    """The target release cannot be modified or transitioned."""


# --------------------------------------------------------------------------- helpers


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_record_hash(record: dict[str, Any]) -> str:
    canonical = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256_bytes(canonical.encode("utf-8"))


def toneless_pinyin(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value.casefold())
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.sub(r"[^a-z]", "", stripped)


def normalize_reading(value: str) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFC", value.strip()).casefold())


def source_readings(raw_pinyin: str) -> list[str]:
    return [part.strip() for part in raw_pinyin.split("/") if part.strip()]


def parse_level_name(level_name: str) -> list[str]:
    """Return ``[primary, *annotations]`` level codes or raise ``ValueError``."""
    text = level_name.strip()
    base = text.split("（", 1)[0]
    rest = text[len(base):]
    annotations = _LEVEL_PART.findall(rest)
    if _LEVEL_PART.sub("", rest).strip():
        raise ValueError("unparseable_level_name")
    codes = []
    for name in [base, *annotations]:
        code = LEVEL_NAMES.get(name.strip())
        if code is None:
            raise ValueError("unknown_level")
        if code in codes:
            raise ValueError("repeated_level")
        codes.append(code)
    return codes


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


# --------------------------------------------------------------------------- dataset


@dataclass
class Dataset:
    directory: Path
    manifest: dict[str, Any]
    source_sha256: str
    records: list[Any]
    review: dict[str, Any] | None


def load_dataset(directory: Path) -> Dataset:
    manifest_path = directory / "manifest.json"
    if not manifest_path.is_file():
        raise DatasetError("manifest.json not found")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    _validate_manifest(manifest)

    source_path = directory / manifest["source_file"]
    source_bytes = source_path.read_bytes()
    actual = sha256_bytes(source_bytes)
    if actual != manifest["source_sha256"]:
        raise DatasetError(
            f"source SHA-256 mismatch: manifest {manifest['source_sha256']}, file {actual}"
        )
    payload = json.loads(source_bytes.decode("utf-8"))
    if isinstance(payload, dict):
        records = (payload.get("data") or {}).get("records")
    else:
        records = payload
    if not isinstance(records, list):
        raise DatasetError("source file has no record list")

    review = None
    if manifest.get("review_file"):
        review = json.loads((directory / manifest["review_file"]).read_text(encoding="utf-8"))
        if not isinstance(review, dict):
            raise DatasetError("review file must be a JSON object")
    return Dataset(directory, manifest, actual, records, review)


def _validate_manifest(manifest: Any) -> None:
    if not isinstance(manifest, dict):
        raise DatasetError("manifest must be an object")
    required = (
        "release_code",
        "title",
        "learning_track_code",
        "language_code",
        "source_name",
        "source_file",
        "source_sha256",
        "source_record_id_type",
        "data_origin",
        "permissions",
    )
    missing = [key for key in required if not manifest.get(key)]
    if missing:
        raise DatasetError(f"manifest missing: {', '.join(missing)}")
    if manifest["data_origin"] not in DATA_ORIGINS:
        raise DatasetError("manifest data_origin is invalid")
    if not re.fullmatch(r"[0-9a-f]{64}", manifest["source_sha256"]):
        raise DatasetError("manifest source_sha256 must be 64 lowercase hex characters")
    permissions = manifest["permissions"]
    for key in PERMISSION_KEYS:
        entry = permissions.get(key) if isinstance(permissions, dict) else None
        if not isinstance(entry, dict) or entry.get("status") not in PERMISSION_STATUSES:
            raise DatasetError(f"manifest permission '{key}' needs a valid status")
        if entry["status"] == "approved" and not entry.get("evidence"):
            raise DatasetError(f"permission '{key}' is approved without evidence")
    scope = manifest.get("level_scope", list(SCOPE_LEVELS))
    if not scope or any(level not in CATALOG_LEVEL_CODES for level in scope):
        raise DatasetError("manifest level_scope is invalid")


# --------------------------------------------------------------------------- validation


@dataclass
class SourceRow:
    record_id: str
    serial: int | None
    raw_word: str
    raw_pinyin: str
    raw_pos: str | None
    raw_level_name: str
    levels: list[str]
    payload: dict[str, Any]
    payload_sha256: str
    flags: list[str] = field(default_factory=list)

    @property
    def primary_level(self) -> str:
        return self.levels[0]


@dataclass
class Issue:
    kind: str  # rejected | duplicate | review_rejected | review_duplicate
    reason: str
    record_id: str | None = None
    serial: int | None = None
    level: str | None = None
    detail: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if v is not None}


@dataclass
class ValidationResult:
    manifest: dict[str, Any]
    source_sha256: str
    rows: list[SourceRow]
    issues: list[Issue]
    serial_gaps: list[int]
    lexical_entries: list[dict[str, Any]]
    mappings: list[dict[str, Any]]
    report: dict[str, Any]
    topics: list[dict[str, Any]] = field(default_factory=list)
    entry_topics: list[dict[str, Any]] = field(default_factory=list)


def validate_dataset(dataset: Dataset) -> ValidationResult:
    manifest = dataset.manifest
    scope = tuple(manifest.get("level_scope", SCOPE_LEVELS))
    issues: list[Issue] = []
    rows: list[SourceRow] = []
    seen_ids: set[str] = set()
    seen_serials: set[int] = set()
    all_serials: list[int] = []
    level_of_serial: dict[int, str] = {}
    excluded_by_level: Counter[str] = Counter()

    for position, record in enumerate(dataset.records):
        if not isinstance(record, dict):
            issues.append(Issue("rejected", "record_not_object", detail=f"position {position}"))
            continue
        raw_id = record.get("id")
        if raw_id is None or isinstance(raw_id, bool) or not str(raw_id).strip():
            issues.append(Issue("rejected", "missing_record_id", detail=f"position {position}"))
            continue
        record_id = str(raw_id).strip()
        serial_value = record.get("sort")
        serial: int | None = None
        if serial_value is not None:
            if not _is_int(serial_value) or serial_value <= 0:
                issues.append(Issue("rejected", "invalid_serial", record_id))
                continue
            serial = serial_value
            all_serials.append(serial)
        try:
            levels = parse_level_name(str(record.get("levelName") or ""))
        except ValueError as exc:
            issues.append(Issue("rejected", str(exc), record_id, serial))
            continue
        if serial is not None:
            level_of_serial.setdefault(serial, levels[0])
        if record_id in seen_ids:
            issues.append(Issue("duplicate", "duplicate_record_id", record_id, serial, levels[0]))
            continue
        if serial is not None and serial in seen_serials:
            issues.append(Issue("duplicate", "duplicate_serial", record_id, serial, levels[0]))
            continue
        seen_ids.add(record_id)
        if serial is not None:
            seen_serials.add(serial)

        if levels[0] not in scope:
            excluded_by_level[levels[0]] += 1
            continue
        word = record.get("word")
        pinyin = record.get("pinyin")
        if not isinstance(word, str) or not word.strip():
            issues.append(Issue("rejected", "missing_word", record_id, serial, levels[0]))
            continue
        if not isinstance(pinyin, str) or not pinyin.strip():
            issues.append(Issue("rejected", "missing_pinyin", record_id, serial, levels[0]))
            continue

        flags: list[str] = []
        if "cixing" not in record or record.get("cixing") is None:
            raw_pos = None
            flags.append("pos_absent")
        elif not str(record["cixing"]).strip():
            raw_pos = None
            flags.append("pos_blank")
        else:
            raw_pos = str(record["cixing"]).strip()
            if "（" in raw_pos or "(" in raw_pos:
                flags.append("pos_parenthesized")
        if len(source_readings(pinyin)) > 1:
            flags.append("multiple_readings")
        if _HOMOGRAPH_SUFFIX.match(word.strip()):
            flags.append("homograph_suffix")
        if serial is None:
            flags.append("serial_absent")
        rows.append(
            SourceRow(
                record_id=record_id,
                serial=serial,
                raw_word=word.strip(),
                raw_pinyin=pinyin.strip(),
                raw_pos=raw_pos,
                raw_level_name=str(record["levelName"]).strip(),
                levels=levels,
                payload=record,
                payload_sha256=canonical_record_hash(record),
                flags=flags,
            )
        )

    surface_counts = Counter(row.raw_word for row in rows)
    for row in rows:
        if surface_counts[row.raw_word] > 1:
            row.flags.append("repeated_surface")

    serial_gaps: list[int] = []
    if all_serials:
        present = set(all_serials)
        serial_gaps = [s for s in range(min(present), max(present) + 1) if s not in present]

    lexical_entries, mappings = _validate_review(dataset.review, rows, issues)
    topics, entry_topics = _validate_topics(dataset.review, rows, issues, scope)
    report = _build_report(
        manifest, dataset.source_sha256, rows, issues, serial_gaps, level_of_serial,
        excluded_by_level, mappings, scope, len(dataset.records), entry_topics,
    )
    report["review"]["topics_accepted"] = len(topics)
    report["review"]["entry_topics_accepted"] = len(entry_topics)
    return ValidationResult(
        manifest, dataset.source_sha256, rows, issues, serial_gaps,
        lexical_entries, mappings, report, topics, entry_topics,
    )


TOPIC_SOURCES = ("official_syllabus", "mascot")
ENTRY_TOPIC_ORIGINS = ("ai_suggested", "editorial")
ENTRY_TOPIC_STATUSES = ("proposed", "approved", "rejected")


def topic_key(path: list[str]) -> str:
    return "/".join(part.strip() for part in path)


def _validate_topics(
    review: dict[str, Any] | None,
    rows: list[SourceRow],
    issues: list[Issue],
    scope: tuple[str, ...],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Validate the per-level topic tree and word-to-topic assignments.

    A word is assigned only to topics of its primary level. Unknown topics,
    out-of-scope levels and wrong levels are rejected for human review.
    """
    if not review:
        return [], []
    accepted: dict[tuple[str, str], dict[str, Any]] = {}
    for item in review.get("topics", []):
        level = item.get("level_code")
        path = [str(part).strip() for part in item.get("path") or []]
        key = topic_key(path)
        reason = None
        if level not in scope:
            reason = "topic_level_out_of_scope"
        elif not 1 <= len(path) <= 3 or not all(path):
            reason = "topic_invalid_path"
        elif len(path) > 1 and (level, topic_key(path[:-1])) not in accepted:
            reason = "topic_parent_missing"
        elif (level, key) in accepted:
            reason = "duplicate_topic"
        elif item.get("source", "official_syllabus") not in TOPIC_SOURCES:
            reason = "topic_invalid_source"
        if reason:
            issues.append(
                Issue("review_rejected", reason, level=level if level in scope else None, detail=key)
            )
            continue
        accepted[(level, key)] = {**item, "path": path, "key": key}

    rows_by_id = {row.record_id: row for row in rows}
    seen: set[tuple[str, str]] = set()
    assignments: list[dict[str, Any]] = []
    for item in review.get("entry_topics", []):
        record_id = str(item.get("source_record_id") or "").strip()
        row = rows_by_id.get(record_id)
        path = [str(part).strip() for part in item.get("topic_path") or []]
        key = topic_key(path)
        level = row.primary_level if row else None
        reason = None
        if row is None:
            reason = "entry_topic_unknown_source"
        elif item.get("level_code", level) != level:
            reason = "entry_topic_not_primary_level"
        elif (level, key) not in accepted:
            reason = "entry_topic_unknown_topic"
        elif item.get("origin", "ai_suggested") not in ENTRY_TOPIC_ORIGINS:
            reason = "entry_topic_invalid_origin"
        elif item.get("review_status", "proposed") not in ENTRY_TOPIC_STATUSES:
            reason = "entry_topic_invalid_review_status"
        if reason:
            issues.append(Issue("review_rejected", reason, record_id or None, level=level, detail=key))
            continue
        if (record_id, key) in seen:
            issues.append(Issue("review_duplicate", "duplicate_entry_topic", record_id, level=level))
            continue
        seen.add((record_id, key))
        assignments.append({**item, "source_record_id": record_id, "level_code": level, "key": key})
    return list(accepted.values()), assignments


def _validate_review(
    review: dict[str, Any] | None, rows: list[SourceRow], issues: list[Issue]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not review:
        return [], []
    rows_by_id = {row.record_id: row for row in rows}
    lexical_by_key: dict[str, dict[str, Any]] = {}

    for item in review.get("lexical_entries", []):
        key = str(item.get("lexical_key") or "").strip()
        reason = _lexical_problem(item, lexical_by_key)
        if reason:
            issues.append(Issue("review_rejected", reason, detail=f"lexical {key or '?'}"))
            continue
        lexical_by_key[key] = item

    accepted_mappings: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for item in review.get("mappings", []):
        record_id = str(item.get("source_record_id") or "").strip()
        row = rows_by_id.get(record_id)
        level = row.primary_level if row else None
        lexical = lexical_by_key.get(str(item.get("lexical_key") or "").strip())
        reason = None
        if row is None:
            reason = "mapping_unknown_or_unaccepted_source"
        elif lexical is None:
            reason = "mapping_unknown_lexical_entry"
        elif item.get("review_status", "proposed") not in MAPPING_REVIEW_STATUSES:
            reason = "mapping_invalid_review_status"
        else:
            reason = _mapping_problem(item, lexical, row)
        if reason:
            issues.append(Issue("review_rejected", reason, record_id or None, level=level))
            continue
        identity = (
            record_id,
            lexical["lexical_key"],
            item.get("pronunciation"),
            item.get("sense_key"),
        )
        if identity in seen:
            issues.append(Issue("review_duplicate", "duplicate_mapping", record_id, level=level))
            continue
        seen.add(identity)
        accepted_mappings.append(item)
    return list(lexical_by_key.values()), accepted_mappings


def _lexical_problem(item: dict[str, Any], existing: dict[str, Any]) -> str | None:
    key = str(item.get("lexical_key") or "").strip()
    if not key or not str(item.get("headword") or "").strip():
        return "lexical_missing_key_or_headword"
    if key in existing:
        return "duplicate_lexical_key"
    readings = [str(p.get("pinyin") or "").strip() for p in item.get("pronunciations", [])]
    if any(not reading for reading in readings) or len(set(readings)) != len(readings):
        return "lexical_invalid_pronunciations"
    sense_keys = set()
    for sense in item.get("senses", []):
        sense_key = str(sense.get("sense_key") or "").strip()
        if not sense_key or sense_key in sense_keys:
            return "sense_missing_or_duplicate_key"
        sense_keys.add(sense_key)
        if not (sense.get("gloss_en") or "").strip() and not (sense.get("gloss_vi") or "").strip():
            return "sense_without_gloss"
        if not str(sense.get("gloss_source") or "").strip():
            return "sense_without_gloss_source"
        if sense.get("review_status", "draft") not in SENSE_REVIEW_STATUSES:
            return "sense_invalid_review_status"
        if sense.get("status", "active") not in SENSE_STATUSES:
            return "sense_invalid_status"
        codes = [pos.get("code") for pos in sense.get("pos", [])]
        if len(set(codes)) != len(codes):
            return "sense_duplicate_pos"
        for pos in sense.get("pos", []):
            if pos.get("code") not in POS_CODES or pos.get("origin") not in POS_ORIGINS:
                return "sense_invalid_pos"
        for reading in sense.get("pronunciations", []):
            if reading not in readings:
                return "sense_pronunciation_not_in_lexical_entry"
        orders = [example.get("order", index) for index, example in enumerate(sense.get("examples", []))]
        if len(set(orders)) != len(orders):
            return "example_duplicate_order"
        for example in sense.get("examples", []):
            if not str(example.get("text_zh") or "").strip() or not str(example.get("source") or "").strip():
                return "example_missing_text_or_source"
    for variant in item.get("variants", []):
        if not str(variant.get("form") or "").strip() or variant.get("type") not in VARIANT_TYPES:
            return "variant_invalid"
        if not str(variant.get("source") or "").strip():
            return "variant_without_source"
        if variant.get("pronunciation") and variant["pronunciation"] not in readings:
            return "variant_pronunciation_not_in_lexical_entry"
    return None


def _mapping_problem(item: dict[str, Any], lexical: dict[str, Any], row: SourceRow) -> str | None:
    readings = [p["pinyin"].strip() for p in lexical.get("pronunciations", [])]
    senses = {s["sense_key"]: s for s in lexical.get("senses", [])}
    reading = item.get("pronunciation")
    sense_key = item.get("sense_key")
    source = {normalize_reading(r) for r in source_readings(row.raw_pinyin)}
    if reading is not None:
        if reading not in readings:
            return "mapping_pronunciation_not_in_lexical_entry"
        if normalize_reading(reading) not in source:
            return "mapping_pronunciation_not_in_source"
    if sense_key is not None:
        sense = senses.get(sense_key)
        if sense is None:
            return "mapping_sense_not_in_lexical_entry"
        linked = sense.get("pronunciations", [])
        if reading is not None and reading not in linked:
            return "mapping_sense_pronunciation_not_linked"
        if reading is None and any(normalize_reading(r) not in source for r in linked):
            return "mapping_sense_reading_not_in_source"
    return None


def _build_report(
    manifest, source_sha256, rows, issues, serial_gaps, level_of_serial,
    excluded_by_level, mappings, scope, records_in_file, entry_topics=(),
) -> dict[str, Any]:
    approved_records = {
        str(m["source_record_id"]) for m in mappings if m.get("review_status") == "approved"
    }
    gate_open = manifest["data_origin"] != "third_party" or all(
        manifest["permissions"][key]["status"] == "approved" for key in PERMISSION_KEYS
    )
    with_topic = {
        t["source_record_id"]
        for t in entry_topics
        if t.get("review_status", "proposed") != "rejected"
    }
    per_level: dict[str, Counter[str]] = {level: Counter() for level in scope}
    for row in rows:
        counts = per_level[row.primary_level]
        counts["source_rows"] += 1
        if row.record_id in with_topic:
            counts["with_topic"] += 1
        counts["accepted"] += 1
        if "pos_absent" in row.flags or "pos_blank" in row.flags:
            counts["missing_pos"] += 1
        if row.record_id in approved_records:
            counts["mapped"] += 1
            if gate_open:
                counts["publicly_eligible"] += 1
        elif AMBIGUITY_FLAGS.intersection(row.flags):
            counts["ambiguous"] += 1
        else:
            counts["awaiting_review"] += 1
        for flag in row.flags:
            counts[f"flag:{flag}"] += 1
    for issue in issues:
        if issue.level in per_level:
            per_level[issue.level][issue.kind] += 1
            if issue.kind in ("rejected", "duplicate"):
                per_level[issue.level]["source_rows"] += 1
    gaps = [
        {
            "serial": gap,
            "previous_serial_level": level_of_serial.get(gap - 1),
            "next_serial_level": level_of_serial.get(gap + 1),
        }
        for gap in serial_gaps
    ]
    for gap in gaps:
        # Attribute a gap to a level only when both neighbours share that level.
        if gap["previous_serial_level"] == gap["next_serial_level"] in per_level:
            per_level[gap["previous_serial_level"]]["missing_serial_within_level"] += 1
    return {
        "release_code": manifest["release_code"],
        "source_name": manifest["source_name"],
        "source_version": manifest.get("source_version"),
        "source_sha256": source_sha256,
        "data_origin": manifest["data_origin"],
        "permissions": {key: manifest["permissions"][key]["status"] for key in PERMISSION_KEYS},
        "publication_permission_gate_open": gate_open,
        "level_scope": list(scope),
        "records_in_file": records_in_file,
        "excluded_out_of_scope_by_primary_level": dict(sorted(excluded_by_level.items())),
        "serial_gaps": gaps,
        "per_level": {level: dict(sorted(per_level[level].items())) for level in scope},
        "issue_counts": dict(Counter(f"{i.kind}:{i.reason}" for i in issues)),
        "review": {
            "lexical_entries_accepted": None,  # filled by caller
            "mappings_accepted": len(mappings),
            "mappings_approved": sum(1 for m in mappings if m.get("review_status") == "approved"),
        },
    }


def finalize_report(result: ValidationResult) -> dict[str, Any]:
    result.report["review"]["lexical_entries_accepted"] = len(result.lexical_entries)
    return result.report


def write_report(result: ValidationResult, report_dir: Path, *, include_rows: bool) -> Path:
    report_dir.mkdir(parents=True, exist_ok=True)
    report = dict(finalize_report(result))
    if include_rows:
        report["issues"] = [issue.as_dict() for issue in result.issues]
        report["flagged_rows"] = [
            {"record_id": r.record_id, "serial": r.serial, "level": r.primary_level, "flags": r.flags}
            for r in result.rows
            if r.flags
        ]
    path = report_dir / f"{result.manifest['release_code']}-import-report.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (report_dir / f"{result.manifest['release_code']}-import-report.md").write_text(
        render_markdown_report(report), encoding="utf-8"
    )
    return path


def render_markdown_report(report: dict[str, Any]) -> str:
    columns = (
        "source_rows", "accepted", "ambiguous", "awaiting_review", "rejected", "duplicate",
        "missing_pos", "missing_serial_within_level", "mapped", "with_topic",
        "publicly_eligible",
    )
    lines = [
        f"# Import report — {report['release_code']}",
        "",
        f"- Source: {report['source_name']} {report.get('source_version') or ''}".rstrip(),
        f"- SHA-256: `{report['source_sha256']}`",
        f"- Data origin: {report['data_origin']}",
        "- Permissions: " + ", ".join(f"{k}={v}" for k, v in report["permissions"].items()),
        f"- Publication permission gate open: {report['publication_permission_gate_open']}",
        f"- Records in file: {report['records_in_file']}",
        f"- Excluded (primary level out of scope): {report['excluded_out_of_scope_by_primary_level']}",
        f"- Serial gaps: {[g['serial'] for g in report['serial_gaps']]}",
        "",
        "| Level | " + " | ".join(columns) + " |",
        "|---|" + "---|" * len(columns),
    ]
    for level, counts in report["per_level"].items():
        lines.append(f"| {level} | " + " | ".join(str(counts.get(c, 0)) for c in columns) + " |")
    lines += ["", "Flags by level:", ""]
    for level, counts in report["per_level"].items():
        flags = {k[5:]: v for k, v in counts.items() if k.startswith("flag:")}
        lines.append(f"- {level}: {flags}")
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- database


@dataclass
class ApplyResult:
    release_id: Any
    counts: dict[str, int]


def apply_release(db, result: ValidationResult) -> ApplyResult:
    """Upsert a validated release. One transaction; safe to repeat."""
    from sqlalchemy import select

    from app.models.hsk_catalog import (
        CatalogRelease,
        CatalogSourceEntry,
        CatalogSourceEntryLevel,
        CatalogSourceMapping,
    )
    from app.models.language import Language
    from app.models.learning_track import LearningTrack

    manifest = result.manifest
    language = db.scalar(select(Language).where(Language.code == manifest["language_code"]))
    if language is None:
        raise DatasetError(f"language {manifest['language_code']} not found")
    track = db.scalar(
        select(LearningTrack).where(
            LearningTrack.language_id == language.id,
            LearningTrack.code == manifest["learning_track_code"],
        )
    )
    if track is None or track.level_framework.upper() != "HSK":
        raise DatasetError("learning track not found or not an HSK track")

    try:
        release = db.scalar(
            select(CatalogRelease)
            .where(
                CatalogRelease.learning_track_id == track.id,
                CatalogRelease.code == manifest["release_code"],
            )
            .with_for_update()
        )
        if release is None:
            release = CatalogRelease(
                learning_track_id=track.id,
                code=manifest["release_code"],
                status="draft",
                source_sha256=result.source_sha256,
            )
            db.add(release)
        elif release.status in ("published", "retired"):
            raise ReleaseStateError(
                f"release {release.code} is {release.status}; corrections need a new release"
            )
        elif release.source_sha256 != result.source_sha256:
            raise ReleaseStateError(
                f"release {release.code} was captured from a different source file"
            )
        release.title = manifest["title"]
        release.source_name = manifest["source_name"]
        release.source_version = manifest.get("source_version")
        release.data_origin = manifest["data_origin"]
        release.source_manifest = {
            k: v for k, v in manifest.items() if k not in ("permissions",)
        }
        for key in PERMISSION_KEYS:
            setattr(release, f"{key}_permission_status", manifest["permissions"][key]["status"])
        release.permission_evidence = {
            key: manifest["permissions"][key].get("evidence") for key in PERMISSION_KEYS
        }
        db.flush()

        existing = {
            entry.source_record_id_value: entry
            for entry in db.scalars(
                select(CatalogSourceEntry).where(
                    CatalogSourceEntry.catalog_release_id == release.id,
                    CatalogSourceEntry.source_record_id_type == manifest["source_record_id_type"],
                )
            )
        }
        existing_levels = {
            (level.source_entry_id, level.level_code)
            for level in db.scalars(
                select(CatalogSourceEntryLevel).where(
                    CatalogSourceEntryLevel.catalog_release_id == release.id
                )
            )
        }
        approved = {
            str(m["source_record_id"]) for m in result.mappings if m.get("review_status") == "approved"
        }
        counts: Counter[str] = Counter()
        entries_by_record: dict[str, CatalogSourceEntry] = {}
        for row in result.rows:
            entry = existing.get(row.record_id)
            if entry is None:
                entry = CatalogSourceEntry(
                    catalog_release_id=release.id,
                    source_record_id_type=manifest["source_record_id_type"],
                    source_record_id_value=row.record_id,
                    official_serial=row.serial,
                    raw_word=row.raw_word,
                    raw_pinyin=row.raw_pinyin,
                    raw_pos=row.raw_pos,
                    raw_level_name=row.raw_level_name,
                    raw_payload=row.payload,
                    payload_sha256=row.payload_sha256,
                    search_pinyin=toneless_pinyin(row.raw_pinyin),
                )
                db.add(entry)
                counts["source_entries_inserted"] += 1
            elif entry.payload_sha256 != row.payload_sha256:
                raise ReleaseStateError(
                    f"source record {row.record_id} changed; corrections need a new release"
                )
            else:
                counts["source_entries_unchanged"] += 1
            if entry.review_status != "retired":
                if row.record_id in approved:
                    entry.review_status = "accepted"
                elif AMBIGUITY_FLAGS.intersection(row.flags):
                    entry.review_status = "ambiguous"
                else:
                    entry.review_status = "pending"
            entry.review_flags = list(row.flags)
            entries_by_record[row.record_id] = entry
        db.flush()

        for row in result.rows:
            entry = entries_by_record[row.record_id]
            for index, level in enumerate(row.levels):
                if (entry.id, level) in existing_levels:
                    continue
                db.add(
                    CatalogSourceEntryLevel(
                        source_entry_id=entry.id,
                        level_code=level,
                        catalog_release_id=release.id,
                        role="primary" if index == 0 else "annotation",
                        order_index=index,
                    )
                )
                counts["levels_inserted"] += 1
        db.flush()

        lexical_ids = _apply_lexical(db, language.id, result.lexical_entries, counts)

        existing_mappings = {
            (m.source_entry_id, m.lexical_entry_id, m.pronunciation_id, m.sense_id): m
            for m in db.scalars(
                select(CatalogSourceMapping).where(
                    CatalogSourceMapping.catalog_release_id == release.id
                )
            )
        }
        for index, item in enumerate(result.mappings):
            lexical = lexical_ids[item["lexical_key"]]
            entry = entries_by_record[str(item["source_record_id"])]
            pronunciation_id = (
                lexical["pronunciations"][item["pronunciation"]]
                if item.get("pronunciation") is not None
                else None
            )
            sense_id = (
                lexical["senses"][item["sense_key"]] if item.get("sense_key") is not None else None
            )
            key = (entry.id, lexical["id"], pronunciation_id, sense_id)
            mapping = existing_mappings.get(key)
            if mapping is None:
                mapping = CatalogSourceMapping(
                    catalog_release_id=release.id,
                    source_entry_id=entry.id,
                    lexical_entry_id=lexical["id"],
                    pronunciation_id=pronunciation_id,
                    sense_id=sense_id,
                )
                db.add(mapping)
                existing_mappings[key] = mapping
                counts["mappings_inserted"] += 1
            else:
                counts["mappings_unchanged"] += 1
            mapping.review_status = item.get("review_status", "proposed")
            mapping.order_index = int(item.get("order", index))
            mapping.notes = item.get("notes")

        _apply_topics(db, release.id, result, entries_by_record, counts)

        release.import_report = finalize_report(result)
        release.import_completed_at = datetime.now(UTC)
        db.flush()
        db.commit()
    except Exception:
        db.rollback()
        raise
    return ApplyResult(release.id, dict(counts))


def _apply_topics(db, release_id, result: ValidationResult, entries_by_record, counts) -> None:
    from sqlalchemy import select

    from app.models.hsk_catalog import CatalogEntryTopic, CatalogTopic

    existing = {
        (topic.level_code, topic.topic_key): topic
        for topic in db.scalars(
            select(CatalogTopic).where(CatalogTopic.catalog_release_id == release_id)
        )
    }
    for index, item in enumerate(result.topics):
        level, key, path = item["level_code"], item["key"], item["path"]
        topic = existing.get((level, key))
        if topic is None:
            parent = existing[(level, topic_key(path[:-1]))] if len(path) > 1 else None
            topic = CatalogTopic(
                catalog_release_id=release_id,
                level_code=level,
                parent_id=parent.id if parent else None,
                depth=len(path),
                topic_key=key,
            )
            db.add(topic)
            existing[(level, key)] = topic
            counts["topics_inserted"] += 1
        topic.name_zh = path[-1]
        topic.name_vi = (item.get("name_vi") or "").strip() or None
        topic.source = item.get("source", "official_syllabus")
        topic.order_index = int(item.get("order", index))
        db.flush()

    current = {
        (link.source_entry_id, link.topic_id): link
        for link in db.scalars(
            select(CatalogEntryTopic).where(CatalogEntryTopic.catalog_release_id == release_id)
        )
    }
    for item in result.entry_topics:
        entry = entries_by_record[item["source_record_id"]]
        topic = existing[(item["level_code"], item["key"])]
        link = current.get((entry.id, topic.id))
        if link is None:
            link = CatalogEntryTopic(
                source_entry_id=entry.id,
                topic_id=topic.id,
                catalog_release_id=release_id,
                level_code=item["level_code"],
            )
            db.add(link)
            current[(entry.id, topic.id)] = link
            counts["entry_topics_inserted"] += 1
        link.origin = item.get("origin", "ai_suggested")
        link.review_status = item.get("review_status", "proposed")
    db.flush()


def _apply_lexical(db, language_id, items, counts) -> dict[str, dict[str, Any]]:
    from sqlalchemy import delete, select

    from app.models.hsk_catalog import (
        LexicalEntry,
        LexicalPronunciation,
        LexicalSense,
        LexicalSenseExample,
        LexicalSensePos,
        LexicalSensePronunciation,
        LexicalVariant,
    )

    resolved: dict[str, dict[str, Any]] = {}
    for item in items:
        key = item["lexical_key"].strip()
        lexical = db.scalar(
            select(LexicalEntry).where(
                LexicalEntry.language_id == language_id, LexicalEntry.lexical_key == key
            )
        )
        if lexical is None:
            lexical = LexicalEntry(language_id=language_id, lexical_key=key)
            db.add(lexical)
            counts["lexical_entries_inserted"] += 1
        else:
            counts["lexical_entries_unchanged"] += 1
        lexical.headword = item["headword"].strip()
        lexical.status = item.get("status", "active")
        db.flush()

        pronunciations: dict[str, Any] = {}
        current = {
            p.pinyin: p
            for p in db.scalars(
                select(LexicalPronunciation).where(
                    LexicalPronunciation.lexical_entry_id == lexical.id
                )
            )
        }
        for index, reading in enumerate(item.get("pronunciations", [])):
            pinyin = reading["pinyin"].strip()
            row = current.get(pinyin)
            if row is None:
                row = LexicalPronunciation(lexical_entry_id=lexical.id, pinyin=pinyin)
                db.add(row)
                counts["pronunciations_inserted"] += 1
            row.order_index = index
            db.flush()
            pronunciations[pinyin] = row.id

        senses: dict[str, Any] = {}
        for index, sense_item in enumerate(item.get("senses", [])):
            sense = db.scalar(
                select(LexicalSense).where(
                    LexicalSense.lexical_entry_id == lexical.id,
                    LexicalSense.sense_key == sense_item["sense_key"],
                )
            )
            if sense is None:
                sense = LexicalSense(lexical_entry_id=lexical.id, sense_key=sense_item["sense_key"])
                db.add(sense)
                counts["senses_inserted"] += 1
            sense.gloss_en = (sense_item.get("gloss_en") or "").strip() or None
            sense.gloss_vi = (sense_item.get("gloss_vi") or "").strip() or None
            sense.gloss_source = sense_item["gloss_source"].strip()
            sense.review_status = sense_item.get("review_status", "draft")
            sense.status = sense_item.get("status", "active")
            sense.order_index = int(sense_item.get("order", index))
            db.flush()
            senses[sense.sense_key] = sense.id

            db.execute(delete(LexicalSensePos).where(LexicalSensePos.sense_id == sense.id))
            for pos in sense_item.get("pos", []):
                db.add(
                    LexicalSensePos(
                        sense_id=sense.id,
                        pos_code=pos["code"],
                        pos_origin=pos["origin"],
                        source_label=pos.get("source_label"),
                    )
                )
            linked = set(
                db.scalars(
                    select(LexicalSensePronunciation.pronunciation_id).where(
                        LexicalSensePronunciation.sense_id == sense.id
                    )
                )
            )
            for reading in sense_item.get("pronunciations", []):
                pronunciation_id = pronunciations[reading]
                if pronunciation_id not in linked:
                    db.add(
                        LexicalSensePronunciation(
                            sense_id=sense.id,
                            pronunciation_id=pronunciation_id,
                            lexical_entry_id=lexical.id,
                        )
                    )
            examples = {
                e.order_index: e
                for e in db.scalars(
                    select(LexicalSenseExample).where(LexicalSenseExample.sense_id == sense.id)
                )
            }
            for example_index, example_item in enumerate(sense_item.get("examples", [])):
                order = int(example_item.get("order", example_index))
                example = examples.get(order)
                if example is None:
                    example = LexicalSenseExample(sense_id=sense.id, order_index=order)
                    db.add(example)
                example.text_zh = example_item["text_zh"].strip()
                example.pinyin = example_item.get("pinyin")
                example.translation_vi = example_item.get("translation_vi")
                example.example_source = example_item["source"].strip()
            db.flush()

        current_variants = {
            (v.variant_form, v.variant_type): v
            for v in db.scalars(
                select(LexicalVariant).where(LexicalVariant.lexical_entry_id == lexical.id)
            )
        }
        for index, variant_item in enumerate(item.get("variants", [])):
            form = variant_item["form"].strip()
            variant = current_variants.get((form, variant_item["type"]))
            if variant is None:
                variant = LexicalVariant(
                    lexical_entry_id=lexical.id, variant_form=form, variant_type=variant_item["type"]
                )
                db.add(variant)
            variant.pronunciation_id = (
                pronunciations[variant_item["pronunciation"]]
                if variant_item.get("pronunciation")
                else None
            )
            variant.variant_source = variant_item["source"].strip()
            variant.order_index = index
        db.flush()
        resolved[key] = {"id": lexical.id, "pronunciations": pronunciations, "senses": senses}
    return resolved


def publish_release(
    db, *, track_id, release_code: str, allow_awaiting_review: bool = False
) -> None:
    """Publish one release for a track, retiring the previously published one."""
    from sqlalchemy import func, select

    from app.models.hsk_catalog import CatalogRelease, CatalogSourceEntry

    try:
        release = db.scalar(
            select(CatalogRelease)
            .where(CatalogRelease.learning_track_id == track_id, CatalogRelease.code == release_code)
            .with_for_update()
        )
        if release is None:
            raise ReleaseStateError("release not found")
        if release.status not in ("draft", "in_review"):
            raise ReleaseStateError(f"release is {release.status}")
        if release.import_completed_at is None:
            raise ReleaseStateError("release import is incomplete")
        if release.data_origin == "third_party" and any(
            getattr(release, f"{key}_permission_status") != "approved" for key in PERMISSION_KEYS
        ):
            raise ReleaseStateError(
                "publication blocked: storage, transformation, redistribution and publication "
                "permissions must all be approved with evidence"
            )
        unreviewed = db.scalar(
            select(func.count())
            .select_from(CatalogSourceEntry)
            .where(
                CatalogSourceEntry.catalog_release_id == release.id,
                CatalogSourceEntry.review_status.in_(("pending", "ambiguous")),
            )
        ) or 0
        if unreviewed and not allow_awaiting_review:
            raise ReleaseStateError(
                f"{unreviewed} source records are awaiting review; pass allow_awaiting_review "
                "to publish them with official fields only"
            )
        current = db.scalars(
            select(CatalogRelease)
            .where(
                CatalogRelease.learning_track_id == track_id,
                CatalogRelease.status == "published",
            )
            .with_for_update()
        ).all()
        for previous in current:
            previous.status = "retired"
        db.flush()
        release.status = "published"
        release.published_at = datetime.now(UTC)
        db.commit()
    except Exception:
        db.rollback()
        raise


def retire_source_entry(db, source_entry_id) -> None:
    """Retire a source record without deleting it (saved snapshots stay intact)."""
    from app.models.hsk_catalog import CatalogSourceEntry

    entry = db.get(CatalogSourceEntry, source_entry_id)
    if entry is None:
        raise ReleaseStateError("source entry not found")
    entry.review_status = "retired"
    db.commit()
