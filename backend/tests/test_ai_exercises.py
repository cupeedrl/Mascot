from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.ai.dependencies import get_exercise_ai_provider
from app.ai.provider import AIProviderTimeoutError
from app.main import app
from app.models import Exercise, ExerciseAttempt, exercise_vocabularies
from tests.test_vocabulary import authenticate, create_item, general_english_track_id


class FakeExerciseProvider:
    def __init__(self, result: object, error: Exception | None = None) -> None:
        self.result = result
        self.error = error
        self.calls: list[tuple[list[dict[str, object]], str, int]] = []

    def generate_exercises(
        self,
        vocabulary_context: list[dict[str, object]],
        exercise_type: str,
        count: int,
    ) -> object:
        self.calls.append((vocabulary_context, exercise_type, count))
        if self.error is not None:
            raise self.error
        return self.result


def _select_vocabularies(
    client: TestClient,
    headers: dict[str, str],
    track_id: uuid.UUID,
) -> list[dict[str, object]]:
    words = ["solely", "sustainable", "compromise", "revenue"]
    return [
        create_item(
            client,
            headers,
            track_id,
            word=word,
            meaning=f"A learner-friendly meaning for {word}.",
        )
        for word in words
    ]


def _multiple_choice(vocabularies: list[dict[str, object]], **overrides: object):
    candidate: dict[str, object] = {
        "exercise_type": "multiple_choice",
        "prompt": "The decision was based ____ on cost.",
        "options": [
            {"id": "A", "text": "solely"},
            {"id": "B", "text": "sustainable"},
            {"id": "C", "text": "compromise"},
            {"id": "D", "text": "revenue"},
        ],
        "correct_answer": "A",
        "explanation": "Solely means only or exclusively.",
        "source_vocabulary_ids": [vocabularies[0]["id"]],
    }
    candidate.update(overrides)
    return candidate


def _fill_in_blank(vocabularies: list[dict[str, object]], **overrides: object):
    candidate: dict[str, object] = {
        "exercise_type": "fill_in_blank",
        "prompt": "The two companies reached a ______ after negotiation.",
        "correct_answer": "compromise",
        "accepted_answers": ["compromise"],
        "explanation": "A compromise is an agreement reached by concessions.",
        "source_vocabulary_ids": [vocabularies[2]["id"]],
    }
    candidate.update(overrides)
    return candidate


def _use_provider(provider: FakeExerciseProvider) -> None:
    app.dependency_overrides[get_exercise_ai_provider] = lambda: provider


def _request(
    client: TestClient,
    headers: dict[str, str],
    vocabularies: list[dict[str, object]],
    *,
    exercise_type: str = "multiple_choice",
    count: int = 1,
):
    return client.post(
        "/api/v1/ai/exercises/generate",
        headers=headers,
        json={
            "vocabulary_ids": [item["id"] for item in vocabularies],
            "exercise_type": exercise_type,
            "count": count,
        },
    )


def test_generate_multiple_choice_is_stored_linked_and_learner_safe(
    client: TestClient,
    general_english_track_id: uuid.UUID,
    session_factory: sessionmaker[Session],
) -> None:
    headers = authenticate(client, "ai-exercise-mc@example.com")
    vocabularies = _select_vocabularies(client, headers, general_english_track_id)
    provider = FakeExerciseProvider(
        {"exercises": [_multiple_choice(vocabularies)]}
    )
    _use_provider(provider)

    response = _request(client, headers, vocabularies)

    assert response.status_code == 200, response.text
    assert response.json()["created_count"] == 1
    item = response.json()["items"][0]
    assert item["source"] == "ai"
    for hidden_field in (
        "correct_answer",
        "accepted_answers",
        "explanation",
        "source_vocabulary_ids",
    ):
        assert hidden_field not in item
    assert len(provider.calls) == 1
    sent_context = provider.calls[0][0]
    assert set(sent_context[0]) == {
        "id",
        "word",
        "part_of_speech",
        "meaning",
        "example_sentences",
    }
    with session_factory() as db:
        exercise = db.scalar(select(Exercise))
        assert exercise is not None
        assert exercise.source == "ai"
        links = list(
            db.execute(
                select(exercise_vocabularies).where(
                    exercise_vocabularies.c.exercise_id == exercise.id
                )
            ).all()
        )
        assert len(links) == 1
        assert links[0].vocabulary_id == uuid.UUID(str(vocabularies[0]["id"]))


def test_generate_fill_in_blank_and_grade_deterministically(
    client: TestClient,
    general_english_track_id: uuid.UUID,
    session_factory: sessionmaker[Session],
) -> None:
    headers = authenticate(client, "ai-exercise-fill@example.com")
    vocabularies = _select_vocabularies(client, headers, general_english_track_id)
    _use_provider(
        FakeExerciseProvider({"exercises": [_fill_in_blank(vocabularies)]})
    )

    generated = _request(
        client,
        headers,
        vocabularies,
        exercise_type="fill_in_blank",
    )
    assert generated.status_code == 200, generated.text
    exercise_id = generated.json()["items"][0]["id"]
    graded = client.post(
        f"/api/v1/exercises/{exercise_id}/attempts",
        headers=headers,
        json={"answer": "  COMPromise "},
    )

    assert graded.status_code == 200
    assert graded.json()["is_correct"] is True
    assert graded.json()["correct_answer"] == "compromise"
    with session_factory() as db:
        attempt = db.scalar(select(ExerciseAttempt))
        assert attempt is not None
        assert attempt.correct_answer == "compromise"


def test_generation_requires_authentication(client: TestClient) -> None:
    provider = FakeExerciseProvider({"exercises": []})
    _use_provider(provider)
    response = client.post(
        "/api/v1/ai/exercises/generate",
        json={
            "vocabulary_ids": [str(uuid.uuid4())],
            "exercise_type": "fill_in_blank",
            "count": 1,
        },
    )
    assert response.status_code == 401
    assert provider.calls == []


def test_user_cannot_generate_from_another_users_vocabulary(
    client: TestClient,
    general_english_track_id: uuid.UUID,
) -> None:
    owner = authenticate(client, "ai-owner@example.com")
    attacker = authenticate(client, "ai-attacker@example.com")
    owned = _select_vocabularies(client, owner, general_english_track_id)
    provider = FakeExerciseProvider({"exercises": []})
    _use_provider(provider)

    response = _request(client, attacker, owned)

    assert response.status_code == 404
    assert provider.calls == []


@pytest.mark.parametrize(
    "exercise_type,count,id_count",
    [
        ("essay", 1, 1),
        ("fill_in_blank", 0, 1),
        ("fill_in_blank", 11, 11),
        ("fill_in_blank", 2, 1),
    ],
)
def test_invalid_generation_input_is_rejected(
    client: TestClient,
    exercise_type: str,
    count: int,
    id_count: int,
) -> None:
    headers = authenticate(client, f"invalid-{uuid.uuid4()}@example.com")
    provider = FakeExerciseProvider({"exercises": []})
    _use_provider(provider)
    response = client.post(
        "/api/v1/ai/exercises/generate",
        headers=headers,
        json={
            "vocabulary_ids": [str(uuid.uuid4()) for _ in range(id_count)],
            "exercise_type": exercise_type,
            "count": count,
        },
    )
    assert response.status_code == 422
    assert provider.calls == []


def test_multiple_choice_requires_four_distinct_words(
    client: TestClient,
    general_english_track_id: uuid.UUID,
) -> None:
    headers = authenticate(client, "too-few-mc@example.com")
    vocabularies = [
        create_item(client, headers, general_english_track_id, word="solely")
    ]
    provider = FakeExerciseProvider({"exercises": []})
    _use_provider(provider)
    response = _request(client, headers, vocabularies)
    assert response.status_code == 422
    assert provider.calls == []


def test_provider_timeout_returns_safe_error_without_persistence(
    client: TestClient,
    general_english_track_id: uuid.UUID,
    session_factory: sessionmaker[Session],
) -> None:
    headers = authenticate(client, "ai-exercise-timeout@example.com")
    vocabularies = _select_vocabularies(client, headers, general_english_track_id)
    provider = FakeExerciseProvider(
        {"exercises": []},
        error=AIProviderTimeoutError(),
    )
    _use_provider(provider)
    response = _request(client, headers, vocabularies)
    assert response.status_code == 504
    assert "quá thời gian chờ" in response.json()["detail"]
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(Exercise)) == 0


@pytest.mark.parametrize(
    "result",
    [
        {"unexpected": []},
        {"exercises": [{"exercise_type": "multiple_choice"}]},
    ],
)
def test_malformed_ai_output_is_rejected_atomically(
    client: TestClient,
    general_english_track_id: uuid.UUID,
    session_factory: sessionmaker[Session],
    result: object,
) -> None:
    headers = authenticate(client, f"malformed-{uuid.uuid4()}@example.com")
    vocabularies = _select_vocabularies(client, headers, general_english_track_id)
    _use_provider(FakeExerciseProvider(result))
    response = _request(client, headers, vocabularies)
    assert response.status_code == 502
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(Exercise)) == 0


def test_invalid_correct_answer_is_rejected(
    client: TestClient,
    general_english_track_id: uuid.UUID,
    session_factory: sessionmaker[Session],
) -> None:
    headers = authenticate(client, "invalid-correct@example.com")
    vocabularies = _select_vocabularies(client, headers, general_english_track_id)
    _use_provider(
        FakeExerciseProvider(
            {"exercises": [_multiple_choice(vocabularies, correct_answer="Z")]}
        )
    )
    response = _request(client, headers, vocabularies)
    assert response.status_code == 502
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(Exercise)) == 0


def test_invalid_source_reference_rejects_entire_batch(
    client: TestClient,
    general_english_track_id: uuid.UUID,
    session_factory: sessionmaker[Session],
) -> None:
    headers = authenticate(client, "invalid-source@example.com")
    vocabularies = _select_vocabularies(client, headers, general_english_track_id)
    valid = _fill_in_blank(vocabularies)
    invalid = _fill_in_blank(
        vocabularies,
        prompt="Revenue is the ______ earned by a business.",
        correct_answer="revenue",
        accepted_answers=["revenue"],
        source_vocabulary_ids=[str(uuid.uuid4())],
    )
    _use_provider(FakeExerciseProvider({"exercises": [valid, invalid]}))
    response = _request(
        client,
        headers,
        vocabularies,
        exercise_type="fill_in_blank",
        count=2,
    )
    assert response.status_code == 502
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(Exercise)) == 0
