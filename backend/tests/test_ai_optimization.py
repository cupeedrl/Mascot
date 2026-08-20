from __future__ import annotations

import time
import uuid
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from openai import APITimeoutError, RateLimitError, APIConnectionError
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.ai.dependencies import get_exercise_ai_provider, get_vocabulary_ai_provider
from app.ai.openai_compatible_provider import OpenAICompatibleVocabularyProvider
from app.ai.provider import (
    AIProviderQuotaError,
    AIProviderRateLimitError,
    AIProviderTimeoutError,
)
from app.main import app
from app.models import Exercise, ExerciseAttempt, Language, LearningTrack, User
from app.services.ai_guard import ai_guard, AICooldownError, AIDuplicateRequestError
from tests.test_vocabulary import authenticate, create_item


@pytest.fixture
def general_english_track_id(
    session_factory: sessionmaker[Session],
) -> uuid.UUID:
    with session_factory() as db:
        existing = db.scalar(
            select(LearningTrack).where(LearningTrack.code == "general-english")
        )
        if existing is not None:
            return existing.id

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


class TrackingExerciseProvider:
    def __init__(self, result: object, error: Exception | None = None) -> None:
        self.result = result
        self.error = error
        self.call_count = 0

    def generate_exercises(
        self,
        vocabulary_context: list[dict[str, object]],
        exercise_type: str,
        count: int,
    ) -> object:
        self.call_count += 1
        if self.error is not None:
            raise self.error
        return self.result


class TrackingVocabularyProvider:
    def __init__(self, result: object, error: Exception | None = None) -> None:
        self.result = result
        self.error = error
        self.call_count = 0

    def generate_vocabulary(
        self, word: str, part_of_speech: str, translation: str
    ) -> object:
        self.call_count += 1
        if self.error is not None:
            raise self.error
        return self.result


def _setup_user_and_words(client: TestClient, track_id: uuid.UUID, email: str):
    headers = authenticate(client, email=email)
    words = ["pioneer", "innovate", "resilient", "strategy"]
    vocab_ids = []
    for w in words:
        item = create_item(client, headers, track_id, word=w, meaning=f"Meaning of {w}")
        vocab_ids.append(item["id"])
    return headers, vocab_ids


def _sample_batch(vocab_ids: list[str]) -> dict[str, Any]:
    return {
        "exercises": [
            {
                "exercise_type": "multiple_choice",
                "prompt": "The team chose to _______ the entire industry with new methods.",
                "options": [
                    {"id": "A", "text": "pioneer"},
                    {"id": "B", "text": "innovate"},
                    {"id": "C", "text": "resilient"},
                    {"id": "D", "text": "strategy"},
                ],
                "correct_answer": "A",
                "explanation": "Pioneer means to develop or be the first to open up.",
                "target_vocabulary_id": vocab_ids[0],
            },
            {
                "exercise_type": "multiple_choice",
                "prompt": "We need to _______ our business model for digital growth.",
                "options": [
                    {"id": "A", "text": "pioneer"},
                    {"id": "B", "text": "innovate"},
                    {"id": "C", "text": "resilient"},
                    {"id": "D", "text": "strategy"},
                ],
                "correct_answer": "B",
                "explanation": "Innovate means to introduce new methods.",
                "target_vocabulary_id": vocab_ids[1],
            },
        ]
    }


def test_active_session_resumption_prevents_new_ai_calls(
    client: TestClient,
    general_english_track_id: uuid.UUID,
) -> None:
    headers, vocab_ids = _setup_user_and_words(client, general_english_track_id, "resumption_user@example.com")
    provider = TrackingExerciseProvider(result=_sample_batch(vocab_ids))
    app.dependency_overrides[get_exercise_ai_provider] = lambda: provider

    try:
        # First generation: calls AI
        resp1 = client.post(
            "/api/v1/ai/exercises/generate",
            headers=headers,
            json={
                "source_mode": "custom",
                "vocabulary_ids": vocab_ids,
                "exercise_type": "multiple_choice",
                "count": 2,
            },
        )
        assert resp1.status_code == 200
        data1 = resp1.json()
        assert data1["created_count"] == 2
        assert data1["resumed"] is False
        assert provider.call_count == 1

        # Check GET /api/v1/ai/exercises/active returns the active session
        resp_active = client.get("/api/v1/ai/exercises/active", headers=headers)
        assert resp_active.status_code == 200
        assert resp_active.json()["created_count"] == 2
        assert resp_active.json()["resumed"] is True

        # Second generation attempt without finishing: returns existing session, NO new AI call
        resp2 = client.post(
            "/api/v1/ai/exercises/generate",
            headers=headers,
            json={
                "source_mode": "custom",
                "vocabulary_ids": vocab_ids,
                "exercise_type": "multiple_choice",
                "count": 2,
            },
        )
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2["created_count"] == 2
        assert data2["resumed"] is True
        assert {item["id"] for item in data2["items"]} == {item["id"] for item in data1["items"]}
        # AI was NOT called again!
        assert provider.call_count == 1

    finally:
        app.dependency_overrides.pop(get_exercise_ai_provider, None)


def test_completed_session_allows_new_generation_after_cooldown(
    client: TestClient,
    general_english_track_id: uuid.UUID,
    session_factory: sessionmaker[Session],
) -> None:
    headers, vocab_ids = _setup_user_and_words(client, general_english_track_id, "completed_user@example.com")
    provider = TrackingExerciseProvider(result=_sample_batch(vocab_ids))
    app.dependency_overrides[get_exercise_ai_provider] = lambda: provider

    try:
        # 1. First generation
        resp1 = client.post(
            "/api/v1/ai/exercises/generate",
            headers=headers,
            json={
                "source_mode": "custom",
                "vocabulary_ids": vocab_ids,
                "exercise_type": "multiple_choice",
                "count": 2,
            },
        )
        assert resp1.status_code == 200
        exercises = resp1.json()["items"]
        assert provider.call_count == 1

        # 2. Attempt both exercises (completing the session)
        for ex in exercises:
            submit_resp = client.post(
                f"/api/v1/exercises/{ex['id']}/attempts",
                headers=headers,
                json={"answer": "A"},
            )
            assert submit_resp.status_code == 200

        # Active endpoint now returns empty
        active_resp = client.get("/api/v1/ai/exercises/active", headers=headers)
        assert active_resp.status_code == 200
        assert active_resp.json()["created_count"] == 0

        # 3. Trying to generate immediately hits cooldown
        resp_cooldown = client.post(
            "/api/v1/ai/exercises/generate",
            headers=headers,
            json={
                "source_mode": "custom",
                "vocabulary_ids": vocab_ids,
                "exercise_type": "multiple_choice",
                "count": 2,
            },
        )
        assert resp_cooldown.status_code == 429
        assert "Retry-After" in resp_cooldown.headers
        assert "quá nhanh" in resp_cooldown.json()["detail"]

        # 4. Clear user cooldown to simulate time passing
        with session_factory() as db:
            user = db.scalar(select(User).where(User.email == "completed_user@example.com"))
            ai_guard.reset_user(user.id)

        # 5. New generation succeeds
        resp3 = client.post(
            "/api/v1/ai/exercises/generate",
            headers=headers,
            json={
                "source_mode": "custom",
                "vocabulary_ids": vocab_ids,
                "exercise_type": "multiple_choice",
                "count": 2,
            },
        )
        assert resp3.status_code == 200
        assert resp3.json()["resumed"] is False
        assert provider.call_count == 2

    finally:
        app.dependency_overrides.pop(get_exercise_ai_provider, None)


def test_cooldown_isolation_between_different_users(
    client: TestClient,
    general_english_track_id: uuid.UUID,
) -> None:
    headers1, vocab_ids1 = _setup_user_and_words(client, general_english_track_id, "user1@example.com")
    headers2, vocab_ids2 = _setup_user_and_words(client, general_english_track_id, "user2@example.com")

    provider = TrackingExerciseProvider(result=_sample_batch(vocab_ids1))
    app.dependency_overrides[get_exercise_ai_provider] = lambda: provider

    try:
        # User 1 generates
        resp1 = client.post(
            "/api/v1/ai/exercises/generate",
            headers=headers1,
            json={"source_mode": "custom", "vocabulary_ids": vocab_ids1, "exercise_type": "multiple_choice", "count": 2},
        )
        assert resp1.status_code == 200

        # User 2 generates immediately without being blocked by User 1's cooldown
        provider.result = _sample_batch(vocab_ids2)
        resp2 = client.post(
            "/api/v1/ai/exercises/generate",
            headers=headers2,
            json={"source_mode": "custom", "vocabulary_ids": vocab_ids2, "exercise_type": "multiple_choice", "count": 2},
        )
        assert resp2.status_code == 200
        assert provider.call_count == 2

    finally:
        app.dependency_overrides.pop(get_exercise_ai_provider, None)


def test_ai_vocabulary_guard_and_no_auto_regeneration(
    client: TestClient,
    general_english_track_id: uuid.UUID,
) -> None:
    headers, _ = _setup_user_and_words(client, general_english_track_id, "vocab_ai_user@example.com")
    mock_candidate = {
        "word": "solitude",
        "ipa": "/ˈsɒl.ɪ.tʃuːd/",
        "part_of_speech": "noun",
        "definition": "The state or situation of being alone.",
        "translation": "sự cô độc tĩnh lặng",
        "examples": ["He enjoyed the peace and solitude of the woods."],
        "cefr_level": "B2",
        "topic": "Personal Development",
    }
    provider = TrackingVocabularyProvider(result=mock_candidate)
    app.dependency_overrides[get_vocabulary_ai_provider] = lambda: provider

    try:
        resp1 = client.post(
            "/api/v1/ai/vocabulary",
            headers=headers,
            json={
                "word": "solitude",
                "part_of_speech": "noun",
                "translation": "sự cô độc tĩnh lặng",
            },
        )
        assert resp1.status_code == 200
        assert resp1.json()["definition"] == "The state or situation of being alone."
        assert provider.call_count == 1

        # Immediate repeat within 5 seconds triggers cooldown
        resp2 = client.post(
            "/api/v1/ai/vocabulary",
            headers=headers,
            json={
                "word": "solitude",
                "part_of_speech": "noun",
                "translation": "sự cô độc tĩnh lặng",
            },
        )
        assert resp2.status_code == 429
        assert "quá nhanh" in resp2.json()["detail"]
        assert provider.call_count == 1

    finally:
        app.dependency_overrides.pop(get_vocabulary_ai_provider, None)


def test_provider_bounded_retry_on_transient_error() -> None:
    provider = OpenAICompatibleVocabularyProvider(
        api_key="test-api-key",
        model="test-model",
        timeout_seconds=5.0,
        max_output_tokens=500,
    )

    mock_client = MagicMock()
    # 1st call fails with APITimeoutError, 2nd call succeeds
    mock_parsed_response = MagicMock()
    mock_parsed_response.output_parsed = MagicMock(
        model_dump=lambda **kwargs: {"word": "test", "ipa": "/test/", "part_of_speech": "noun", "definition": "A test definition.", "translation": "bài kiểm tra", "examples": ["This is a test."], "cefr_level": "A1", "topic": "School"}
    )
    mock_client.responses.parse.side_effect = [
        APITimeoutError(request=MagicMock()),
        mock_parsed_response,
    ]

    with patch("openai.OpenAI", return_value=mock_client), patch("time.sleep", return_value=None):
        result = provider.generate_vocabulary("test", "noun", "bài kiểm tra")
        assert result["word"] == "test"
        assert mock_client.responses.parse.call_count == 2
