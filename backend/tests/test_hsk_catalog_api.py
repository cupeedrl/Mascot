"""HSK catalog API behaviour on the default in-memory SQLite test database.

PostgreSQL-specific guarantees (composite FKs, NULLS NOT DISTINCT, partial
unique indexes, publication CHECKs, migration) are proven separately in
``tests/postgres/test_hsk_catalog_postgres.py``.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.catalog import hsk_import
from app.models import (
    CatalogRelease,
    CatalogSourceEntry,
    CatalogSourceMapping,
    Language,
    LearningTrack,
    Vocabulary,
    VocabularyEntry,
    VocabularySet,
)
from tests.hsk_fixtures import build_dataset
from tests.hsk_scenario import authenticate, import_and_publish, import_dataset, run_learner_flow


@pytest.fixture
def chinese_track(session_factory: sessionmaker[Session]) -> uuid.UUID:
    with session_factory() as db:
        language = Language(code="zh", name="Chinese", native_name="中文")
        track = LearningTrack(
            language=language, code="general-chinese", name="General Chinese", level_framework="HSK"
        )
        legacy = VocabularySet(
            learning_track=track,
            name="HSK 1 · Daily Foundations",
            level_code="HSK1",
            topic="Daily Life",
        )
        legacy.entries = [
            VocabularyEntry(
                word="水",
                normalized_word="水",
                ipa="shuǐ",
                part_of_speech="noun",
                meaning="water",
                translation="nước",
                example_sentences=["我想喝水。"],
            )
        ]
        db.add(legacy)
        db.commit()
        return track.id


def test_no_published_release_means_empty_catalog_without_fallback(
    client: TestClient, session_factory, chinese_track, tmp_path: Path
) -> None:
    import_dataset(session_factory, build_dataset(tmp_path / "draft"))  # draft only
    headers = authenticate(client, "draft@example.com")
    levels = client.get(f"/api/v1/catalog/hsk/{chinese_track}/levels", headers=headers).json()
    assert levels["release"] is None
    assert all(level["entry_count"] == 0 for level in levels["levels"])
    entries = client.get(f"/api/v1/catalog/hsk/{chinese_track}/entries", headers=headers).json()
    assert entries["items"] == [] and entries["release"] is None
    with session_factory() as db:
        release_id = db.scalar(select(CatalogRelease.id))
    # Ordinary users cannot preview drafts by id.
    preview = client.get(
        f"/api/v1/catalog/hsk/{chinese_track}/levels",
        params={"release_id": str(release_id)},
        headers=headers,
    )
    assert preview.status_code == 404
    # The legacy v1 library still serves the development set unchanged.
    legacy = client.get("/api/v1/vocabulary-sets", params={"level": "HSK1"}, headers=headers)
    assert legacy.status_code == 200 and legacy.json()["total"] == 1


def test_learner_flow_on_published_release(
    client: TestClient, session_factory, chinese_track, tmp_path: Path
) -> None:
    import_and_publish(session_factory, tmp_path)
    headers = authenticate(client, "hsk-learner@example.com")
    run_learner_flow(client, headers, chinese_track)


def test_unspecialized_and_draft_senses_are_not_saveable(
    client: TestClient, session_factory, chinese_track, tmp_path: Path
) -> None:
    import_and_publish(session_factory, tmp_path)
    headers = authenticate(client, "null-sense@example.com")
    with session_factory() as db:
        rows = db.execute(
            select(CatalogSourceEntry.id, CatalogSourceEntry.raw_word, CatalogSourceMapping.id)
            .join(CatalogSourceMapping, CatalogSourceMapping.source_entry_id == CatalogSourceEntry.id)
            .where(CatalogSourceEntry.raw_word.in_(("朋友", "你好")))
        ).all()
    codes = {}
    for entry_id, word, mapping_id in rows:
        response = client.post(
            f"/api/v1/catalog/hsk/{chinese_track}/entries/{entry_id}/save",
            headers=headers,
            json={"mapping_id": str(mapping_id)},
        )
        assert response.status_code == 409
        codes[word] = response.json()["detail"]["code"]
    assert codes == {"朋友": "sense_required", "你好": "sense_not_saveable"}
    with session_factory() as db:
        assert db.scalar(select(Vocabulary.id)) is None


def test_selected_meanings_import_like_english_sets(
    client: TestClient, session_factory, chinese_track, tmp_path: Path
) -> None:
    import_and_publish(session_factory, tmp_path)
    headers = authenticate(client, "select-senses@example.com")
    with session_factory() as db:
        mapping_ids = [
            str(mapping_id)
            for mapping_id in db.scalars(
                select(CatalogSourceMapping.id)
                .join(CatalogSourceEntry, CatalogSourceEntry.id == CatalogSourceMapping.source_entry_id)
                .where(CatalogSourceEntry.raw_word == "长")
            )
        ]
    first = client.post(
        f"/api/v1/catalog/hsk/{chinese_track}/senses/import",
        headers=headers,
        json={"mapping_ids": mapping_ids},
    )
    assert first.status_code == 200, first.text
    assert first.json()["created_count"] == 2
    again = client.post(
        f"/api/v1/catalog/hsk/{chinese_track}/senses/import",
        headers=headers,
        json={"mapping_ids": mapping_ids},
    )
    assert again.json()["created_count"] == 0 and again.json()["skipped_count"] == 2
    missing = client.post(
        f"/api/v1/catalog/hsk/{chinese_track}/senses/import",
        headers=headers,
        json={"mapping_ids": [str(uuid.uuid4())]},
    )
    assert missing.status_code == 404


def test_overlap_with_existing_personal_word_is_not_duplicated(
    client: TestClient, session_factory, chinese_track, tmp_path: Path
) -> None:
    import_and_publish(session_factory, tmp_path)
    headers = authenticate(client, "overlap@example.com")
    with session_factory() as db:
        legacy_set_id = db.scalar(select(VocabularySet.id))
    assert client.post(
        f"/api/v1/vocabulary-sets/{legacy_set_id}/start-learning", headers=headers
    ).json()["created_count"] == 1
    water = client.get(
        f"/api/v1/catalog/hsk/{chinese_track}/entries", params={"q": "水"}, headers=headers
    ).json()["items"][0]
    detail = client.get(
        f"/api/v1/catalog/hsk/{chinese_track}/entries/{water['id']}", headers=headers
    ).json()
    mapping_id = detail["interpretations"][0]["senses"][0]["mapping_id"]
    response = client.post(
        f"/api/v1/catalog/hsk/{chinese_track}/entries/{water['id']}/save",
        headers=headers,
        json={"mapping_id": mapping_id},
    )
    assert response.json()["created"] is False
    assert response.json()["reason"] == "overlapping_personal_word"


def test_catalog_edit_and_retirement_preserve_snapshot_and_progress(
    client: TestClient, session_factory, chinese_track, tmp_path: Path
) -> None:
    import_and_publish(session_factory, tmp_path)
    headers = authenticate(client, "preserve@example.com")
    ids = run_learner_flow(client, headers, chinese_track)
    before = client.get(f"/api/v1/vocabularies/{ids['grow_vocabulary_id']}", headers=headers).json()

    # Retire a sense and a source record in the live catalog.
    with session_factory() as db:
        vocabulary = db.get(Vocabulary, uuid.UUID(ids["grow_vocabulary_id"]))
        from app.models import LexicalSense

        sense = db.get(LexicalSense, vocabulary.catalog_sense_id)
        sense.status = "retired"
        sense.gloss_en = "changed after save"
        db.commit()
        hsk_import.retire_source_entry(db, uuid.UUID(ids["chang_entry_id"]))

    after = client.get(f"/api/v1/vocabularies/{ids['grow_vocabulary_id']}", headers=headers).json()
    for field in ("word", "ipa", "meaning", "translation", "review_count", "learning_status", "catalog_snapshot"):
        assert after[field] == before[field]
    listing = client.get(
        f"/api/v1/catalog/hsk/{chinese_track}/entries", params={"level": "HSK2"}, headers=headers
    ).json()
    assert "长" not in [item["raw_word"] for item in listing["items"]]
    detail = client.get(
        f"/api/v1/catalog/hsk/{chinese_track}/entries/{ids['chang_entry_id']}", headers=headers
    ).json()
    assert detail["source"]["review_status"] == "retired"
    assert all(not s["saveable"] for i in detail["interpretations"] for s in i["senses"])


def test_large_topics_are_split_into_study_sized_parts(
    client: TestClient, session_factory, chinese_track, tmp_path: Path, monkeypatch
) -> None:
    import copy

    from app.services import hsk_catalog as service
    from tests.hsk_fixtures import REVIEW

    review = copy.deepcopy(REVIEW)
    review["entry_topics"].append(
        {"source_record_id": "101", "topic_path": ["日常生活", "饮食"], "origin": "editorial", "review_status": "approved"}
    )
    import_and_publish(session_factory, tmp_path, review=review)
    monkeypatch.setattr(service, "PART_SIZE", 1)
    headers = authenticate(client, "parts@example.com")
    base = f"/api/v1/catalog/hsk/{chinese_track}"

    def food_cards():
        levels = client.get(f"{base}/levels", headers=headers).json()
        return [card for card in levels["levels"][0]["topic_groups"][1]["topics"] if card["name_zh"] == "饮食"]

    cards = food_cards()
    assert [(c["part"], c["part_count"], c["entry_count"]) for c in cards] == [(1, 2, 1), (2, 2, 1)]
    topic_id = cards[0]["id"]
    first = client.get(f"{base}/topics/{topic_id}", params={"part": 1}, headers=headers).json()
    second = client.get(f"{base}/topics/{topic_id}", params={"part": 2}, headers=headers).json()
    assert [row["word"] for row in first["entries"]] == ["爱"]  # serial 1
    assert [row["word"] for row in second["entries"]] == ["水"]  # serial 2
    assert (second["part"], second["part_count"]) == (2, 2)
    assert client.get(f"{base}/topics/{topic_id}", params={"part": 3}, headers=headers).status_code == 404

    saved = client.post(f"{base}/topics/{topic_id}/save-all", params={"part": 2}, headers=headers)
    assert saved.json() == {"created_count": 1, "skipped_count": 0}
    assert [c["saved_count"] for c in food_cards()] == [0, 1]
