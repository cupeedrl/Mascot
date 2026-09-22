from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.models import Language, LearningTrack, Vocabulary

PASSWORD = "StrongPassword123!"


@pytest.fixture
def general_english_track_id(
    session_factory: sessionmaker[Session],
) -> uuid.UUID:
    with session_factory() as db:
        language = Language(code="en", name="English", native_name="English")
        track = LearningTrack(
            language=language,
            code="general-english",
            name="General English",
            description="General English learning for V1",
            level_framework="CEFR",
        )
        db.add(track)
        db.commit()
        return track.id


def authenticate(client: TestClient, email: str = "learner@example.com") -> dict[str, str]:
    registration = client.post(
        "/api/v1/auth/register", json={"email": email, "password": PASSWORD}
    )
    assert registration.status_code == 201
    login = client.post(
        "/api/v1/auth/login", json={"email": email, "password": PASSWORD}
    )
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def vocabulary_payload(track_id: uuid.UUID, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "learning_track_id": str(track_id),
        "word": "Solely",
        "part_of_speech": "adverb",
        "meaning": "Only and not involving anyone or anything else.",
        "translation": "chỉ, duy nhất",
        "translation_language_code": "vi",
        "example_sentences": ["The decision was solely hers."],
        "level_code": "B2",
        "topic": "Work",
        "learning_status": "new",
    }
    payload.update(overrides)
    return payload


def create_item(
    client: TestClient,
    headers: dict[str, str],
    track_id: uuid.UUID,
    **overrides: object,
) -> dict[str, object]:
    response = client.post(
        "/api/v1/vocabularies",
        headers=headers,
        json=vocabulary_payload(track_id, **overrides),
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_catalog_returns_only_active_general_english(
    client: TestClient, general_english_track_id: uuid.UUID
) -> None:
    headers = authenticate(client)

    languages = client.get("/api/v1/languages", headers=headers)
    tracks = client.get("/api/v1/learning-tracks?language_code=en", headers=headers)

    assert languages.status_code == 200
    assert [item["code"] for item in languages.json()] == ["en"]
    assert tracks.status_code == 200
    assert tracks.json()[0]["id"] == str(general_english_track_id)
    assert tracks.json()[0]["code"] == "general-english"
    assert tracks.json()[0]["language"]["code"] == "en"


def test_create_vocabulary_successfully(
    client: TestClient, general_english_track_id: uuid.UUID
) -> None:
    headers = authenticate(client)

    response = client.post(
        "/api/v1/vocabularies",
        headers=headers,
        json=vocabulary_payload(general_english_track_id),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["word"] == "Solely"
    assert body["normalized_word"] == "solely"
    assert body["learning_track"]["language"]["code"] == "en"
    assert body["review_count"] == 0
    assert "user_id" not in body


def test_create_vocabulary_requires_authentication(
    client: TestClient, general_english_track_id: uuid.UUID
) -> None:
    response = client.post(
        "/api/v1/vocabularies", json=vocabulary_payload(general_english_track_id)
    )
    assert response.status_code == 401


def test_invalid_cefr_level_is_rejected(
    client: TestClient, general_english_track_id: uuid.UUID
) -> None:
    headers = authenticate(client)
    response = client.post(
        "/api/v1/vocabularies",
        headers=headers,
        json=vocabulary_payload(general_english_track_id, level_code="Z9"),
    )
    assert response.status_code == 422


def test_invalid_learning_status_is_rejected(
    client: TestClient, general_english_track_id: uuid.UUID
) -> None:
    headers = authenticate(client)
    response = client.post(
        "/api/v1/vocabularies",
        headers=headers,
        json=vocabulary_payload(general_english_track_id, learning_status="forgotten"),
    )
    assert response.status_code == 422


def test_list_vocabulary_is_scoped_to_current_user(
    client: TestClient, general_english_track_id: uuid.UUID
) -> None:
    first_headers = authenticate(client, "first@example.com")
    second_headers = authenticate(client, "second@example.com")
    create_item(client, first_headers, general_english_track_id, word="First")
    create_item(client, second_headers, general_english_track_id, word="Second")

    response = client.get("/api/v1/vocabularies", headers=first_headers)

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["word"] == "First"


def test_get_vocabulary_by_id(
    client: TestClient, general_english_track_id: uuid.UUID
) -> None:
    headers = authenticate(client)
    item = create_item(client, headers, general_english_track_id)

    response = client.get(f"/api/v1/vocabularies/{item['id']}", headers=headers)

    assert response.status_code == 200
    assert response.json()["id"] == item["id"]


def test_update_vocabulary_and_recompute_normalized_word(
    client: TestClient, general_english_track_id: uuid.UUID
) -> None:
    headers = authenticate(client)
    item = create_item(client, headers, general_english_track_id)

    response = client.patch(
        f"/api/v1/vocabularies/{item['id']}",
        headers=headers,
        json={"word": "  Exclusively  ", "learning_status": "learning"},
    )

    assert response.status_code == 200
    assert response.json()["word"] == "Exclusively"
    assert response.json()["normalized_word"] == "exclusively"
    assert response.json()["learning_status"] == "learning"


def test_ownership_fields_cannot_be_submitted(
    client: TestClient, general_english_track_id: uuid.UUID
) -> None:
    headers = authenticate(client)
    payload = vocabulary_payload(general_english_track_id, user_id=str(uuid.uuid4()))
    assert client.post(
        "/api/v1/vocabularies", headers=headers, json=payload
    ).status_code == 422


def test_delete_vocabulary(
    client: TestClient,
    general_english_track_id: uuid.UUID,
    session_factory: sessionmaker[Session],
) -> None:
    headers = authenticate(client)
    item = create_item(client, headers, general_english_track_id)

    response = client.delete(f"/api/v1/vocabularies/{item['id']}", headers=headers)

    assert response.status_code == 204
    with session_factory() as db:
        assert db.scalar(select(Vocabulary).where(Vocabulary.id == uuid.UUID(item["id"]))) is None


def test_search_matches_word_meaning_and_translation(
    client: TestClient, general_english_track_id: uuid.UUID
) -> None:
    headers = authenticate(client)
    create_item(client, headers, general_english_track_id, word="Solely")
    create_item(
        client,
        headers,
        general_english_track_id,
        word="Commitment",
        meaning="A strong dedication to something.",
        translation="sự tận tâm",
    )

    word_result = client.get("/api/v1/vocabularies?q=sole", headers=headers).json()
    meaning_result = client.get("/api/v1/vocabularies?q=dedication", headers=headers).json()
    translation_result = client.get(
        "/api/v1/vocabularies?q=tận tâm", headers=headers
    ).json()

    assert word_result["total"] == 1
    assert meaning_result["total"] == 1
    assert translation_result["total"] == 1


def test_filter_by_learning_status(
    client: TestClient, general_english_track_id: uuid.UUID
) -> None:
    headers = authenticate(client)
    create_item(client, headers, general_english_track_id, learning_status="learning")
    create_item(client, headers, general_english_track_id, word="Done", learning_status="mastered")
    result = client.get(
        "/api/v1/vocabularies?learning_status=mastered", headers=headers
    ).json()
    assert result["total"] == 1
    assert result["items"][0]["word"] == "Done"


def test_filter_by_cefr_level(
    client: TestClient, general_english_track_id: uuid.UUID
) -> None:
    headers = authenticate(client)
    create_item(client, headers, general_english_track_id, level_code="B2")
    create_item(client, headers, general_english_track_id, word="Basic", level_code="A1")
    result = client.get("/api/v1/vocabularies?level=A1", headers=headers).json()
    assert result["total"] == 1
    assert result["items"][0]["level_code"] == "A1"


def test_filter_by_topic_is_case_insensitive(
    client: TestClient, general_english_track_id: uuid.UUID
) -> None:
    headers = authenticate(client)
    create_item(client, headers, general_english_track_id, topic="Work")
    create_item(client, headers, general_english_track_id, word="Trip", topic="Travel")
    result = client.get("/api/v1/vocabularies?topic=work", headers=headers).json()
    assert result["total"] == 1
    assert result["items"][0]["topic"] == "Work"


def test_pagination_happens_in_query(
    client: TestClient, general_english_track_id: uuid.UUID
) -> None:
    headers = authenticate(client)
    for index in range(5):
        create_item(client, headers, general_english_track_id, word=f"Word {index}")

    first = client.get("/api/v1/vocabularies?page=1&page_size=2", headers=headers).json()
    third = client.get("/api/v1/vocabularies?page=3&page_size=2", headers=headers).json()

    assert first["total"] == 5
    assert first["total_pages"] == 3
    assert len(first["items"]) == 2
    assert len(third["items"]) == 1


def test_normalized_word_trims_and_casefolds(
    client: TestClient, general_english_track_id: uuid.UUID
) -> None:
    headers = authenticate(client)
    item = create_item(client, headers, general_english_track_id, word="  Solely  ")
    assert item["word"] == "Solely"
    assert item["normalized_word"] == "solely"


def _two_users_and_foreign_item(
    client: TestClient, track_id: uuid.UUID
) -> tuple[dict[str, str], dict[str, object]]:
    owner_headers = authenticate(client, "owner@example.com")
    attacker_headers = authenticate(client, "attacker@example.com")
    foreign_item = create_item(client, owner_headers, track_id)
    return attacker_headers, foreign_item


def test_user_cannot_read_another_users_vocabulary(
    client: TestClient, general_english_track_id: uuid.UUID
) -> None:
    attacker_headers, item = _two_users_and_foreign_item(client, general_english_track_id)
    response = client.get(
        f"/api/v1/vocabularies/{item['id']}", headers=attacker_headers
    )
    assert response.status_code == 404


def test_user_cannot_update_another_users_vocabulary(
    client: TestClient, general_english_track_id: uuid.UUID
) -> None:
    attacker_headers, item = _two_users_and_foreign_item(client, general_english_track_id)
    response = client.patch(
        f"/api/v1/vocabularies/{item['id']}",
        headers=attacker_headers,
        json={"word": "Stolen"},
    )
    assert response.status_code == 404


def test_user_cannot_delete_another_users_vocabulary(
    client: TestClient, general_english_track_id: uuid.UUID
) -> None:
    attacker_headers, item = _two_users_and_foreign_item(client, general_english_track_id)
    response = client.delete(
        f"/api/v1/vocabularies/{item['id']}", headers=attacker_headers
    )
    assert response.status_code == 404


def test_exact_duplicate_vocabulary_sense_is_rejected(
    client: TestClient, general_english_track_id: uuid.UUID
) -> None:
    headers = authenticate(client)
    existing = create_item(client, headers, general_english_track_id, word="hand")

    response = client.post(
        "/api/v1/vocabularies",
        headers=headers,
        json=vocabulary_payload(general_english_track_id, word="hand"),
    )

    assert response.status_code == 409
    assert response.json()["detail"] == {
        "message": (
            "This word already exists in My Vocabulary with the same or overlapping "
            "meaning. Edit the existing entry or add a genuinely different sense."
        ),
        "existing_vocabulary_id": existing["id"],
    }


def test_duplicate_response_identifies_the_entry_that_caused_the_conflict(
    client: TestClient, general_english_track_id: uuid.UUID
) -> None:
    headers = authenticate(client)
    create_item(
        client,
        headers,
        general_english_track_id,
        word="bank",
        meaning="The land beside a river.",
        translation="bờ sông",
    )
    matching = create_item(
        client,
        headers,
        general_english_track_id,
        word="bank",
        meaning="A business that keeps and lends money.",
        translation="ngân hàng",
    )

    response = client.post(
        "/api/v1/vocabularies",
        headers=headers,
        json=vocabulary_payload(
            general_english_track_id,
            word="BANK",
            meaning="A financial institution.",
            translation="ngân hàng",
        ),
    )

    assert response.status_code == 409
    assert response.json()["detail"]["existing_vocabulary_id"] == matching["id"]


def test_case_insensitive_word_duplicate_is_rejected(
    client: TestClient, general_english_track_id: uuid.UUID
) -> None:
    headers = authenticate(client)
    create_item(client, headers, general_english_track_id, word="  Hand  ")
    response = client.post(
        "/api/v1/vocabularies",
        headers=headers,
        json=vocabulary_payload(general_english_track_id, word="HAND"),
    )
    assert response.status_code == 409


def test_part_of_speech_does_not_bypass_duplicate_rule(
    client: TestClient, general_english_track_id: uuid.UUID
) -> None:
    headers = authenticate(client)
    create_item(client, headers, general_english_track_id, word="hand", part_of_speech="noun")
    response = client.post(
        "/api/v1/vocabularies",
        headers=headers,
        json=vocabulary_payload(
            general_english_track_id,
            word="hand",
            part_of_speech="verb",
        ),
    )
    assert response.status_code == 409


def test_same_translation_with_different_definition_is_rejected(
    client: TestClient, general_english_track_id: uuid.UUID
) -> None:
    headers = authenticate(client)
    create_item(
        client,
        headers,
        general_english_track_id,
        word="hand",
        meaning="The body part at the end of an arm.",
        translation="bàn tay",
    )
    response = client.post(
        "/api/v1/vocabularies",
        headers=headers,
        json=vocabulary_payload(
            general_english_track_id,
            word="hand",
            meaning="Help given to another person.",
            translation="  BÀN   TAY  ",
        ),
    )
    assert response.status_code == 409


def test_same_definition_with_different_translation_is_rejected(
    client: TestClient, general_english_track_id: uuid.UUID
) -> None:
    headers = authenticate(client)
    create_item(
        client,
        headers,
        general_english_track_id,
        word="hand",
        meaning="Help given to another person.",
        translation="sự giúp đỡ",
    )
    response = client.post(
        "/api/v1/vocabularies",
        headers=headers,
        json=vocabulary_payload(
            general_english_track_id,
            word="hand",
            meaning="  HELP  given to another person. ",
            translation="người làm thuê",
        ),
    )
    assert response.status_code == 409


def test_same_word_with_both_definition_and_translation_different_is_allowed(
    client: TestClient, general_english_track_id: uuid.UUID
) -> None:
    headers = authenticate(client)
    create_item(
        client,
        headers,
        general_english_track_id,
        word="hand",
        meaning="The body part at the end of an arm.",
        translation="bàn tay",
    )
    response = client.post(
        "/api/v1/vocabularies",
        headers=headers,
        json=vocabulary_payload(
            general_english_track_id,
            word="hand",
            meaning="A person who performs physical work.",
            translation="người làm thuê",
        ),
    )
    assert response.status_code == 201


def test_edit_duplicate_check_excludes_the_current_record(
    client: TestClient, general_english_track_id: uuid.UUID
) -> None:
    headers = authenticate(client)
    item = create_item(client, headers, general_english_track_id, word="hand")
    response = client.patch(
        f"/api/v1/vocabularies/{item['id']}",
        headers=headers,
        json={"word": "HAND", "meaning": item["meaning"], "translation": item["translation"]},
    )
    assert response.status_code == 200


def test_vocabulary_accepts_at_most_one_example_sentence(
    client: TestClient, general_english_track_id: uuid.UUID
) -> None:
    headers = authenticate(client)
    one = client.post(
        "/api/v1/vocabularies",
        headers=headers,
        json=vocabulary_payload(
            general_english_track_id,
            example_sentences=["One natural example."],
        ),
    )
    many = client.post(
        "/api/v1/vocabularies",
        headers=headers,
        json=vocabulary_payload(
            general_english_track_id,
            word="different",
            example_sentences=["First example.", "Second example."],
        ),
    )
    assert one.status_code == 201
    assert one.json()["example_sentences"] == ["One natural example."]
    assert many.status_code == 422


def test_vocabulary_ipa_saved_and_updated(
    client: TestClient, general_english_track_id: uuid.UUID
) -> None:
    headers = authenticate(client)
    item = create_item(
        client,
        headers,
        general_english_track_id,
        word="solely",
        ipa="/ˈsəʊl.li/",
    )
    assert item["ipa"] == "/ˈsəʊl.li/"

    # Check detail
    detail = client.get(f"/api/v1/vocabularies/{item['id']}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["ipa"] == "/ˈsəʊl.li/"

    # Check update
    updated = client.patch(
        f"/api/v1/vocabularies/{item['id']}",
        headers=headers,
        json={"ipa": "/ˈsoʊl.li/"},
    )
    assert updated.status_code == 200
    assert updated.json()["ipa"] == "/ˈsoʊl.li/"


def test_topic_fallback_to_khac_when_omitted_or_none(
    client: TestClient, general_english_track_id: uuid.UUID
) -> None:
    headers = authenticate(client)
    item = create_item(
        client,
        headers,
        general_english_track_id,
        word="wander",
        topic=None,
    )
    assert item["topic"] == "Khác"


def test_duplicate_rule_not_bypassed_by_different_part_of_speech(
    client: TestClient, general_english_track_id: uuid.UUID
) -> None:
    headers = authenticate(client)
    create_item(
        client,
        headers,
        general_english_track_id,
        word="run",
        part_of_speech="verb",
        meaning="Move rapidly on foot.",
        translation="chạy",
    )
    # Attempt to create duplicate with part_of_speech="noun"
    duplicate = client.post(
        "/api/v1/vocabularies",
        headers=headers,
        json=vocabulary_payload(
            general_english_track_id,
            word="run",
            part_of_speech="noun",
            meaning="Move rapidly on foot.",
            translation="chạy",
        ),
    )
    assert duplicate.status_code == 409

