from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.models import (
    Exercise,
    ExerciseAttempt,
    User,
    Vocabulary,
    exercise_vocabularies,
)
from scripts.seed_demo_exercises import seed_for_user
from tests.test_vocabulary import authenticate, create_item, general_english_track_id


def _user_id(session_factory: sessionmaker[Session], email: str) -> uuid.UUID:
    with session_factory() as db:
        user = db.scalar(select(User).where(User.normalized_email == email.casefold()))
        assert user is not None
        return user.id


def _create_exercise(
    session_factory: sessionmaker[Session],
    *,
    user_id: uuid.UUID,
    track_id: uuid.UUID,
    exercise_type: str = "multiple_choice",
    vocabulary_id: uuid.UUID | None = None,
) -> uuid.UUID:
    with session_factory() as db:
        exercise = Exercise(
            user_id=user_id,
            learning_track_id=track_id,
            exercise_type=exercise_type,
            prompt=(
                "The decision was based ____ on cost."
                if exercise_type == "multiple_choice"
                else "The two sides reached a ______ after discussion."
            ),
            options=(
                [
                    {"id": "A", "text": "solely"},
                    {"id": "B", "text": "sustainable"},
                    {"id": "C", "text": "compromise"},
                    {"id": "D", "text": "revenue"},
                ]
                if exercise_type == "multiple_choice"
                else None
            ),
            correct_answer="A" if exercise_type == "multiple_choice" else "compromise",
            accepted_answers=[] if exercise_type == "multiple_choice" else ["a compromise"],
            explanation="A deterministic explanation.",
            source="manual",
        )
        if vocabulary_id is not None:
            vocabulary = db.get(Vocabulary, vocabulary_id)
            assert vocabulary is not None
            exercise.vocabularies.append(vocabulary)
        db.add(exercise)
        db.commit()
        return exercise.id


def test_authenticated_listing_is_scoped_and_hides_answers(
    client: TestClient,
    general_english_track_id: uuid.UUID,
    session_factory: sessionmaker[Session],
) -> None:
    email = "exercise-list@example.com"
    headers = authenticate(client, email)
    other_headers = authenticate(client, "exercise-list-other@example.com")
    vocabulary = create_item(client, headers, general_english_track_id)
    own_id = _create_exercise(
        session_factory,
        user_id=_user_id(session_factory, email),
        track_id=general_english_track_id,
        vocabulary_id=uuid.UUID(str(vocabulary["id"])),
    )
    _create_exercise(
        session_factory,
        user_id=_user_id(session_factory, "exercise-list-other@example.com"),
        track_id=general_english_track_id,
    )

    response = client.get("/api/v1/exercises", headers=headers)

    assert response.status_code == 200
    assert response.json()["total"] == 1
    item = response.json()["items"][0]
    assert item["id"] == str(own_id)
    assert "correct_answer" not in item
    assert "accepted_answers" not in item
    assert "explanation" not in item
    assert "source_vocabulary_ids" not in item
    detail = client.get(f"/api/v1/exercises/{own_id}", headers=headers)
    assert detail.status_code == 200
    assert "correct_answer" not in detail.json()
    assert "accepted_answers" not in detail.json()
    assert "explanation" not in detail.json()
    with session_factory() as db:
        linked_ids = list(
            db.scalars(
                select(exercise_vocabularies.c.vocabulary_id).where(
                    exercise_vocabularies.c.exercise_id == own_id
                )
            )
        )
        assert linked_ids == [uuid.UUID(str(vocabulary["id"]))]
    assert client.get("/api/v1/exercises", headers=other_headers).json()["total"] == 1


def test_exercise_access_requires_authentication(client: TestClient) -> None:
    assert client.get("/api/v1/exercises").status_code == 401
    assert client.get(f"/api/v1/exercises/{uuid.uuid4()}").status_code == 401


def test_user_cannot_read_another_users_exercise(
    client: TestClient,
    general_english_track_id: uuid.UUID,
    session_factory: sessionmaker[Session],
) -> None:
    authenticate(client, "exercise-owner@example.com")
    attacker_headers = authenticate(client, "exercise-attacker@example.com")
    exercise_id = _create_exercise(
        session_factory,
        user_id=_user_id(session_factory, "exercise-owner@example.com"),
        track_id=general_english_track_id,
    )

    response = client.get(f"/api/v1/exercises/{exercise_id}", headers=attacker_headers)

    assert response.status_code == 404


def test_multiple_choice_correct_and_incorrect_attempts_are_stored(
    client: TestClient,
    general_english_track_id: uuid.UUID,
    session_factory: sessionmaker[Session],
) -> None:
    email = "multiple-choice@example.com"
    headers = authenticate(client, email)
    exercise_id = _create_exercise(
        session_factory,
        user_id=_user_id(session_factory, email),
        track_id=general_english_track_id,
    )

    correct = client.post(
        f"/api/v1/exercises/{exercise_id}/attempts",
        headers=headers,
        json={"answer": " a "},
    )
    incorrect = client.post(
        f"/api/v1/exercises/{exercise_id}/attempts",
        headers=headers,
        json={"answer": "B"},
    )

    assert correct.status_code == 200
    assert correct.json()["is_correct"] is True
    assert correct.json()["correct_answer"] == "A"
    assert correct.json()["explanation"] == "A deterministic explanation."
    assert incorrect.status_code == 200
    assert incorrect.json()["is_correct"] is False
    with session_factory() as db:
        attempts = list(
            db.scalars(
                select(ExerciseAttempt).where(
                    ExerciseAttempt.exercise_id == exercise_id
                )
            )
        )
        assert len(attempts) == 2
        assert {attempt.correct_answer for attempt in attempts} == {"A"}


def test_fill_in_blank_normalization_and_accepted_answers(
    client: TestClient,
    general_english_track_id: uuid.UUID,
    session_factory: sessionmaker[Session],
) -> None:
    email = "fill-blank@example.com"
    headers = authenticate(client, email)
    exercise_id = _create_exercise(
        session_factory,
        user_id=_user_id(session_factory, email),
        track_id=general_english_track_id,
        exercise_type="fill_in_blank",
    )

    normalized = client.post(
        f"/api/v1/exercises/{exercise_id}/attempts",
        headers=headers,
        json={"answer": "  COMPromise  "},
    )
    accepted = client.post(
        f"/api/v1/exercises/{exercise_id}/attempts",
        headers=headers,
        json={"answer": " A   COMPROMISE "},
    )

    assert normalized.status_code == 200
    assert normalized.json()["is_correct"] is True
    assert accepted.status_code == 200
    assert accepted.json()["is_correct"] is True


def test_correct_answer_snapshot_does_not_change_with_exercise(
    client: TestClient,
    general_english_track_id: uuid.UUID,
    session_factory: sessionmaker[Session],
) -> None:
    email = "answer-snapshot@example.com"
    headers = authenticate(client, email)
    exercise_id = _create_exercise(
        session_factory,
        user_id=_user_id(session_factory, email),
        track_id=general_english_track_id,
    )
    response = client.post(
        f"/api/v1/exercises/{exercise_id}/attempts",
        headers=headers,
        json={"answer": "A"},
    )
    attempt_id = uuid.UUID(response.json()["id"])

    with session_factory() as db:
        exercise = db.get(Exercise, exercise_id)
        assert exercise is not None
        exercise.correct_answer = "B"
        db.commit()
        attempt = db.get(ExerciseAttempt, attempt_id)
        assert attempt is not None
        assert attempt.correct_answer == "A"


def test_user_cannot_submit_or_list_attempts_for_another_user(
    client: TestClient,
    general_english_track_id: uuid.UUID,
    session_factory: sessionmaker[Session],
) -> None:
    owner_email = "attempt-owner@example.com"
    owner_headers = authenticate(client, owner_email)
    attacker_headers = authenticate(client, "attempt-attacker@example.com")
    exercise_id = _create_exercise(
        session_factory,
        user_id=_user_id(session_factory, owner_email),
        track_id=general_english_track_id,
    )
    owner_attempt = client.post(
        f"/api/v1/exercises/{exercise_id}/attempts",
        headers=owner_headers,
        json={"answer": "A"},
    )
    assert owner_attempt.status_code == 200

    attack = client.post(
        f"/api/v1/exercises/{exercise_id}/attempts",
        headers=attacker_headers,
        json={"answer": "A"},
    )
    attacker_history = client.get("/api/v1/exercise-attempts", headers=attacker_headers)
    owner_history = client.get("/api/v1/exercise-attempts", headers=owner_headers)

    assert attack.status_code == 404
    assert attacker_history.status_code == 200
    assert attacker_history.json()["total"] == 0
    assert owner_history.json()["total"] == 1
    assert owner_history.json()["items"][0]["correct_answer"] == "A"


def test_exercise_type_filter_and_input_validation(
    client: TestClient,
    general_english_track_id: uuid.UUID,
    session_factory: sessionmaker[Session],
) -> None:
    email = "exercise-filter@example.com"
    headers = authenticate(client, email)
    user_id = _user_id(session_factory, email)
    _create_exercise(
        session_factory, user_id=user_id, track_id=general_english_track_id
    )
    _create_exercise(
        session_factory,
        user_id=user_id,
        track_id=general_english_track_id,
        exercise_type="fill_in_blank",
    )

    response = client.get(
        "/api/v1/exercises?exercise_type=fill_in_blank", headers=headers
    )
    invalid_filter = client.get(
        "/api/v1/exercises?exercise_type=essay", headers=headers
    )
    blank_answer = client.post(
        f"/api/v1/exercises/{response.json()['items'][0]['id']}/attempts",
        headers=headers,
        json={"answer": "   "},
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["exercise_type"] == "fill_in_blank"
    assert invalid_filter.status_code == 422
    assert blank_answer.status_code == 422


def test_demo_seed_is_deterministic_idempotent_and_links_vocabulary(
    client: TestClient,
    general_english_track_id: uuid.UUID,
    session_factory: sessionmaker[Session],
) -> None:
    email = "demo-exercise-seed@example.com"
    headers = authenticate(client, email)
    for word in ["Solely", "Revenue", "Efficient", "Negotiate"]:
        create_item(
            client,
            headers,
            general_english_track_id,
            word=word,
            meaning=f"Demo meaning for {word}.",
        )

    with session_factory() as db:
        user = db.scalar(select(User).where(User.normalized_email == email))
        assert user is not None
        assert seed_for_user(db, user) == 2
        assert seed_for_user(db, user) == 0
        exercises = list(
            db.scalars(select(Exercise).where(Exercise.user_id == user.id))
        )
        assert {item.exercise_type for item in exercises} == {
            "multiple_choice",
            "fill_in_blank",
        }
        assert {item.source for item in exercises} == {"manual"}
        links = list(db.execute(select(exercise_vocabularies)).all())
        assert len(links) == 8
