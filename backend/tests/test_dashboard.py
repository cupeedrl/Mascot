from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.models import ExerciseAttempt, User, Vocabulary
from app.services.dashboard import get_dashboard_snapshot
from tests.test_exercises import _create_exercise
from tests.test_vocabulary import authenticate, create_item, general_english_track_id


def _user_id(session_factory: sessionmaker[Session], email: str) -> uuid.UUID:
    with session_factory() as db:
        user = db.scalar(select(User).where(User.normalized_email == email.casefold()))
        assert user is not None
        return user.id


def _update_vocabulary(
    session_factory: sessionmaker[Session], vocabulary_id: str, **changes: object
) -> None:
    with session_factory() as db:
        item = db.get(Vocabulary, uuid.UUID(vocabulary_id))
        assert item is not None
        for field, value in changes.items():
            setattr(item, field, value)
        db.commit()


def test_empty_user_dashboard_has_zero_metrics(client: TestClient) -> None:
    headers = authenticate(client, "empty-dashboard@example.com")

    response = client.get("/api/v1/dashboard", headers=headers)

    assert response.status_code == 200
    assert response.json() == {
        "total_vocabulary": 0,
        "new_words": 0,
        "learning_words": 0,
        "review_words": 0,
        "mastered_words": 0,
        "words_due_for_review": 0,
        "exercises_completed": 0,
        "correct_exercise_attempts": 0,
        "incorrect_exercise_attempts": 0,
        "exercise_accuracy": 0.0,
        "current_streak": 0,
        "longest_streak": 0,
        "recent_active_dates": [],
        "recently_added_vocabulary": [],
    }


def test_streak_counts_consecutive_meaningful_actions_once_per_day(
    client: TestClient,
    general_english_track_id: uuid.UUID,
    session_factory: sessionmaker[Session],
) -> None:
    email = "dashboard-streak@example.com"
    headers = authenticate(client, email)
    now = datetime(2026, 8, 18, 12, tzinfo=UTC)
    first = create_item(client, headers, general_english_track_id, word="Streak first")
    second = create_item(client, headers, general_english_track_id, word="Streak second")
    _update_vocabulary(
        session_factory,
        str(first["id"]),
        created_at=now - timedelta(days=2),
        last_reviewed_at=now - timedelta(days=1),
    )
    _update_vocabulary(
        session_factory,
        str(second["id"]),
        created_at=now - timedelta(days=1),
    )
    same_day = create_item(
        client, headers, general_english_track_id, word="Streak same day"
    )
    _update_vocabulary(
        session_factory,
        str(same_day["id"]),
        created_at=now,
        last_reviewed_at=now,
    )

    exercise_id = _create_exercise(
        session_factory,
        user_id=_user_id(session_factory, email),
        track_id=general_english_track_id,
    )
    attempt = client.post(
        f"/api/v1/exercises/{exercise_id}/attempts",
        headers=headers,
        json={"answer": "A"},
    )
    assert attempt.status_code == 200
    with session_factory() as db:
        stored_attempt = db.get(ExerciseAttempt, uuid.UUID(attempt.json()["id"]))
        assert stored_attempt is not None
        stored_attempt.completed_at = now
        db.commit()
        snapshot = get_dashboard_snapshot(db, _user_id(session_factory, email), now=now)

    assert snapshot.current_streak == 3
    assert snapshot.longest_streak == 3
    assert snapshot.recent_active_dates == [
        (now - timedelta(days=2)).date(),
        (now - timedelta(days=1)).date(),
        now.date(),
    ]


def test_streak_break_and_same_day_actions(
    client: TestClient,
    general_english_track_id: uuid.UUID,
    session_factory: sessionmaker[Session],
) -> None:
    email = "dashboard-streak-break@example.com"
    headers = authenticate(client, email)
    now = datetime(2026, 8, 18, 12, tzinfo=UTC)
    for index, days_ago in enumerate([4, 3, 2]):
        item = create_item(
            client,
            headers,
            general_english_track_id,
            word=f"Break streak {index}",
        )
        _update_vocabulary(
            session_factory,
            str(item["id"]),
            created_at=now - timedelta(days=days_ago),
            last_reviewed_at=now - timedelta(days=days_ago),
        )

    with session_factory() as db:
        snapshot = get_dashboard_snapshot(db, _user_id(session_factory, email), now=now)

    assert snapshot.current_streak == 0
    assert snapshot.longest_streak == 3
    assert len(snapshot.recent_active_dates) == 3


def test_vocabulary_status_totals_and_mastered_count(
    client: TestClient,
    general_english_track_id: uuid.UUID,
) -> None:
    headers = authenticate(client, "dashboard-status@example.com")
    for index, status in enumerate(["new", "new", "learning", "review", "mastered"]):
        create_item(
            client,
            headers,
            general_english_track_id,
            word=f"Status word {index}",
            learning_status=status,
        )

    body = client.get("/api/v1/dashboard", headers=headers).json()

    assert body["total_vocabulary"] == 5
    assert body["new_words"] == 2
    assert body["learning_words"] == 1
    assert body["review_words"] == 1
    assert body["mastered_words"] == 1


def test_due_count_excludes_future_and_mastered_words(
    client: TestClient,
    general_english_track_id: uuid.UUID,
    session_factory: sessionmaker[Session],
) -> None:
    headers = authenticate(client, "dashboard-due@example.com")
    due_null = create_item(client, headers, general_english_track_id, word="Due null")
    due_past = create_item(client, headers, general_english_track_id, word="Due past")
    future = create_item(client, headers, general_english_track_id, word="Future")
    mastered = create_item(
        client,
        headers,
        general_english_track_id,
        word="Mastered due",
        learning_status="mastered",
    )
    now = datetime.now(UTC)
    _update_vocabulary(
        session_factory,
        due_past["id"],
        next_review_at=now - timedelta(minutes=1),
    )
    _update_vocabulary(
        session_factory,
        future["id"],
        next_review_at=now + timedelta(days=1),
    )
    _update_vocabulary(
        session_factory,
        mastered["id"],
        next_review_at=None,
    )

    body = client.get("/api/v1/dashboard", headers=headers).json()

    assert due_null["id"]
    assert body["words_due_for_review"] == 2


def test_attempt_totals_and_accuracy_count_every_completion(
    client: TestClient,
    general_english_track_id: uuid.UUID,
    session_factory: sessionmaker[Session],
) -> None:
    email = "dashboard-attempts@example.com"
    headers = authenticate(client, email)
    exercise_id = _create_exercise(
        session_factory,
        user_id=_user_id(session_factory, email),
        track_id=general_english_track_id,
    )
    for answer in ["A", "B", "A"]:
        response = client.post(
            f"/api/v1/exercises/{exercise_id}/attempts",
            headers=headers,
            json={"answer": answer},
        )
        assert response.status_code == 200

    body = client.get("/api/v1/dashboard", headers=headers).json()

    assert body["exercises_completed"] == 3
    assert body["correct_exercise_attempts"] == 2
    assert body["incorrect_exercise_attempts"] == 1
    assert body["exercise_accuracy"] == 66.7


def test_recent_vocabulary_is_newest_first_limited_and_minimal(
    client: TestClient,
    general_english_track_id: uuid.UUID,
    session_factory: sessionmaker[Session],
) -> None:
    headers = authenticate(client, "dashboard-recent@example.com")
    base_time = datetime(2026, 1, 1, tzinfo=UTC)
    items: list[dict[str, object]] = []
    for index in range(6):
        item = create_item(
            client,
            headers,
            general_english_track_id,
            word=f"Recent {index}",
            meaning=f"Meaning {index}",
        )
        items.append(item)
        _update_vocabulary(
            session_factory,
            str(item["id"]),
            created_at=base_time + timedelta(days=index),
        )

    recent = client.get("/api/v1/dashboard", headers=headers).json()[
        "recently_added_vocabulary"
    ]

    assert len(recent) == 6
    assert [item["word"] for item in recent] == [
        "Recent 5",
        "Recent 4",
        "Recent 3",
        "Recent 2",
        "Recent 1",
        "Recent 0",
    ]
    assert set(recent[0]) == {
        "id",
        "word",
        "meaning",
        "level_code",
        "learning_status",
        "created_at",
    }


def test_dashboard_is_isolated_between_users(
    client: TestClient,
    general_english_track_id: uuid.UUID,
    session_factory: sessionmaker[Session],
) -> None:
    first_email = "dashboard-first@example.com"
    first = authenticate(client, first_email)
    second_email = "dashboard-second@example.com"
    second = authenticate(client, second_email)
    create_item(client, first, general_english_track_id, word="First only")
    create_item(client, second, general_english_track_id, word="Second one")
    create_item(client, second, general_english_track_id, word="Second two")
    second_exercise = _create_exercise(
        session_factory,
        user_id=_user_id(session_factory, second_email),
        track_id=general_english_track_id,
    )
    client.post(
        f"/api/v1/exercises/{second_exercise}/attempts",
        headers=second,
        json={"answer": "A"},
    )

    first_body = client.get("/api/v1/dashboard", headers=first).json()
    second_body = client.get("/api/v1/dashboard", headers=second).json()

    assert first_body["total_vocabulary"] == 1
    assert first_body["exercises_completed"] == 0
    assert first_body["current_streak"] == 1
    assert [item["word"] for item in first_body["recently_added_vocabulary"]] == [
        "First only"
    ]
    assert second_body["total_vocabulary"] == 2
    assert second_body["exercises_completed"] == 1
    assert second_body["current_streak"] == 1


def test_dashboard_requires_authentication(client: TestClient) -> None:
    response = client.get("/api/v1/dashboard")
    assert response.status_code == 401


def test_study_calendar_returns_activity_for_requested_month(
    client: TestClient,
    general_english_track_id: uuid.UUID,
    session_factory: sessionmaker[Session],
) -> None:
    headers = authenticate(client, "dashboard-calendar@example.com")
    first = create_item(client, headers, general_english_track_id, word="Calendar one")
    second = create_item(client, headers, general_english_track_id, word="Calendar two")
    _update_vocabulary(
        session_factory,
        first["id"],
        created_at=datetime(2026, 8, 3, 6, tzinfo=UTC),
    )
    _update_vocabulary(
        session_factory,
        second["id"],
        created_at=datetime(2026, 9, 4, 6, tzinfo=UTC),
    )

    response = client.get(
        "/api/v1/dashboard/study-calendar",
        headers=headers,
        params={
            "learning_track_id": str(general_english_track_id),
            "year": 2026,
            "month": 8,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["year"] == 2026
    assert body["month"] == 8
    assert body["learning_track_id"] == str(general_english_track_id)
    assert body["active_dates"] == ["2026-08-03"]
    assert set(body) == {
        "year",
        "month",
        "today",
        "active_dates",
        "current_streak",
        "longest_streak",
        "learning_track_id",
    }


def test_study_calendar_validates_month_and_requires_authentication(
    client: TestClient,
) -> None:
    headers = authenticate(client, "dashboard-calendar-validation@example.com")

    invalid = client.get(
        "/api/v1/dashboard/study-calendar",
        headers=headers,
        params={"year": 2026, "month": 13},
    )
    unauthenticated = client.get(
        "/api/v1/dashboard/study-calendar",
        params={"year": 2026, "month": 8},
    )

    assert invalid.status_code == 422
    assert unauthenticated.status_code == 401
