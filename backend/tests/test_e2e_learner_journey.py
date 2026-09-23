from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.ai.dependencies import get_exercise_ai_provider, get_vocabulary_ai_provider
from app.main import app
from app.models import Language, LearningTrack, VocabularyEntry, VocabularySet
from tests.test_ai_exercises import FakeExerciseProvider
from tests.test_ai_vocabulary import FakeVocabularyProvider


PASSWORD = "StrongPassword123!"


@pytest.fixture
def journey_catalog(session_factory: sessionmaker[Session]) -> dict[str, uuid.UUID]:
    with session_factory() as db:
        language = Language(code="en", name="English", native_name="English")
        track = LearningTrack(
            language=language,
            code="general-english",
            name="General English",
            level_framework="CEFR",
        )
        vocabulary_set = VocabularySet(
            learning_track=track,
            name="Daily Life",
            description="Small test-only learner journey set",
            level_code="A1",
            topic="Daily Life",
            order_index=1,
        )
        vocabulary_set.entries = [
            VocabularyEntry(
                word="routine",
                normalized_word="routine",
                part_of_speech="noun",
                meaning="Things regularly done in the same order.",
                translation="thói quen",
                example_sentences=["Exercise is part of her daily routine."],
                order_index=0,
            ),
            VocabularyEntry(
                word="prepare",
                normalized_word="prepare",
                part_of_speech="verb",
                meaning="To make something ready.",
                translation="chuẩn bị",
                example_sentences=["I prepare breakfast every morning."],
                order_index=1,
            ),
        ]
        db.add(vocabulary_set)
        db.commit()
        return {"track_id": track.id, "set_id": vocabulary_set.id}


def _authenticate(client: TestClient) -> dict[str, str]:
    credentials = {"email": "journey@example.com", "password": PASSWORD}
    assert client.post("/api/v1/auth/register", json=credentials).status_code == 201
    login = client.post("/api/v1/auth/login", json=credentials)
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_complete_v1_learner_journey(
    client: TestClient,
    journey_catalog: dict[str, uuid.UUID],
) -> None:
    headers = _authenticate(client)

    # Learn: browse a set and add its shared catalog entries to My Vocabulary.
    sets = client.get("/api/v1/vocabulary-sets?level=A1", headers=headers)
    assert sets.status_code == 200
    assert sets.json()["total"] == 1
    set_id = journey_catalog["set_id"]
    detail = client.get(f"/api/v1/vocabulary-sets/{set_id}", headers=headers)
    assert detail.status_code == 200
    assert len(detail.json()["entries"]) == 2
    imported = client.post(
        f"/api/v1/vocabulary-sets/{set_id}/start-learning", headers=headers
    )
    assert imported.status_code == 200
    assert imported.json()["created_count"] == 2

    # Manual vocabulary remains a separate, supported source.
    manual = client.post(
        "/api/v1/vocabularies",
        headers=headers,
        json={
            "learning_track_id": str(journey_catalog["track_id"]),
            "word": "habit",
            "part_of_speech": "noun",
            "meaning": "Something done regularly.",
            "translation": "thói quen",
            "example_sentences": ["Reading is a useful habit."],
            "level_code": "A2",
            "topic": "Daily Life",
            "learning_status": "new",
        },
    )
    assert manual.status_code == 201

    # AI only prepares an editable preview; persistence still needs an explicit save.
    vocabulary_provider = FakeVocabularyProvider()
    app.dependency_overrides[get_vocabulary_ai_provider] = lambda: vocabulary_provider
    preview = client.post(
        "/api/v1/ai/vocabulary",
        headers=headers,
        json={"word": "solely", "part_of_speech": "adverb", "translation": "chỉ, duy nhất"},
    )
    assert preview.status_code == 200
    assert client.get("/api/v1/vocabularies", headers=headers).json()["total"] == 3
    candidate = preview.json()
    saved_ai_vocabulary = client.post(
        "/api/v1/vocabularies",
        headers=headers,
        json={
            "learning_track_id": str(journey_catalog["track_id"]),
            "word": candidate["word"],
            "part_of_speech": candidate["part_of_speech"],
            "meaning": f"{candidate['definition']} (learner edited)",
            "translation": candidate["translation"],
            "example_sentences": candidate["examples"],
            "level_code": candidate["cefr_level"],
            "topic": "AI preview",
            "learning_status": "new",
        },
    )
    assert saved_ai_vocabulary.status_code == 201

    vocabulary_items = client.get(
        "/api/v1/vocabularies?page_size=20", headers=headers
    ).json()["items"]
    assert len(vocabulary_items) == 4

    # Review one due word.
    due = client.get("/api/v1/vocabularies/due-for-review", headers=headers)
    assert due.status_code == 200
    reviewed_id = due.json()["items"][0]["id"]
    reviewed = client.post(
        f"/api/v1/vocabularies/{reviewed_id}/reviews",
        headers=headers,
        json={"is_correct": True},
    )
    assert reviewed.status_code == 200
    assert reviewed.json()["review_count"] == 1

    # AI generates learner-safe content, then normal backend code grades it.
    vocabulary_ids = [item["id"] for item in vocabulary_items]
    exercise_provider = FakeExerciseProvider(
        {
            "exercises": [
                {
                    "exercise_type": "multiple_choice",
                    "prompt": "The task was handled _______ by one person.",
                    "options": [
                        {"id": "A", "text": "solely"},
                        {"id": "B", "text": "routine"},
                        {"id": "C", "text": "prepare"},
                        {"id": "D", "text": "habit"},
                    ],
                    "correct_answer": "A",
                    "explanation": "Solely means only or exclusively.",
                    "target_vocabulary_id": saved_ai_vocabulary.json()["id"],
                }
            ]
        }
    )
    app.dependency_overrides[get_exercise_ai_provider] = lambda: exercise_provider
    generated = client.post(
        "/api/v1/ai/exercises/generate",
        headers=headers,
        json={
            "vocabulary_ids": vocabulary_ids,
            "exercise_type": "multiple_choice",
            "count": 1,
        },
    )
    assert generated.status_code == 200, generated.text
    generated_item = generated.json()["items"][0]
    assert "correct_answer" not in generated_item
    # The backend deals the options out again, so locate the answer by its text.
    answer_id = next(
        option["id"]
        for option in generated_item["options"]
        if option["text"] == "solely"
    )
    attempt = client.post(
        f"/api/v1/exercises/{generated_item['id']}/attempts",
        headers=headers,
        json={"answer": answer_id},
    )
    assert attempt.status_code == 200
    assert attempt.json()["is_correct"] is True

    # Dashboard derives its totals from persisted learner data and attempts.
    dashboard = client.get("/api/v1/dashboard", headers=headers)
    assert dashboard.status_code == 200
    assert dashboard.json()["total_vocabulary"] == 4
    assert dashboard.json()["exercises_completed"] == 1
    assert dashboard.json()["exercise_accuracy"] == 100.0
