from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.models import (
    Language,
    LearningTrack,
    Vocabulary,
    VocabularyEntry,
    VocabularySet,
)

PASSWORD = "StrongPassword123!"


@pytest.fixture
def library(
    session_factory: sessionmaker[Session],
) -> dict[str, object]:
    with session_factory() as db:
        language = Language(code="en", name="English", native_name="English")
        track = LearningTrack(
            language=language,
            code="general-english",
            name="General English",
            level_framework="CEFR",
        )
        travel = VocabularySet(
            learning_track=track,
            name="Travel",
            description="Demo A2 travel set",
            level_code="A2",
            topic="Travel",
            order_index=1,
        )
        business = VocabularySet(
            learning_track=track,
            name="Work & Business",
            description="Demo B2 business set",
            level_code="B2",
            topic="Work & Business",
            order_index=2,
        )
        travel.entries = [
            VocabularyEntry(
                word="journey",
                normalized_word="journey",
                part_of_speech="noun",
                meaning="The act of travelling from one place to another.",
                translation="hành trình",
                example_sentences=["The journey took three hours."],
                order_index=0,
            ),
            VocabularyEntry(
                word="luggage",
                normalized_word="luggage",
                part_of_speech="noun",
                meaning="Bags used while travelling.",
                translation="hành lý",
                example_sentences=["Her luggage is ready."],
                order_index=1,
            ),
        ]
        business.entries = [
            VocabularyEntry(
                word="negotiate",
                normalized_word="negotiate",
                part_of_speech="verb",
                meaning="To discuss in order to reach an agreement.",
                translation="đàm phán",
                example_sentences=["They negotiated a contract."],
                order_index=0,
            ),
            VocabularyEntry(
                word="revenue",
                normalized_word="revenue",
                part_of_speech="noun",
                meaning="Money received by a business.",
                translation="doanh thu",
                example_sentences=["Revenue increased this year."],
                order_index=1,
            ),
            VocabularyEntry(
                word="efficient",
                normalized_word="efficient",
                part_of_speech="adjective",
                meaning="Working well without wasting resources.",
                translation="hiệu quả",
                example_sentences=["The process is efficient."],
                order_index=2,
            ),
        ]
        db.add_all([travel, business])
        db.commit()
        return {
            "track_id": track.id,
            "travel_set_id": travel.id,
            "travel_entry_ids": [entry.id for entry in travel.entries],
            "business_set_id": business.id,
            "business_entry_ids": [entry.id for entry in business.entries],
        }


def authenticate(client: TestClient, email: str = "learner@example.com") -> dict[str, str]:
    assert client.post(
        "/api/v1/auth/register", json={"email": email, "password": PASSWORD}
    ).status_code == 201
    login = client.post(
        "/api/v1/auth/login", json={"email": email, "password": PASSWORD}
    )
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_list_vocabulary_sets(client: TestClient, library: dict[str, object]) -> None:
    response = client.get("/api/v1/vocabulary-sets", headers=authenticate(client))
    assert response.status_code == 200
    assert response.json()["total"] == 2
    assert response.json()["items"][0]["entry_count"] > 0
    assert response.json()["items"][0]["import_status"] == "none"


def test_filter_sets_by_level(client: TestClient, library: dict[str, object]) -> None:
    response = client.get(
        "/api/v1/vocabulary-sets?level=B2", headers=authenticate(client)
    )
    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["level_code"] == "B2"


def test_filter_sets_by_topic(client: TestClient, library: dict[str, object]) -> None:
    response = client.get(
        "/api/v1/vocabulary-sets?topic=travel", headers=authenticate(client)
    )
    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["topic"] == "Travel"


def test_get_vocabulary_set_details(
    client: TestClient, library: dict[str, object]
) -> None:
    response = client.get(
        f"/api/v1/vocabulary-sets/{library['travel_set_id']}",
        headers=authenticate(client),
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Travel"
    assert len(response.json()["entries"]) == 2
    assert all(entry["is_added"] is False for entry in response.json()["entries"])


def test_catalog_entries_are_shared_not_user_owned(
    client: TestClient, library: dict[str, object]
) -> None:
    first = authenticate(client, "first@example.com")
    second = authenticate(client, "second@example.com")
    url = f"/api/v1/vocabulary-sets/{library['travel_set_id']}"
    first_ids = [entry["id"] for entry in client.get(url, headers=first).json()["entries"]]
    second_ids = [entry["id"] for entry in client.get(url, headers=second).json()["entries"]]
    assert first_ids == second_ids


def test_add_one_catalog_word_to_my_vocabulary(
    client: TestClient,
    library: dict[str, object],
    session_factory: sessionmaker[Session],
) -> None:
    headers = authenticate(client)
    entry_id = library["travel_entry_ids"][0]
    response = client.post(
        f"/api/v1/vocabulary-entries/{entry_id}/add-to-my-vocabulary",
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["created_count"] == 1
    with session_factory() as db:
        item = db.scalar(select(Vocabulary))
        assert item is not None
        assert item.source_vocabulary_entry_id == entry_id
        assert item.learning_status == "new"


def test_add_multiple_catalog_words(
    client: TestClient, library: dict[str, object]
) -> None:
    headers = authenticate(client)
    entry_ids = library["business_entry_ids"][:2]
    response = client.post(
        "/api/v1/vocabulary-entries/import",
        headers=headers,
        json={"entry_ids": [str(item) for item in entry_ids]},
    )
    assert response.status_code == 200
    assert response.json()["created_count"] == 2
    assert client.get("/api/v1/vocabularies", headers=headers).json()["total"] == 2


def test_add_whole_vocabulary_set(
    client: TestClient, library: dict[str, object]
) -> None:
    headers = authenticate(client)
    response = client.post(
        f"/api/v1/vocabulary-sets/{library['business_set_id']}/start-learning",
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["created_count"] == 3
    detail = client.get(
        f"/api/v1/vocabulary-sets/{library['business_set_id']}", headers=headers
    ).json()
    assert detail["import_status"] == "all"
    assert detail["added_count"] == detail["entry_count"]


def test_duplicate_import_is_idempotent(
    client: TestClient, library: dict[str, object]
) -> None:
    headers = authenticate(client)
    entry_id = library["travel_entry_ids"][0]
    url = f"/api/v1/vocabulary-entries/{entry_id}/add-to-my-vocabulary"
    assert client.post(url, headers=headers).json()["created_count"] == 1
    duplicate = client.post(url, headers=headers)
    assert duplicate.status_code == 200
    assert duplicate.json()["created_count"] == 0
    assert duplicate.json()["skipped_count"] == 1
    assert client.get("/api/v1/vocabularies", headers=headers).json()["total"] == 1


def test_imported_vocabulary_is_owned_only_by_authenticated_user(
    client: TestClient, library: dict[str, object]
) -> None:
    owner = authenticate(client, "owner@example.com")
    other = authenticate(client, "other@example.com")
    entry_id = library["travel_entry_ids"][0]
    client.post(
        f"/api/v1/vocabulary-entries/{entry_id}/add-to-my-vocabulary",
        headers=owner,
    )
    assert client.get("/api/v1/vocabularies", headers=owner).json()["total"] == 1
    assert client.get("/api/v1/vocabularies", headers=other).json()["total"] == 0


def test_user_a_import_does_not_change_user_b_library_state(
    client: TestClient, library: dict[str, object]
) -> None:
    first = authenticate(client, "first@example.com")
    second = authenticate(client, "second@example.com")
    set_id = library["travel_set_id"]
    client.post(f"/api/v1/vocabulary-sets/{set_id}/start-learning", headers=first)
    assert client.get(f"/api/v1/vocabulary-sets/{set_id}", headers=first).json()[
        "import_status"
    ] == "all"
    assert client.get(f"/api/v1/vocabulary-sets/{set_id}", headers=second).json()[
        "import_status"
    ] == "none"


def test_manual_vocabulary_creation_still_works(
    client: TestClient, library: dict[str, object]
) -> None:
    headers = authenticate(client)
    response = client.post(
        "/api/v1/vocabularies",
        headers=headers,
        json={
            "learning_track_id": str(library["track_id"]),
            "word": "custom",
            "part_of_speech": "adjective",
            "meaning": "Made for a particular person.",
            "translation": "tùy chỉnh",
            "example_sentences": [],
            "level_code": "B1",
            "topic": "Personal",
            "learning_status": "new",
        },
    )
    assert response.status_code == 201
    assert response.json()["source_vocabulary_entry_id"] is None
    assert response.json()["source_vocabulary_entry"] is None


def test_imported_vocabulary_exposes_source_without_user_id(
    client: TestClient, library: dict[str, object]
) -> None:
    headers = authenticate(client)
    entry_id = library["business_entry_ids"][0]
    client.post(
        f"/api/v1/vocabulary-entries/{entry_id}/add-to-my-vocabulary",
        headers=headers,
    )
    item = client.get("/api/v1/vocabularies", headers=headers).json()["items"][0]
    assert item["source_vocabulary_entry"]["vocabulary_set"]["name"] == "Work & Business"
    assert "user_id" not in item


def test_library_and_import_endpoints_require_authentication(
    client: TestClient, library: dict[str, object]
) -> None:
    assert client.get("/api/v1/vocabulary-sets").status_code == 401
    assert client.post(
        f"/api/v1/vocabulary-sets/{library['travel_set_id']}/start-learning"
    ).status_code == 401


def test_library_import_skips_overlapping_personal_sense(
    client: TestClient, library: dict[str, object]
) -> None:
    headers = authenticate(client)
    entry_id = library["travel_entry_ids"][0]
    detail = client.get(
        f"/api/v1/vocabulary-sets/{library['travel_set_id']}", headers=headers
    ).json()
    entry = next(item for item in detail["entries"] if item["id"] == str(entry_id))
    manual = client.post(
        "/api/v1/vocabularies",
        headers=headers,
        json={
            "learning_track_id": str(library["track_id"]),
            "word": entry["word"].upper(),
            "part_of_speech": entry["part_of_speech"],
            "meaning": "A deliberately different definition.",
            "translation": entry["translation"],
            "example_sentences": ["A manual example sentence."],
            "level_code": "A2",
            "topic": "Personal",
            "learning_status": "new",
        },
    )
    assert manual.status_code == 201

    imported = client.post(
        f"/api/v1/vocabulary-entries/{entry_id}/add-to-my-vocabulary",
        headers=headers,
    )
    assert imported.status_code == 200
    assert imported.json()["created_count"] == 0
    assert imported.json()["skipped_count"] == 1
    assert client.get("/api/v1/vocabularies", headers=headers).json()["total"] == 1
