from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.ai.chat_schema import Message, ProviderResult
from app.ai.dependencies import get_chat_ai_provider
from app.ai.prompts import CHAT_ASSISTANT_SYSTEM_PROMPT
from app.ai.provider import ChatAIProvider
from app.ai.tools.executor import ToolValidationError, execute_tool
from app.ai.tools.registry import TOOL_REGISTRY
from app.main import app
from app.models.exercise import Exercise
from app.models.exercise_attempt import ExerciseAttempt
from app.models.user import User
from app.models.vocabulary import Vocabulary
from app.services.ai_guard import ai_guard
from app.services.learning_profile import (
    LearningProfileTrackUnavailableError,
    get_learning_profile,
)
from tests.test_multilingual_foundation import Tracks, multilingual_tracks

PASSWORD = "StrongPassword123!"


class RecordingProvider(ChatAIProvider):
    def __init__(self, responses: list[ProviderResult]) -> None:
        self.responses = responses
        self.calls: list[list[Message]] = []
        self.tool_definitions: list[dict[str, Any]] = []

    def generate_chat_response(self, messages: list[dict[str, str]]) -> str:
        raise AssertionError("plain chat fallback must not run")

    def generate_chat_response_with_tools(
        self,
        messages: list[Message],
        tool_definitions: list[dict[str, Any]],
    ) -> ProviderResult:
        self.calls.append(list(messages))
        self.tool_definitions = tool_definitions
        return self.responses[len(self.calls) - 1]


@pytest.fixture(autouse=True)
def clear_chat_state() -> None:
    ai_guard._users.clear()
    yield
    ai_guard._users.clear()
    app.dependency_overrides.pop(get_chat_ai_provider, None)


def create_user(db: Session, label: str) -> User:
    email = f"{label}-{uuid4().hex[:8]}@example.com"
    user = User(
        email=email,
        normalized_email=email,
        password_hash="hashed",
        role="user",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate(client: TestClient, email: str) -> tuple[dict[str, str], UUID]:
    registered = client.post(
        "/api/v1/auth/register", json={"email": email, "password": PASSWORD}
    )
    login = client.post(
        "/api/v1/auth/login", json={"email": email, "password": PASSWORD}
    )
    return {
        "Authorization": f"Bearer {login.json()['access_token']}"
    }, UUID(registered.json()["id"])


def add_vocabulary(
    db: Session,
    *,
    user_id: UUID,
    track_id: UUID,
    word: str,
    level: str,
    status: str = "new",
    topic: str | None = "Daily Life",
    next_review_at: datetime | None = None,
    created_at: datetime | None = None,
) -> Vocabulary:
    item = Vocabulary(
        user_id=user_id,
        learning_track_id=track_id,
        word=word,
        normalized_word=word.casefold(),
        ipa=None,
        part_of_speech="noun",
        meaning=f"Meaning of {word}",
        translation=f"Nghĩa của {word}",
        translation_language_code="vi",
        example_sentences=[],
        level_code=level,
        topic=topic,
        learning_status=status,
        review_count=0,
        correct_count=0,
        incorrect_count=0,
        next_review_at=next_review_at,
        created_at=created_at or datetime.now(UTC),
        updated_at=created_at or datetime.now(UTC),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def add_attempts(
    db: Session,
    *,
    user_id: UUID,
    track_id: UUID,
    results: list[bool],
) -> None:
    exercise = Exercise(
        user_id=user_id,
        learning_track_id=track_id,
        exercise_type="multiple_choice",
        prompt="Choose the answer.",
        options=[{"id": "A", "text": "answer"}],
        correct_answer="A",
        accepted_answers=[],
        source="manual",
    )
    db.add(exercise)
    db.flush()
    now = datetime.now(UTC)
    db.add_all(
        [
            ExerciseAttempt(
                user_id=user_id,
                exercise_id=exercise.id,
                user_answer="A" if is_correct else "B",
                correct_answer="A",
                is_correct=is_correct,
                completed_at=now + timedelta(microseconds=index),
            )
            for index, is_correct in enumerate(results)
        ]
    )
    db.commit()


def test_profile_is_user_and_english_track_scoped(
    session_factory: Any, multilingual_tracks: Tracks
) -> None:
    with session_factory() as db:
        owner = create_user(db, "profile-owner")
        other = create_user(db, "profile-other")
        add_vocabulary(
            db,
            user_id=owner.id,
            track_id=multilingual_tracks.english.id,
            word="resilient",
            level="B2",
            status="learning",
        )
        add_vocabulary(
            db,
            user_id=owner.id,
            track_id=multilingual_tracks.chinese.id,
            word="学习",
            level="HSK1",
            status="mastered",
        )
        add_vocabulary(
            db,
            user_id=other.id,
            track_id=multilingual_tracks.english.id,
            word="private",
            level="C1",
        )

        profile = get_learning_profile(
            db, owner.id, learning_track_id=multilingual_tracks.english.id
        )

    assert profile.language_code == "en"
    assert profile.framework == "CEFR"
    assert profile.total_vocabulary == 1
    assert profile.learning_words == 1
    assert profile.mastered_words == 0


def test_profile_is_chinese_track_scoped_without_english_mixing(
    session_factory: Any, multilingual_tracks: Tracks
) -> None:
    with session_factory() as db:
        user = create_user(db, "profile-chinese")
        add_vocabulary(
            db,
            user_id=user.id,
            track_id=multilingual_tracks.english.id,
            word="english-only",
            level="A1",
        )
        add_vocabulary(
            db,
            user_id=user.id,
            track_id=multilingual_tracks.chinese.id,
            word="你好",
            level="HSK1",
            status="review",
        )
        profile = get_learning_profile(
            db, user.id, learning_track_id=multilingual_tracks.chinese.id
        )

    assert profile.language_code == "zh"
    assert profile.framework == "HSK"
    assert profile.total_vocabulary == 1
    assert profile.review_words == 1


def test_current_level_is_unknown_without_authoritative_assessment(
    session_factory: Any, multilingual_tracks: Tracks
) -> None:
    with session_factory() as db:
        user = create_user(db, "profile-level")
        for word, level in (("basic", "A1"), ("advanced", "C1")):
            add_vocabulary(
                db,
                user_id=user.id,
                track_id=multilingual_tracks.english.id,
                word=word,
                level=level,
            )
        profile = get_learning_profile(
            db, user.id, learning_track_id=multilingual_tracks.english.id
        )

    assert profile.current_level is None


def test_recent_accuracy_uses_only_recent_track_attempts(
    session_factory: Any, multilingual_tracks: Tracks
) -> None:
    with session_factory() as db:
        user = create_user(db, "profile-accuracy")
        other = create_user(db, "profile-accuracy-other")
        add_attempts(
            db,
            user_id=user.id,
            track_id=multilingual_tracks.english.id,
            results=[True, True, False],
        )
        add_attempts(
            db,
            user_id=user.id,
            track_id=multilingual_tracks.chinese.id,
            results=[False, False],
        )
        add_attempts(
            db,
            user_id=other.id,
            track_id=multilingual_tracks.english.id,
            results=[False],
        )
        profile = get_learning_profile(
            db, user.id, learning_track_id=multilingual_tracks.english.id
        )

    assert profile.recent_attempts == 3
    assert profile.recent_accuracy == 0.67


def test_weak_topics_use_due_review_pressure_and_recent_topics_are_ordered(
    session_factory: Any, multilingual_tracks: Tracks
) -> None:
    with session_factory() as db:
        user = create_user(db, "profile-topics")
        now = datetime.now(UTC)
        for index in range(3):
            add_vocabulary(
                db,
                user_id=user.id,
                track_id=multilingual_tracks.english.id,
                word=f"travel-{index}",
                level="A2",
                topic="Travel",
                created_at=now + timedelta(seconds=index),
            )
        for index in range(2):
            add_vocabulary(
                db,
                user_id=user.id,
                track_id=multilingual_tracks.english.id,
                word=f"school-{index}",
                level="A2",
                topic="School",
                created_at=now + timedelta(seconds=10 + index),
            )
        add_vocabulary(
            db,
            user_id=user.id,
            track_id=multilingual_tracks.english.id,
            word="future-health",
            level="A2",
            topic="Health",
            next_review_at=now + timedelta(days=2),
            created_at=now + timedelta(seconds=20),
        )
        profile = get_learning_profile(
            db,
            user.id,
            learning_track_id=multilingual_tracks.english.id,
            now=now,
        )

    assert profile.weak_topics == ["Travel", "School"]
    assert profile.recent_topics == ["Health", "School", "Travel"]


def test_weak_topics_are_empty_when_evidence_is_insufficient(
    session_factory: Any, multilingual_tracks: Tracks
) -> None:
    with session_factory() as db:
        user = create_user(db, "profile-insufficient")
        add_vocabulary(
            db,
            user_id=user.id,
            track_id=multilingual_tracks.english.id,
            word="single",
            level="A1",
            topic="School",
        )
        profile = get_learning_profile(
            db, user.id, learning_track_id=multilingual_tracks.english.id
        )

    assert profile.weak_topics == []
    assert profile.recent_accuracy is None
    assert profile.recent_attempts == 0


def test_profile_tool_has_no_model_controlled_identity_or_track(
    session_factory: Any, multilingual_tracks: Tracks
) -> None:
    with session_factory() as db:
        user = create_user(db, "profile-tool")
        result = execute_tool(
            "get_learning_profile",
            {},
            db,
            user.id,
            learning_track_id=multilingual_tracks.chinese.id,
        )
        with pytest.raises(ToolValidationError):
            execute_tool(
                "get_learning_profile",
                {"user_id": str(user.id)},
                db,
                user.id,
                learning_track_id=multilingual_tracks.chinese.id,
            )

    assert result["language_code"] == "zh"
    assert result["current_level"] is None


def test_unknown_track_is_rejected_instead_of_aggregating_data(
    session_factory: Any
) -> None:
    with session_factory() as db:
        user = create_user(db, "profile-missing-track")
        with pytest.raises(LearningProfileTrackUnavailableError):
            get_learning_profile(db, user.id, learning_track_id=uuid4())


def test_recommendation_routes_to_profile_and_persists_only_visible_messages(
    client: TestClient,
    session_factory: Any,
    multilingual_tracks: Tracks,
) -> None:
    headers, user_id = authenticate(client, "profile-recommendation@example.com")
    with session_factory() as db:
        for index in range(2):
            add_vocabulary(
                db,
                user_id=user_id,
                track_id=multilingual_tracks.chinese.id,
                word=f"词{index}",
                level="HSK1",
                topic="School",
            )
    provider = RecordingProvider(
        [
            {
                "tool_calls": [
                    {
                        "id": "profile-1",
                        "name": "get_learning_profile",
                        "arguments": "{}",
                    }
                ]
            },
            {"content": "Bạn có 2 từ đến hạn; hôm nay hãy ưu tiên ôn nhóm School."},
        ]
    )
    app.dependency_overrides[get_chat_ai_provider] = lambda: provider

    response = client.post(
        "/api/v1/ai/chat",
        headers=headers,
        json={
            "message": "Hôm nay tôi nên học gì?",
            "learning_track_id": str(multilingual_tracks.chinese.id),
        },
    )

    assert response.status_code == 200
    tool_payload = json.loads(provider.calls[1][-1]["content"])
    assert tool_payload["language_code"] == "zh"
    assert tool_payload["due_words"] == 2
    assert tool_payload["weak_topics"] == ["School"]
    assert "2 từ" in response.json()["message"]["content"]
    restored = client.get(
        f"/api/v1/ai/conversations/{response.json()['conversation_id']}",
        headers=headers,
    ).json()
    assert len(restored["messages"]) == 2
    assert all(message["role"] in {"user", "assistant"} for message in restored["messages"])
    assert not any("due_words" in message["content"] for message in restored["messages"])


@pytest.mark.parametrize(
    ("message", "expected_hint", "final_answer"),
    [
        ("Hôm nay tôi nên học gì?", "Respond in Vietnamese", "Bạn nên ôn các từ đến hạn."),
        ("What should I study today?", "Respond in English", "Review your due words first."),
        ("我今天应该学什么？", "Respond in Chinese", "先复习到期的词汇。"),
    ],
)
def test_profile_recommendation_preserves_response_language(
    client: TestClient,
    multilingual_tracks: Tracks,
    message: str,
    expected_hint: str,
    final_answer: str,
) -> None:
    provider = RecordingProvider(
        [
            {
                "tool_calls": [
                    {
                        "id": "profile-language",
                        "name": "get_learning_profile",
                        "arguments": "{}",
                    }
                ]
            },
            {"content": final_answer},
        ]
    )
    app.dependency_overrides[get_chat_ai_provider] = lambda: provider
    headers, _ = authenticate(
        client, f"profile-language-{len(message)}-{uuid4().hex[:6]}@example.com"
    )

    response = client.post(
        "/api/v1/ai/chat",
        headers=headers,
        json={
            "message": message,
            "learning_track_id": str(multilingual_tracks.chinese.id),
        },
    )

    assert response.status_code == 200
    assert response.json()["message"]["content"] == final_answer
    assert expected_hint in provider.calls[1][1]["content"]


def test_prompt_and_registry_distinguish_profile_stats_due_and_writes() -> None:
    assert set(TOOL_REGISTRY) == {
        "get_learning_stats",
        "get_due_vocabulary",
        "get_learning_profile",
        "add_vocabulary",
    }
    assert TOOL_REGISTRY["get_learning_profile"]["classification"] == "read"
    assert TOOL_REGISTRY["get_learning_profile"]["requires_confirmation"] is False
    assert TOOL_REGISTRY["add_vocabulary"]["classification"] == "write"
    assert TOOL_REGISTRY["add_vocabulary"]["requires_confirmation"] is True
    assert "Never infer or invent" in CHAT_ASSISTANT_SYSTEM_PROMPT
    assert "get_learning_stats for exact progress totals" in CHAT_ASSISTANT_SYSTEM_PROMPT
    assert "get_due_vocabulary for the actual due-word list" in CHAT_ASSISTANT_SYSTEM_PROMPT
