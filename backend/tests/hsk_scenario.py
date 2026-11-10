"""Shared HSK catalog learner scenario used by SQLite and PostgreSQL tests."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.ai.dependencies import get_exercise_ai_provider
from app.catalog import hsk_import
from app.main import app
from app.models import LearningTrack
from tests.hsk_fixtures import build_dataset
from tests.test_ai_exercises import FakeExerciseProvider

PASSWORD = "StrongPassword123!"


def import_dataset(session_factory: sessionmaker[Session], directory: Path) -> hsk_import.ApplyResult:
    result = hsk_import.validate_dataset(hsk_import.load_dataset(directory))
    with session_factory() as db:
        return hsk_import.apply_release(db, result)


def import_and_publish(
    session_factory: sessionmaker[Session], tmp_path: Path, **dataset_kwargs: Any
) -> uuid.UUID:
    directory = build_dataset(tmp_path / dataset_kwargs.get("release_code", "v1"), **dataset_kwargs)
    applied = import_dataset(session_factory, directory)
    with session_factory() as db:
        track = db.scalar(select(LearningTrack).where(LearningTrack.code == "general-chinese"))
        hsk_import.publish_release(
            db,
            track_id=track.id,
            release_code=dataset_kwargs.get("release_code", "synthetic-hsk-v1"),
            allow_awaiting_review=True,
        )
    return applied.release_id


def authenticate(client: TestClient, email: str) -> dict[str, str]:
    credentials = {"email": email, "password": PASSWORD}
    assert client.post("/api/v1/auth/register", json=credentials).status_code == 201
    login = client.post("/api/v1/auth/login", json=credentials)
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def find_entry(client: TestClient, headers, track_id, level: str, word: str) -> dict[str, Any]:
    response = client.get(
        f"/api/v1/catalog/hsk/{track_id}/entries", params={"level": level}, headers=headers
    )
    assert response.status_code == 200, response.text
    return next(item for item in response.json()["items"] if item["raw_word"] == word)


def entry_detail(client: TestClient, headers, track_id, entry_id) -> dict[str, Any]:
    response = client.get(f"/api/v1/catalog/hsk/{track_id}/entries/{entry_id}", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def save(client: TestClient, headers, track_id, entry_id, mapping_id):
    return client.post(
        f"/api/v1/catalog/hsk/{track_id}/entries/{entry_id}/save",
        headers=headers,
        json={"mapping_id": str(mapping_id)},
    )


def run_learner_flow(client: TestClient, headers: dict[str, str], track_id: uuid.UUID) -> dict[str, Any]:
    """Browse HSK1–6, inspect entries, save senses, review and exercise."""
    levels = client.get(f"/api/v1/catalog/hsk/{track_id}/levels", headers=headers)
    assert levels.status_code == 200, levels.text
    body = levels.json()
    assert body["release"]["code"] == "synthetic-hsk-v1"
    assert [level["level_code"] for level in body["levels"]] == [
        "HSK1", "HSK2", "HSK3", "HSK4", "HSK5", "HSK6", "HSK7-9"
    ]
    by_level = {level["level_code"]: level["entry_count"] for level in body["levels"]}
    assert by_level == {"HSK1": 2, "HSK2": 2, "HSK3": 2, "HSK4": 2, "HSK5": 2, "HSK6": 2, "HSK7-9": 0}
    hsk1 = body["levels"][0]
    assert [group["name_zh"] for group in hsk1["topic_groups"]] == ["基本信息", "日常生活"]
    food = hsk1["topic_groups"][1]["topics"][0]
    assert (food["name_zh"], food["name_vi"], food["entry_count"]) == ("饮食", "Ăn uống", 1)
    assert food["subtopics"] == ["Đồ ăn, thức uống"]

    for number in range(1, 7):
        listing = client.get(
            f"/api/v1/catalog/hsk/{track_id}/entries",
            params={"level": f"HSK{number}"},
            headers=headers,
        )
        assert listing.status_code == 200
        assert listing.json()["total"] == 2
        assert all(item["level_code"] == f"HSK{number}" for item in listing.json()["items"])

    # Search by raw word, toneless pinyin and gloss.
    for term, expected in (("长", "长"), ("chang", "长"), ("tea", "茶")):
        found = client.get(
            f"/api/v1/catalog/hsk/{track_id}/entries", params={"q": term}, headers=headers
        ).json()["items"]
        assert expected in [item["raw_word"] for item in found]

    # Multiple readings and senses stay separate interpretations of one source record.
    chang = find_entry(client, headers, track_id, "HSK2", "长")
    detail = entry_detail(client, headers, track_id, chang["id"])
    assert detail["source"]["raw_pinyin"] == "cháng/zhǎng"
    assert detail["source"]["raw_pos"] == "形、动"
    assert detail["source"]["levels"] == [
        {"level_code": "HSK2", "role": "primary"},
        {"level_code": "HSK4", "role": "annotation"},
    ]
    assert detail["source"]["record_id"] == "103"
    assert detail["source"]["official_serial"] == 3
    [interpretation] = detail["interpretations"]
    assert interpretation["pronunciations"] == ["cháng", "zhǎng"]
    assert [v["form"] for v in interpretation["variants"]] == ["長"]
    senses = {s["sense_key"]: s for s in interpretation["senses"]}
    assert senses["long"]["pronunciations"] == ["cháng"]
    assert senses["grow"]["pronunciations"] == ["zhǎng"]
    assert senses["long"]["examples"][0]["text_zh"] == "这条河很长。"

    # Missing POS is reported as missing, never filled.
    xing = entry_detail(client, headers, track_id, find_entry(client, headers, track_id, "HSK2", "行1")["id"])
    assert xing["interpretations"][0]["headword"] == "行"
    assert xing["interpretations"][0]["senses"][0]["pos"] == []
    assert xing["interpretations"][0]["senses"][0]["pos_missing"] is True
    study = entry_detail(client, headers, track_id, find_entry(client, headers, track_id, "HSK3", "学习")["id"])
    assert study["source"]["raw_pos"] is None
    assert study["interpretations"][0]["senses"][0]["pos"][0]["origin"] == "editorial"

    # Awaiting-review records expose official fields only.
    friend = entry_detail(client, headers, track_id, find_entry(client, headers, track_id, "HSK4", "朋友")["id"])
    assert friend["interpretations"][0]["senses"] == []
    assert friend["interpretations"][0]["awaiting_sense_review"] is True
    hello = entry_detail(client, headers, track_id, find_entry(client, headers, track_id, "HSK4", "你好")["id"])
    assert hello["interpretations"][0]["senses"] == []  # draft sense hidden
    who = entry_detail(client, headers, track_id, find_entry(client, headers, track_id, "HSK6", "谁")["id"])
    assert who["source"]["review_status"] == "ambiguous"
    assert who["interpretations"] == []

    # Save a chosen sense; repeating is idempotent; a different sense is separate.
    long_saved = save(client, headers, track_id, chang["id"], senses["long"]["mapping_id"])
    assert long_saved.status_code == 200, long_saved.text
    assert long_saved.json()["created"] is True
    again = save(client, headers, track_id, chang["id"], senses["long"]["mapping_id"])
    assert again.json() == {
        "created": False,
        "vocabulary_id": long_saved.json()["vocabulary_id"],
        "reason": "already_saved",
    }
    grow_saved = save(client, headers, track_id, chang["id"], senses["grow"]["mapping_id"])
    assert grow_saved.json()["created"] is True

    saved_ids = [long_saved.json()["vocabulary_id"], grow_saved.json()["vocabulary_id"]]
    for level, word in (("HSK1", "爱"), ("HSK3", "学习"), ("HSK6", "吃")):
        entry = entry_detail(client, headers, track_id, find_entry(client, headers, track_id, level, word)["id"])
        sense = entry["interpretations"][0]["senses"][0]
        response = save(client, headers, track_id, entry["source"]["id"], sense["mapping_id"])
        assert response.json()["created"] is True, response.text
        saved_ids.append(response.json()["vocabulary_id"])

    vocab = client.get(f"/api/v1/vocabularies/{long_saved.json()['vocabulary_id']}", headers=headers)
    assert vocab.status_code == 200, vocab.text
    item = vocab.json()
    assert (item["word"], item["ipa"], item["meaning"], item["translation"]) == ("长", "cháng", "long", "dài")
    assert item["part_of_speech"] == "adjective"
    assert item["level_code"] == "HSK2"
    assert item["catalog_snapshot"]["source"]["record_id"] == "103"
    xing_vocab_detail = xing["interpretations"][0]["senses"][0]
    xing_saved = save(client, headers, track_id, xing["source"]["id"], xing_vocab_detail["mapping_id"])
    assert xing_saved.json()["created"] is True
    xing_item = client.get(f"/api/v1/vocabularies/{xing_saved.json()['vocabulary_id']}", headers=headers).json()
    assert xing_item["word"] == "行"  # headword, not the raw "行1"
    assert xing_item["part_of_speech"] == "unspecified"
    assert xing_item["catalog_snapshot"]["sense"]["pos_missing"] is True
    saved_ids.append(xing_saved.json()["vocabulary_id"])

    # Review the saved Chinese word with the existing review flow.
    reviewed = client.post(
        f"/api/v1/vocabularies/{long_saved.json()['vocabulary_id']}/reviews",
        headers=headers,
        json={"is_correct": True},
    )
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["review_count"] == 1

    # Exercise with the existing (AI-generated, backend-graded) flow.
    provider = FakeExerciseProvider(
        {
            "exercises": [
                {
                    "exercise_type": "multiple_choice",
                    "prompt": "我_______我的家。",
                    "options": [
                        {"id": "A", "text": "爱"},
                        {"id": "B", "text": "长"},
                        {"id": "C", "text": "学习"},
                        {"id": "D", "text": "吃"},
                    ],
                    "correct_answer": "A",
                    "explanation": "爱 means to love.",
                    "target_vocabulary_id": saved_ids[2],
                }
            ]
        }
    )
    app.dependency_overrides[get_exercise_ai_provider] = lambda: provider
    try:
        generated = client.post(
            "/api/v1/ai/exercises/generate",
            headers=headers,
            json={"vocabulary_ids": saved_ids[:5], "exercise_type": "multiple_choice", "count": 1},
        )
    finally:
        app.dependency_overrides.pop(get_exercise_ai_provider, None)
    assert generated.status_code == 200, generated.text
    exercise = generated.json()["items"][0]
    answer = next(option["id"] for option in exercise["options"] if option["text"] == "爱")
    attempt = client.post(
        f"/api/v1/exercises/{exercise['id']}/attempts", headers=headers, json={"answer": answer}
    )
    assert attempt.status_code == 200, attempt.text
    assert attempt.json()["is_correct"] is True

    # A topic is shaped like an English vocabulary set: one row per meaning.
    talk = body["levels"][1]["topic_groups"][0]["topics"][0]
    talk_detail = client.get(f"/api/v1/catalog/hsk/{track_id}/topics/{talk['id']}", headers=headers).json()
    assert [(row["word"], row["pinyin"], row["translation"]) for row in talk_detail["entries"]] == [
        ("长", "cháng", "dài"),
        ("长", "zhǎng", "lớn lên"),
    ]
    assert all(row["is_added"] for row in talk_detail["entries"])
    assert talk_detail["import_status"] == "all"
    food_detail = client.get(f"/api/v1/catalog/hsk/{track_id}/topics/{food['id']}", headers=headers).json()
    assert food_detail["name_vi"] == "Ăn uống" and food_detail["description"] == "Đồ ăn, thức uống"
    assert food_detail["import_status"] == "none"
    assert food_detail["entries"][0]["part_of_speech"] == "noun"

    # Learn a whole topic, like starting an English vocabulary set.
    topic_entries = client.get(
        f"/api/v1/catalog/hsk/{track_id}/entries", params={"topic_id": food["id"]}, headers=headers
    ).json()
    assert [item["raw_word"] for item in topic_entries["items"]] == ["水"]
    assert topic_entries["topic"]["name_zh"] == "饮食"
    whole = client.post(f"/api/v1/catalog/hsk/{track_id}/topics/{food['id']}/save-all", headers=headers)
    assert whole.status_code == 200, whole.text
    assert whole.json() == {"created_count": 1, "skipped_count": 0}
    again_topic = client.post(
        f"/api/v1/catalog/hsk/{track_id}/topics/{food['id']}/save-all", headers=headers
    )
    assert again_topic.json() == {"created_count": 0, "skipped_count": 1}
    refreshed = client.get(f"/api/v1/catalog/hsk/{track_id}/levels", headers=headers).json()
    assert refreshed["levels"][0]["topic_groups"][1]["topics"][0]["saved_count"] == 1

    return {
        "long_vocabulary_id": long_saved.json()["vocabulary_id"],
        "grow_vocabulary_id": grow_saved.json()["vocabulary_id"],
        "chang_entry_id": chang["id"],
        "friend_entry_id": friend["source"]["id"],
        "saved_ids": saved_ids,
        "exercise_id": exercise["id"],
    }
