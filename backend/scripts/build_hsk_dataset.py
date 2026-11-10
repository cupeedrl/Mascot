"""Build an importer dataset (manifest.json + review.json) for HSK levels.

Inputs (kept outside git):
  --cti       frozen CTI vocabulary API snapshot (official word list)
  --tree      official topic tree extracted from the 2025 syllabus (topic_tree.json)
  --content   directory with topic_codes.json, topic_names_vi.json and one
              <level>.tsv per level: "record id|topic code|English|Vietnamese"

For each level the builder creates one lexical entry and one sense per CTI
record, copies the official POS labels (parenthesized labels are skipped, never
guessed), links every reading to the sense, and assigns the record to the topic
named by its code. Meanings are labelled with --gloss-source.

    python -m scripts.build_hsk_dataset --cti <file> --tree <file> --content <dir> \
        --levels HSK1 --release-code hsk-2025-hsk1 --out <dir>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path

from app.catalog.hsk_import import parse_level_name, source_readings, toneless_pinyin

POS_LABELS = {
    "名": "noun",
    "动": "verb",
    "形": "adjective",
    "副": "adverb",
    "代": "pronoun",
    "数": "numeral",
    "量": "measure_word",
    "数量": "numeral_measure",
    "介": "preposition",
    "连": "conjunction",
    "助": "particle",
    "叹": "interjection",
    "拟声": "onomatopoeia",
    "前缀": "prefix",
    "后缀": "suffix",
}
HOMOGRAPH = re.compile(r"^(.+?)\d+$")


def official_pos(cixing: str | None) -> list[dict[str, str]]:
    """Unparenthesized CTI POS labels only; unknown labels are dropped, not guessed."""
    if not cixing or not cixing.strip():
        return []
    result = []
    for label in re.split(r"[、,，]", cixing):
        label = label.strip()
        if not label or "（" in label or "(" in label:
            continue
        code = POS_LABELS.get(label)
        if code and code not in {item["code"] for item in result}:
            result.append({"code": code, "origin": "official_source", "source_label": label})
    return result


def level_file(level: str) -> str:
    return level.lower().replace("-", "") + ".tsv"


def read_content(path: Path) -> dict[str, tuple[str, str, str]]:
    content: dict[str, tuple[str, str, str]] = {}
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip() or line.startswith("#"):
            continue
        parts = line.split("|")
        if len(parts) != 4 or not all(part.strip() for part in parts):
            raise SystemExit(f"{path.name}:{number}: expected 4 non-empty columns")
        record_id, code, gloss_en, gloss_vi = (part.strip() for part in parts)
        if record_id in content:
            raise SystemExit(f"{path.name}:{number}: duplicate record id {record_id}")
        content[record_id] = (code, gloss_en, gloss_vi)
    return content


def build(args: argparse.Namespace) -> dict[str, int]:
    cti_bytes = Path(args.cti).read_bytes()
    records = json.loads(cti_bytes)["data"]["records"]
    tree = {level["level_code"]: level for level in json.loads(Path(args.tree).read_text(encoding="utf-8"))}
    content_dir = Path(args.content)
    codes = json.loads((content_dir / "topic_codes.json").read_text(encoding="utf-8"))
    names_vi = json.loads((content_dir / "topic_names_vi.json").read_text(encoding="utf-8"))

    topics, lexical_entries, mappings, entry_topics = [], [], [], []
    stats = {"records": 0, "with_content": 0, "without_content": 0}
    used_keys: set[str] = set()
    for level in args.levels:
        level_codes = codes[level]
        for node in tree[level]["topics"]:
            topics.append({"level_code": level, "path": [node["name_zh"]], "name_vi": names_vi.get(node["name_zh"])})
            for child in node["children"]:
                path = [node["name_zh"], child["name_zh"]]
                topics.append({"level_code": level, "path": path, "name_vi": names_vi.get(child["name_zh"])})
                for sub in child["subtopics"]:
                    topics.append({"level_code": level, "path": [*path, sub], "name_vi": names_vi.get(sub)})
        for item in codes.get("mascot_topics", []):
            topics.append({"level_code": level, "path": item["path"], "name_vi": item["name_vi"], "source": "mascot"})

        content = read_content(content_dir / level_file(level))
        level_records = [r for r in records if parse_level_name(r["levelName"])[0] == level]
        unknown = set(content) - {str(r["id"]) for r in level_records}
        if unknown:
            raise SystemExit(f"{level}: content ids not in this level: {sorted(unknown)[:10]}")
        for record in level_records:
            stats["records"] += 1
            record_id = str(record["id"])
            if record_id not in content:
                stats["without_content"] += 1
                continue
            stats["with_content"] += 1
            code, gloss_en, gloss_vi = content[record_id]
            if code not in level_codes:
                raise SystemExit(f"{level}: record {record_id} uses unknown topic code {code}")
            word = record["word"].strip()
            headword = (HOMOGRAPH.match(word) or [None, word])[1]
            readings = source_readings(record["pinyin"])
            key = f"zh:{word}#{toneless_pinyin(record['pinyin'])}"
            if key in used_keys:
                key = f"{key}#{record_id}"
            used_keys.add(key)
            lexical_entries.append(
                {
                    "lexical_key": key,
                    "headword": headword,
                    "pronunciations": [{"pinyin": reading} for reading in readings],
                    "senses": [
                        {
                            "sense_key": "s1",
                            "gloss_en": gloss_en,
                            "gloss_vi": gloss_vi,
                            "gloss_source": args.gloss_source,
                            "review_status": "approved",
                            "pos": official_pos(record.get("cixing")),
                            "pronunciations": readings,
                        }
                    ],
                }
            )
            mappings.append(
                {
                    "source_record_id": record_id,
                    "lexical_key": key,
                    "pronunciation": readings[0] if len(readings) == 1 else None,
                    "sense_key": "s1",
                    "review_status": "approved",
                }
            )
            entry_topics.append(
                {
                    "source_record_id": record_id,
                    "topic_path": level_codes[code],
                    "origin": "ai_suggested",
                    "review_status": "proposed",
                }
            )

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    review = {"lexical_entries": lexical_entries, "mappings": mappings, "topics": topics, "entry_topics": entry_topics}
    (out / "review.json").write_text(json.dumps(review, ensure_ascii=False, indent=1), encoding="utf-8")
    evidence = {"decision": "OD-11 owner decision 2026-11-10", "reference": "docs/hsk/OWNER_DECISIONS.md"}
    manifest = {
        "release_code": args.release_code,
        "title": args.title,
        "learning_track_code": "general-chinese",
        "language_code": "zh",
        "source_name": "CTI HSK 3.0 vocabulary list + HSK 2025 topic syllabus",
        "source_version": "CTI API snapshot 2026-10-30; syllabus 2025-11",
        # Relative, so the dataset also loads inside a container with the same layout.
        "source_file": Path(os.path.relpath(Path(args.cti).resolve(), out.resolve())).as_posix(),
        "source_sha256": hashlib.sha256(cti_bytes).hexdigest(),
        "source_record_id_type": "cti_api_id",
        "data_origin": "third_party",
        "level_scope": list(args.levels),
        "permissions": {
            key: {"status": "approved", "evidence": evidence}
            for key in ("storage", "transformation", "redistribution", "publication")
        },
        "review_file": "review.json",
        "content_notes": f"Meanings: {args.gloss_source}. Topic assignment: AI suggestion within the official topic tree.",
    }
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--cti", required=True)
    parser.add_argument("--tree", required=True)
    parser.add_argument("--content", required=True)
    parser.add_argument("--levels", nargs="+", required=True)
    parser.add_argument("--release-code", required=True)
    parser.add_argument("--title", default="HSK 3.0 (2025) vocabulary by topic")
    parser.add_argument("--gloss-source", default="Mascot AI draft (Claude), 2026-11-11")
    parser.add_argument("--out", required=True)
    print(json.dumps(build(parser.parse_args()), indent=1))


if __name__ == "__main__":
    main()
