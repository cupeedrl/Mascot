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
        "prompt": "The decision was based _______ on cost alone.",
        "options": [
            {"id": "A", "text": "solely"},
            {"id": "B", "text": "sustainable"},
            {"id": "C", "text": "compromise"},
            {"id": "D", "text": "revenue"},
        ],
        "correct_answer": "A",
        "explanation": "Solely means only or exclusively.",
        "target_vocabulary_id": vocabularies[0]["id"],
    }
    candidate.update(overrides)
    return candidate


def _fill_in_blank(vocabularies: list[dict[str, object]], **overrides: object):
    targets = [vocabularies[index % len(vocabularies)] for index in range(4)]
    candidate: dict[str, object] = {
        "exercise_type": "fill_in_blank",
        "title": "TEAM UPDATE",
        "passage": (
            "The team chose (1) ______ for the opening sentence.\n"
            "The next report used (2) ______ in a clear example.\n"
            "During the meeting, we practised (3) ______ together.\n"
            "Finally, the summary included (4) ______ for review."
        ),
        "blanks": [
            {
                "number": index + 1,
                "options": [
                    {"id": "A", "text": target["word"]},
                    {"id": "B", "text": f"distractor-{index}-b"},
                    {"id": "C", "text": f"distractor-{index}-c"},
                    {"id": "D", "text": f"distractor-{index}-d"},
                ],
                "correct_answer": "A",
                "target_vocabulary_id": target["id"],
                "explanation": f"The target word is {target['word']}.",
            }
            for index, target in enumerate(targets)
        ],
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
    source_mode: str = "custom",
    topic: str | None = None,
):
    payload: dict[str, object] = {
        "source_mode": source_mode,
        "exercise_type": exercise_type,
        "count": count,
    }
    if source_mode == "custom":
        payload["vocabulary_ids"] = [item["id"] for item in vocabularies]
    elif source_mode == "topic":
        payload["topic"] = topic
    return client.post(
        "/api/v1/ai/exercises/generate",
        headers=headers,
        json=payload,
    )


def _multiple_choice_batch(
    vocabularies: list[dict[str, object]], count: int
) -> dict[str, object]:
    options = [
        {"id": option_id, "text": vocabularies[index]["word"]}
        for index, option_id in enumerate(["A", "B", "C", "D"])
    ]
    return {
        "exercises": [
            _multiple_choice(
                vocabularies,
                prompt=f"The decision in scenario {index + 1} was based _______ on cost alone.",
                options=options,
                correct_answer="A",
                target_vocabulary_id=vocabularies[0]["id"],
            )
            for index in range(count)
        ]
    }


def _fill_in_blank_batch(
    vocabularies: list[dict[str, object]], count: int
) -> dict[str, object]:
    assert count >= 1
    return {"exercises": [_fill_in_blank(vocabularies)]}


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
    assert item["prompt"].count("_______") == 1
    assert len(item["options"]) == 4
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
        "cefr_level",
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
        assert len(links) == 4


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
    learner_item = generated.json()["items"][0]
    exercise_id = learner_item["id"]
    assert learner_item["prompt"].count("(1) ______") == 1
    assert [blank["number"] for blank in learner_item["options"]] == [1, 2, 3, 4]
    assert all(len(blank["options"]) == 4 for blank in learner_item["options"])
    assert all(set(blank) == {"number", "options"} for blank in learner_item["options"])
    assert all(
        set(option) == {"id", "text"}
        for blank in learner_item["options"]
        for option in blank["options"]
    )
    graded = client.post(
        f"/api/v1/exercises/{exercise_id}/attempts",
        headers=headers,
        json={"answers": {"1": "A", "2": "B", "3": "A", "4": "A"}},
    )

    assert graded.status_code == 200
    assert graded.json()["is_correct"] is False
    assert graded.json()["correct_count"] == 3
    assert graded.json()["total"] == 4
    assert graded.json()["score_percent"] == 75
    assert [item["is_correct"] for item in graded.json()["results"]] == [True, False, True, True]
    all_correct = client.post(
        f"/api/v1/exercises/{exercise_id}/attempts",
        headers=headers,
        json={"answers": {"1": "A", "2": "A", "3": "A", "4": "A"}},
    )
    partial_submission = client.post(
        f"/api/v1/exercises/{exercise_id}/attempts",
        headers=headers,
        json={"answers": {"1": "A", "2": "A", "3": "A"}},
    )
    assert all_correct.status_code == 200
    assert all_correct.json()["is_correct"] is True
    assert all_correct.json()["correct_count"] == 4
    assert partial_submission.status_code == 422
    with session_factory() as db:
        attempts = list(db.scalars(select(ExerciseAttempt)))
        assert len(attempts) == 2
        assert {attempt.correct_answer for attempt in attempts} == {
            '{"1": "A", "2": "A", "3": "A", "4": "A"}'
        }


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
        ("fill_in_blank", 16, 16),
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
    assert response.json()["detail"] == (
        "Bạn cần ít nhất 4 từ khác nhau để tạo bài tập trắc nghiệm."
    )
    assert provider.calls == []


@pytest.mark.parametrize("count", [1, 15])
def test_question_count_boundaries_are_accepted(
    client: TestClient,
    general_english_track_id: uuid.UUID,
    count: int,
) -> None:
    headers = authenticate(client, f"count-{count}@example.com")
    vocabularies = _select_vocabularies(client, headers, general_english_track_id)
    provider = FakeExerciseProvider(_multiple_choice_batch(vocabularies, count))
    _use_provider(provider)

    response = _request(
        client,
        headers,
        vocabularies,
        exercise_type="multiple_choice",
        count=count,
    )

    assert response.status_code == 200, response.text
    assert response.json()["created_count"] == count
    assert provider.calls[0][2] == count


def test_fill_in_blank_default_is_one_passage(
    client: TestClient,
    general_english_track_id: uuid.UUID,
) -> None:
    headers = authenticate(client, "default-count@example.com")
    vocabularies = _select_vocabularies(client, headers, general_english_track_id)
    provider = FakeExerciseProvider(_fill_in_blank_batch(vocabularies, 1))
    _use_provider(provider)

    response = client.post(
        "/api/v1/ai/exercises/generate",
        headers=headers,
        json={
            "source_mode": "custom",
            "vocabulary_ids": [item["id"] for item in vocabularies],
            "exercise_type": "fill_in_blank",
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["created_count"] == 1
    assert provider.calls[0][2] == 1


def test_fill_in_blank_request_count_is_normalized_to_one_passage(
    client: TestClient,
    general_english_track_id: uuid.UUID,
) -> None:
    headers = authenticate(client, "fill-count@example.com")
    vocabularies = _select_vocabularies(client, headers, general_english_track_id)
    provider = FakeExerciseProvider(_fill_in_blank_batch(vocabularies, 1))
    _use_provider(provider)

    response = _request(
        client,
        headers,
        vocabularies,
        exercise_type="fill_in_blank",
        count=15,
    )

    assert response.status_code == 200, response.text
    assert response.json()["created_count"] == 1
    assert provider.calls[0][2] == 1


@pytest.mark.parametrize("count", [5, 10])
def test_source_pool_can_be_larger_than_question_count(
    client: TestClient,
    general_english_track_id: uuid.UUID,
    count: int,
) -> None:
    headers = authenticate(client, f"large-pool-{count}@example.com")
    vocabularies = [
        create_item(
            client,
            headers,
            general_english_track_id,
            word=f"sourceword{index}",
            meaning=f"Meaning for source word {index}.",
            translation=f"nghĩa {index}",
        )
        for index in range(16)
    ]
    provider = FakeExerciseProvider(_multiple_choice_batch(vocabularies, count))
    _use_provider(provider)

    response = _request(client, headers, vocabularies, count=count)

    assert response.status_code == 200, response.text
    assert response.json()["created_count"] == count
    assert len(provider.calls[0][0]) == 16


def test_recent_eleven_words_generates_two_valid_sentence_clozes(
    client: TestClient,
    general_english_track_id: uuid.UUID,
    session_factory: sessionmaker[Session],
) -> None:
    """Regression: natural distractors must not reject a valid Groq MCQ batch."""
    headers = authenticate(client, "eleven-recent-words@example.com")
    vocabularies = [
        create_item(
            client,
            headers,
            general_english_track_id,
            word=word,
            meaning=f"A learner-friendly meaning for {word}.",
        )
        for word in [
            "routine", "breakfast", "commute", "neighbor", "relax", "parent",
            "sibling", "cousin", "married", "support", "garden",
        ]
    ]
    first, second = vocabularies[0], vocabularies[1]
    provider = FakeExerciseProvider(
        {
            "exercises": [
                {
                    "exercise_type": "multiple_choice",
                    "prompt": "After a long day, I follow my evening _____ before bed.",
                    "options": [
                        {"id": "A", "text": first["word"]},
                        {"id": "B", "text": "holiday"},
                        {"id": "C", "text": "problem"},
                        {"id": "D", "text": "mistake"},
                    ],
                    "correct_answer": "A",
                    "explanation": "“Routine” là chuỗi hoạt động bạn thường làm theo một trình tự quen thuộc.",
                    "target_vocabulary_id": first["id"],
                },
                {
                    "exercise_type": "multiple_choice",
                    "prompt": "She ate _____ before leaving for school.",
                    "options": [
                        {"id": "A", "text": second["word"]},
                        {"id": "B", "text": "lesson"},
                        {"id": "C", "text": "window"},
                        {"id": "D", "text": "ticket"},
                    ],
                    "correct_answer": "A",
                    "explanation": "“Breakfast” là bữa ăn đầu tiên trong ngày.",
                    "target_vocabulary_id": second["id"],
                },
            ]
        }
    )
    _use_provider(provider)

    response = _request(
        client,
        headers,
        [],
        source_mode="recent",
        exercise_type="multiple_choice",
        count=2,
    )

    assert response.status_code == 200, response.text
    assert response.json()["created_count"] == 2
    assert len(provider.calls[0][0]) == 11
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(Exercise)) == 2


def test_recent_source_only_uses_current_users_vocabulary(
    client: TestClient,
    general_english_track_id: uuid.UUID,
) -> None:
    headers = authenticate(client, "recent-owner@example.com")
    owner_words = _select_vocabularies(client, headers, general_english_track_id)
    other_headers = authenticate(client, "recent-other@example.com")
    create_item(
        client,
        other_headers,
        general_english_track_id,
        word="privateword",
    )
    provider = FakeExerciseProvider(_fill_in_blank_batch(owner_words, 1))
    _use_provider(provider)

    response = _request(
        client,
        headers,
        [],
        exercise_type="fill_in_blank",
        source_mode="recent",
    )

    assert response.status_code == 200, response.text
    sent_ids = {item["id"] for item in provider.calls[0][0]}
    assert sent_ids == {item["id"] for item in owner_words}


def test_topic_source_uses_only_current_users_matching_topic(
    client: TestClient,
    general_english_track_id: uuid.UUID,
) -> None:
    headers = authenticate(client, "topic-owner@example.com")
    work_words = [
        create_item(
            client,
            headers,
            general_english_track_id,
            word=word,
            topic="Work & Business",
        )
        for word in ["revenue", "profit"]
    ]
    create_item(
        client,
        headers,
        general_english_track_id,
        word="journey",
        topic="Travel",
    )
    other_headers = authenticate(client, "topic-other@example.com")
    create_item(
        client,
        other_headers,
        general_english_track_id,
        word="privateword",
        topic="Work & Business",
    )
    provider = FakeExerciseProvider(
        {
            "exercises": [
                _fill_in_blank(work_words)
            ]
        }
    )
    _use_provider(provider)

    response = _request(
        client,
        headers,
        [],
        exercise_type="fill_in_blank",
        source_mode="topic",
        topic="  WORK   & BUSINESS  ",
    )

    assert response.status_code == 200, response.text
    sent_ids = {item["id"] for item in provider.calls[0][0]}
    assert sent_ids == {item["id"] for item in work_words}


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


@pytest.mark.parametrize("mutation", ["blank_count", "option_count"])
def test_malformed_passage_cloze_is_rejected(
    client: TestClient,
    general_english_track_id: uuid.UUID,
    session_factory: sessionmaker[Session],
    mutation: str,
) -> None:
    headers = authenticate(client, f"malformed-cloze-{mutation}@example.com")
    vocabularies = _select_vocabularies(client, headers, general_english_track_id)
    candidate = _fill_in_blank(vocabularies)
    if mutation == "blank_count":
        candidate["blanks"] = candidate["blanks"][:3]
    else:
        candidate["blanks"][0]["options"] = candidate["blanks"][0]["options"][:3]
    _use_provider(FakeExerciseProvider({"exercises": [candidate]}))

    response = _request(
        client,
        headers,
        vocabularies,
        exercise_type="fill_in_blank",
    )

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
    invalid = _fill_in_blank(vocabularies)
    invalid["blanks"][0]["target_vocabulary_id"] = str(uuid.uuid4())
    _use_provider(FakeExerciseProvider({"exercises": [invalid]}))
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
