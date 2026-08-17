from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from tests.test_vocabulary import authenticate, create_item, general_english_track_id


def test_topic_suggestions_are_normalized_and_scoped_to_current_user(
    client: TestClient, general_english_track_id: uuid.UUID
) -> None:
    first = authenticate(client, "topics-first@example.com")
    second = authenticate(client, "topics-second@example.com")
    create_item(client, first, general_english_track_id, word="career", topic="  Work   Life ")
    create_item(client, first, general_english_track_id, word="office", topic="work life")
    create_item(client, second, general_english_track_id, word="secret", topic="Private Topic")

    response = client.get("/api/v1/vocabularies/topics?q=WORK", headers=first)

    assert response.status_code == 200
    assert response.json()["items"] == [
        {"name": "Work Life", "vocabulary_count": 2}
    ]
    assert "Private Topic" not in response.text


def test_topic_suggestions_prioritize_prefix_matches(
    client: TestClient, general_english_track_id: uuid.UUID
) -> None:
    headers = authenticate(client)
    create_item(client, headers, general_english_track_id, word="team", topic="Team Work")
    create_item(client, headers, general_english_track_id, word="network", topic="Social Network")
    response = client.get("/api/v1/vocabularies/topics?q=team", headers=headers)
    assert response.json()["items"][0]["name"] == "Team Work"


def test_rename_topic_updates_only_matching_current_user_entries(
    client: TestClient, general_english_track_id: uuid.UUID
) -> None:
    owner = authenticate(client, "rename-owner@example.com")
    other = authenticate(client, "rename-other@example.com")
    first = create_item(client, owner, general_english_track_id, word="office", topic="Wrok")
    second = create_item(client, owner, general_english_track_id, word="career", topic=" wrok ")
    foreign = create_item(client, other, general_english_track_id, word="foreign", topic="Wrok")

    response = client.patch(
        "/api/v1/vocabularies/topics",
        headers=owner,
        json={"old_topic": "WROK", "new_topic": "Work"},
    )

    assert response.status_code == 200
    assert response.json()["updated_count"] == 2
    assert client.get(f"/api/v1/vocabularies/{first['id']}", headers=owner).json()["topic"] == "Work"
    assert client.get(f"/api/v1/vocabularies/{second['id']}", headers=owner).json()["topic"] == "Work"
    assert client.get(f"/api/v1/vocabularies/{foreign['id']}", headers=other).json()["topic"] == "Wrok"


def test_remove_topic_sets_topic_to_null_without_deleting_vocabulary(
    client: TestClient, general_english_track_id: uuid.UUID
) -> None:
    headers = authenticate(client)
    other = authenticate(client, "remove-other@example.com")
    item = create_item(client, headers, general_english_track_id, word="office", topic="Work")
    foreign = create_item(client, other, general_english_track_id, word="foreign", topic="Work")

    response = client.request(
        "DELETE",
        "/api/v1/vocabularies/topics",
        headers=headers,
        json={"topic": " work "},
    )

    assert response.status_code == 200
    assert response.json()["updated_count"] == 1
    saved = client.get(f"/api/v1/vocabularies/{item['id']}", headers=headers)
    assert saved.status_code == 200
    assert saved.json()["topic"] is None
    assert client.get(f"/api/v1/vocabularies/{foreign['id']}", headers=other).json()["topic"] == "Work"


def test_topic_endpoints_require_authentication(client: TestClient) -> None:
    assert client.get("/api/v1/vocabularies/topics").status_code == 401
