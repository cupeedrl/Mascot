from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.models import Vocabulary
from tests.test_vocabulary import (
    authenticate,
    create_item,
    general_english_track_id,
)


def _update_review_state(
    session_factory: sessionmaker[Session],
    vocabulary_id: str,
    **changes: object,
) -> None:
    with session_factory() as db:
        item = db.get(Vocabulary, uuid.UUID(vocabulary_id))
        assert item is not None
        for field, value in changes.items():
            setattr(item, field, value)
        db.commit()


def _assert_delay(value: str, expected: timedelta, *, tolerance_seconds: int = 5) -> None:
    scheduled = datetime.fromisoformat(value)
    if scheduled.tzinfo is None:
        # SQLite drops timezone metadata in tests; the service always writes UTC.
        scheduled = scheduled.replace(tzinfo=UTC)
    now = datetime.now(UTC)
    difference = scheduled.astimezone(UTC) - now
    assert expected - timedelta(seconds=tolerance_seconds) <= difference
    assert difference <= expected + timedelta(seconds=tolerance_seconds)


def test_due_query_returns_null_and_past_schedules_only_for_current_user(
    client: TestClient,
    general_english_track_id: uuid.UUID,
    session_factory: sessionmaker[Session],
) -> None:
    headers = authenticate(client)
    other_headers = authenticate(client, "other-reviewer@example.com")
    immediately_due = create_item(client, headers, general_english_track_id, word="Due now")
    past_due = create_item(client, headers, general_english_track_id, word="Past due")
    future = create_item(client, headers, general_english_track_id, word="Future")
    mastered = create_item(
        client,
        headers,
        general_english_track_id,
        word="Mastered",
        learning_status="mastered",
    )
    create_item(client, other_headers, general_english_track_id, word="Other user")
    _update_review_state(
        session_factory,
        past_due["id"],
        next_review_at=datetime.now(UTC) - timedelta(minutes=1),
    )
    _update_review_state(
        session_factory,
        future["id"],
        next_review_at=datetime.now(UTC) + timedelta(days=1),
    )

    response = client.get("/api/v1/vocabularies/due-for-review", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert {item["id"] for item in body["items"]} == {
        immediately_due["id"],
        past_due["id"],
    }
    assert mastered["id"] not in {item["id"] for item in body["items"]}


def test_correct_review_updates_counts_time_schedule_and_new_status(
    client: TestClient, general_english_track_id: uuid.UUID
) -> None:
    headers = authenticate(client)
    item = create_item(client, headers, general_english_track_id)

    response = client.post(
        f"/api/v1/vocabularies/{item['id']}/reviews",
        headers=headers,
        json={"is_correct": True},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["review_count"] == 1
    assert body["correct_count"] == 1
    assert body["incorrect_count"] == 0
    assert body["last_reviewed_at"] is not None
    assert body["learning_status"] == "learning"
    _assert_delay(body["next_review_at"], timedelta(days=1))


def test_correct_learning_item_progresses_to_review(
    client: TestClient, general_english_track_id: uuid.UUID
) -> None:
    headers = authenticate(client)
    item = create_item(
        client, headers, general_english_track_id, learning_status="learning"
    )

    response = client.post(
        f"/api/v1/vocabularies/{item['id']}/reviews",
        headers=headers,
        json={"is_correct": True},
    )

    body = response.json()
    assert body["learning_status"] == "review"
    _assert_delay(body["next_review_at"], timedelta(days=3))


def test_correct_review_item_progresses_to_mastered(
    client: TestClient, general_english_track_id: uuid.UUID
) -> None:
    headers = authenticate(client)
    item = create_item(
        client, headers, general_english_track_id, learning_status="review"
    )

    response = client.post(
        f"/api/v1/vocabularies/{item['id']}/reviews",
        headers=headers,
        json={"is_correct": True},
    )

    body = response.json()
    assert body["learning_status"] == "mastered"
    assert body["next_review_at"] is None


def test_incorrect_review_updates_count_and_schedules_soon(
    client: TestClient, general_english_track_id: uuid.UUID
) -> None:
    headers = authenticate(client)
    item = create_item(
        client, headers, general_english_track_id, learning_status="review"
    )

    response = client.post(
        f"/api/v1/vocabularies/{item['id']}/reviews",
        headers=headers,
        json={"is_correct": False},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["review_count"] == 1
    assert body["correct_count"] == 0
    assert body["incorrect_count"] == 1
    assert body["last_reviewed_at"] is not None
    assert body["learning_status"] == "learning"
    _assert_delay(body["next_review_at"], timedelta(hours=1))


def test_user_cannot_review_another_users_vocabulary(
    client: TestClient, general_english_track_id: uuid.UUID
) -> None:
    owner_headers = authenticate(client, "review-owner@example.com")
    attacker_headers = authenticate(client, "review-attacker@example.com")
    item = create_item(client, owner_headers, general_english_track_id)

    response = client.post(
        f"/api/v1/vocabularies/{item['id']}/reviews",
        headers=attacker_headers,
        json={"is_correct": True},
    )

    assert response.status_code == 404


def test_future_review_cannot_be_submitted_early(
    client: TestClient,
    general_english_track_id: uuid.UUID,
    session_factory: sessionmaker[Session],
) -> None:
    headers = authenticate(client)
    item = create_item(client, headers, general_english_track_id)
    _update_review_state(
        session_factory,
        item["id"],
        next_review_at=datetime.now(UTC) + timedelta(days=1),
    )

    response = client.post(
        f"/api/v1/vocabularies/{item['id']}/reviews",
        headers=headers,
        json={"is_correct": True},
    )

    assert response.status_code == 409


def test_no_review_due_returns_empty_queue(
    client: TestClient,
    general_english_track_id: uuid.UUID,
    session_factory: sessionmaker[Session],
) -> None:
    headers = authenticate(client)
    item = create_item(client, headers, general_english_track_id)
    _update_review_state(
        session_factory,
        item["id"],
        next_review_at=datetime.now(UTC) + timedelta(days=1),
    )

    response = client.get("/api/v1/vocabularies/due-for-review", headers=headers)

    assert response.status_code == 200
    assert response.json()["total"] == 0
    assert response.json()["items"] == []
