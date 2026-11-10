"""Mascot-authored synthetic HSK dataset for tests and local demos.

NOT OFFICIAL HSK DATA. Records imitate the *shape* of the CTI API payload
(``id``, ``sort``, ``word``, ``pinyin``, ``cixing``, ``levelName``) so the
importer can be exercised, but the level assignments, serials, glosses,
POS annotations and examples are invented by Mascot for testing. The
release is labelled ``data_origin = synthetic_fixture``.

Usage for a disposable database demo::

    python -m tests.hsk_fixtures <output_dir> [--variant v2]
"""

from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

FIXTURE_SOURCE_NAME = "Mascot synthetic HSK fixture (not official)"

# API id and serial deliberately differ so tests prove they are stored separately.
SOURCE_RECORDS: list[dict[str, Any]] = [
    {"id": "101", "type": 1, "word": "爱", "pinyin": "ài", "cixing": "动", "sort": 1, "levelName": "一级"},
    {"id": "102", "type": 1, "word": "水", "pinyin": "shuǐ", "cixing": "名", "sort": 2, "levelName": "一级"},
    {"id": "103", "type": 1, "word": "长", "pinyin": "cháng/zhǎng", "cixing": "形、动", "sort": 3, "levelName": "二级（四级）"},
    {"id": "104", "type": 1, "word": "行1", "pinyin": "xíng", "cixing": "形", "sort": 4, "levelName": "二级"},
    {"id": "105", "type": 1, "word": "行2", "pinyin": "háng", "cixing": "名", "sort": 5, "levelName": "三级"},
    # serial 6 intentionally absent (synthetic gap)
    {"id": "106", "type": 1, "word": "学习", "pinyin": "xuéxí", "sort": 7, "levelName": "三级"},
    {"id": "107", "type": 1, "word": "朋友", "pinyin": "péngyou", "cixing": "名", "sort": 8, "levelName": "四级"},
    {"id": "108", "type": 1, "word": "喜欢", "pinyin": "xǐhuan", "cixing": "动", "sort": 9, "levelName": "五级"},
    {"id": "109", "type": 1, "word": "谁", "pinyin": "shéi/shuí", "cixing": "代", "sort": 10, "levelName": "六级"},
    {"id": "110", "type": 1, "word": "吃", "pinyin": "chī", "cixing": "", "sort": 11, "levelName": "六级"},
    {"id": "111", "type": 1, "word": "研究", "pinyin": "yánjiū", "cixing": "动", "sort": 12, "levelName": "七-九级"},
    {"id": "112", "type": 1, "word": "家", "pinyin": "jiā", "cixing": "名", "sort": 13, "levelName": "十级"},
    {"id": "101", "type": 1, "word": "爱", "pinyin": "ài", "cixing": "动", "sort": 14, "levelName": "一级"},
    {"id": "113", "type": 1, "word": " ", "pinyin": "kòng", "cixing": "名", "sort": 15, "levelName": "二级"},
    {"id": "114", "type": 1, "word": "你好", "pinyin": "nǐ hǎo", "cixing": "动", "sort": 16, "levelName": "四级"},
    {"id": "115", "type": 1, "word": "茶", "pinyin": "chá", "cixing": "名", "sort": 17, "levelName": "五级"},
]

SOURCE_TAG = "mascot-synthetic-fixture"

REVIEW: dict[str, Any] = {
    "lexical_entries": [
        {
            "lexical_key": "zh:爱",
            "headword": "爱",
            "pronunciations": [{"pinyin": "ài"}],
            "senses": [
                {
                    "sense_key": "s1",
                    "gloss_en": "to love",
                    "gloss_vi": "yêu",
                    "gloss_source": SOURCE_TAG,
                    "review_status": "approved",
                    "pos": [{"code": "verb", "origin": "official_source", "source_label": "动"}],
                    "pronunciations": ["ài"],
                    "examples": [{"text_zh": "我爱我的家。", "translation_vi": "Tôi yêu gia đình tôi.", "source": SOURCE_TAG}],
                }
            ],
        },
        {
            "lexical_key": "zh:水",
            "headword": "水",
            "pronunciations": [{"pinyin": "shuǐ"}],
            "senses": [
                {
                    "sense_key": "s1",
                    "gloss_en": "water",
                    "gloss_vi": "nước",
                    "gloss_source": SOURCE_TAG,
                    "review_status": "approved",
                    "pos": [{"code": "noun", "origin": "official_source", "source_label": "名"}],
                    "pronunciations": ["shuǐ"],
                }
            ],
        },
        {
            "lexical_key": "zh:长",
            "headword": "长",
            "pronunciations": [{"pinyin": "cháng"}, {"pinyin": "zhǎng"}],
            "variants": [{"form": "長", "type": "traditional", "source": SOURCE_TAG}],
            "senses": [
                {
                    "sense_key": "long",
                    "gloss_en": "long",
                    "gloss_vi": "dài",
                    "gloss_source": SOURCE_TAG,
                    "review_status": "approved",
                    "pos": [{"code": "adjective", "origin": "official_source", "source_label": "形"}],
                    "pronunciations": ["cháng"],
                    "examples": [{"text_zh": "这条河很长。", "source": SOURCE_TAG}],
                },
                {
                    "sense_key": "grow",
                    "gloss_en": "to grow",
                    "gloss_vi": "lớn lên",
                    "gloss_source": SOURCE_TAG,
                    "review_status": "approved",
                    "pos": [{"code": "verb", "origin": "official_source", "source_label": "动"}],
                    "pronunciations": ["zhǎng"],
                },
            ],
        },
        {
            "lexical_key": "zh:行#xing",
            "headword": "行",
            "pronunciations": [{"pinyin": "xíng"}],
            "senses": [
                {
                    # POS intentionally left unannotated at sense level.
                    "sense_key": "ok",
                    "gloss_en": "all right; OK",
                    "gloss_vi": "được",
                    "gloss_source": SOURCE_TAG,
                    "review_status": "approved",
                    "pronunciations": ["xíng"],
                }
            ],
        },
        {
            "lexical_key": "zh:行#hang",
            "headword": "行",
            "pronunciations": [{"pinyin": "háng"}],
            "senses": [
                {
                    "sense_key": "row",
                    "gloss_en": "row; line",
                    "gloss_vi": "hàng",
                    "gloss_source": SOURCE_TAG,
                    "review_status": "approved",
                    "pos": [{"code": "noun", "origin": "official_source", "source_label": "名"}],
                    "pronunciations": ["háng"],
                }
            ],
        },
        {
            "lexical_key": "zh:学习",
            "headword": "学习",
            "pronunciations": [{"pinyin": "xuéxí"}],
            "senses": [
                {
                    "sense_key": "s1",
                    "gloss_en": "to study",
                    "gloss_vi": "học",
                    "gloss_source": SOURCE_TAG,
                    "review_status": "approved",
                    # Official POS is missing; this annotation is explicitly editorial.
                    "pos": [{"code": "verb", "origin": "editorial"}],
                    "pronunciations": ["xuéxí"],
                }
            ],
        },
        {
            "lexical_key": "zh:朋友",
            "headword": "朋友",
            "pronunciations": [{"pinyin": "péngyou"}],
            "senses": [],
        },
        {
            "lexical_key": "zh:吃",
            "headword": "吃",
            "pronunciations": [{"pinyin": "chī"}],
            "senses": [
                {
                    "sense_key": "s1",
                    "gloss_en": "to eat",
                    "gloss_vi": "ăn",
                    "gloss_source": SOURCE_TAG,
                    "review_status": "approved",
                    "pos": [{"code": "verb", "origin": "editorial"}],
                    "pronunciations": ["chī"],
                }
            ],
        },
        {
            "lexical_key": "zh:你好",
            "headword": "你好",
            "pronunciations": [{"pinyin": "nǐ hǎo"}],
            "senses": [
                {
                    "sense_key": "s1",
                    "gloss_en": "hello",
                    "gloss_source": SOURCE_TAG,
                    "review_status": "draft",
                    "pronunciations": ["nǐ hǎo"],
                }
            ],
        },
        {
            "lexical_key": "zh:茶",
            "headword": "茶",
            "pronunciations": [{"pinyin": "chá"}],
            "senses": [
                {
                    "sense_key": "s1",
                    "gloss_en": "tea",
                    "gloss_vi": "trà",
                    "gloss_source": SOURCE_TAG,
                    "review_status": "approved",
                    "pos": [{"code": "noun", "origin": "official_source", "source_label": "名"}],
                    "pronunciations": ["chá"],
                }
            ],
        },
        # Rejected: a sense names a reading that this lexical entry does not have.
        {
            "lexical_key": "zh:坏",
            "headword": "坏",
            "pronunciations": [{"pinyin": "huài"}],
            "senses": [
                {
                    "sense_key": "s1",
                    "gloss_en": "bad",
                    "gloss_source": SOURCE_TAG,
                    "pronunciations": ["hǎo"],
                }
            ],
        },
        # Rejected: POS code outside the controlled list.
        {
            "lexical_key": "zh:好",
            "headword": "好",
            "pronunciations": [{"pinyin": "hǎo"}],
            "senses": [
                {
                    "sense_key": "s1",
                    "gloss_en": "good",
                    "gloss_source": SOURCE_TAG,
                    "pos": [{"code": "verbish", "origin": "editorial"}],
                }
            ],
        },
    ],
    "mappings": [
        {"source_record_id": "101", "lexical_key": "zh:爱", "pronunciation": "ài", "sense_key": "s1", "review_status": "approved"},
        {"source_record_id": "102", "lexical_key": "zh:水", "pronunciation": "shuǐ", "sense_key": "s1", "review_status": "approved"},
        {"source_record_id": "103", "lexical_key": "zh:长", "pronunciation": "cháng", "sense_key": "long", "review_status": "approved", "order": 0},
        {"source_record_id": "103", "lexical_key": "zh:长", "pronunciation": "zhǎng", "sense_key": "grow", "review_status": "approved", "order": 1},
        {"source_record_id": "104", "lexical_key": "zh:行#xing", "pronunciation": "xíng", "sense_key": "ok", "review_status": "approved"},
        {"source_record_id": "105", "lexical_key": "zh:行#hang", "pronunciation": "háng", "sense_key": "row", "review_status": "approved"},
        {"source_record_id": "106", "lexical_key": "zh:学习", "pronunciation": "xuéxí", "sense_key": "s1", "review_status": "approved"},
        {"source_record_id": "107", "lexical_key": "zh:朋友", "pronunciation": "péngyou", "sense_key": None, "review_status": "approved"},
        {"source_record_id": "110", "lexical_key": "zh:吃", "pronunciation": "chī", "sense_key": "s1", "review_status": "approved"},
        {"source_record_id": "114", "lexical_key": "zh:你好", "pronunciation": "nǐ hǎo", "sense_key": "s1", "review_status": "approved"},
        {"source_record_id": "115", "lexical_key": "zh:茶", "pronunciation": "chá", "sense_key": "s1", "review_status": "approved"},
        # Duplicate of an earlier mapping.
        {"source_record_id": "101", "lexical_key": "zh:爱", "pronunciation": "ài", "sense_key": "s1", "review_status": "approved"},
        # Rejected: reading not present in the source record.
        {"source_record_id": "101", "lexical_key": "zh:爱", "pronunciation": "ǎi", "sense_key": None, "review_status": "approved"},
        # Rejected: unknown source record.
        {"source_record_id": "999", "lexical_key": "zh:爱", "pronunciation": "ài", "sense_key": "s1", "review_status": "approved"},
        # Rejected: excluded (HSK7-9) source record.
        {"source_record_id": "111", "lexical_key": "zh:爱", "pronunciation": "ài", "sense_key": "s1", "review_status": "approved"},
        # Rejected: sense and reading of 长 that are not linked together.
        {"source_record_id": "103", "lexical_key": "zh:长", "pronunciation": "cháng", "sense_key": "grow", "review_status": "approved"},
    ],
}

PERMISSIONS_FIXTURE = {
    key: {"status": "approved", "evidence": {"note": "Mascot-authored synthetic test data"}}
    for key in ("storage", "transformation", "redistribution", "publication")
}


def build_dataset(
    directory: Path,
    *,
    release_code: str = "synthetic-hsk-v1",
    records: list[dict[str, Any]] | None = None,
    review: dict[str, Any] | None = None,
    data_origin: str = "synthetic_fixture",
    permissions: dict[str, Any] | None = None,
) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    source_bytes = json.dumps(
        {"code": 0, "ok": True, "data": {"records": records if records is not None else SOURCE_RECORDS}},
        ensure_ascii=False,
        indent=1,
    ).encode("utf-8")
    (directory / "source.json").write_bytes(source_bytes)
    (directory / "review.json").write_text(
        json.dumps(review if review is not None else REVIEW, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    manifest = {
        "release_code": release_code,
        "title": "Synthetic HSK test release (NOT official HSK)",
        "learning_track_code": "general-chinese",
        "language_code": "zh",
        "source_name": FIXTURE_SOURCE_NAME,
        "source_version": release_code,
        "source_file": "source.json",
        "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "source_record_id_type": "fixture_api_id",
        "data_origin": data_origin,
        "level_scope": ["HSK1", "HSK2", "HSK3", "HSK4", "HSK5", "HSK6"],
        "permissions": permissions if permissions is not None else PERMISSIONS_FIXTURE,
        "review_file": "review.json",
    }
    (directory / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    return directory


def revised_review() -> dict[str, Any]:
    """A later catalog edit: changed glosses/POS and a retired sense."""
    review = copy.deepcopy(REVIEW)
    for item in review["lexical_entries"]:
        if item["lexical_key"] == "zh:爱":
            item["senses"][0]["gloss_en"] = "to love; to be fond of (revised)"
            item["senses"][0]["gloss_vi"] = "yêu; thích (đã sửa)"
            item["senses"][0]["pos"] = [{"code": "verb", "origin": "editorial"}]
        if item["lexical_key"] == "zh:长":
            item["senses"][1]["status"] = "retired"
    return review


if __name__ == "__main__":
    target = Path(sys.argv[1])
    variant = sys.argv[3] if len(sys.argv) > 3 and sys.argv[2] == "--variant" else "v1"
    if variant == "v2":
        build_dataset(target, release_code="synthetic-hsk-v2", review=revised_review())
    else:
        build_dataset(target)
    print(target)
