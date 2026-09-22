from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.ai.chat_agent import run_chat_agent
from app.ai.chat_schema import Message, ProviderResult, ProviderToolCall
from app.ai.dependencies import get_chat_ai_provider
from app.ai.prompts import CHAT_ASSISTANT_SYSTEM_PROMPT
from app.ai.provider import (
    AIProviderError,
    AIProviderResponseError,
    ChatAIProvider,
)
from app.ai.tools.executor import ToolExecutionError
from app.main import app
from app.models.language import Language
from app.models.learning_track import LearningTrack
from app.models.user import User
from app.models.vocabulary import Vocabulary
from app.services.ai_guard import ai_guard

PASSWORD = "StrongPassword123!"


def authenticate(client: TestClient, email: str = "phase3-learner@example.com") -> dict[str, str]:
    registration = client.post(
        "/api/v1/auth/register", json={"email": email, "password": PASSWORD}
    )
    assert registration.status_code == 201
    login = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert login.status_code == 200
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def create_test_user(db: Session, email_prefix: str = "phase3") -> User:
    unique_email = f"{email_prefix}_{uuid4().hex[:8]}@example.com"
    user = User(
        email=unique_email,
        normalized_email=unique_email.lower(),
        password_hash="hashed_pw_test",
        role="user",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_test_track(db: Session) -> LearningTrack:
    lang = db.query(Language).filter(Language.code == "en").first()
    if not lang:
        lang = Language(code="en", name="English")
        db.add(lang)
        db.commit()
        db.refresh(lang)
    track = db.query(LearningTrack).filter(LearningTrack.code == "en-default").first()
    if not track:
        track = LearningTrack(
            language_id=lang.id,
            code="en-default",
            name="General English",
            level_framework="CEFR",
        )
        db.add(track)
        db.commit()
        db.refresh(track)
    return track


def create_test_vocab(
    db: Session,
    user_id: UUID,
    track_id: UUID,
    word: str,
    status: str = "new",
    next_review_at: datetime | None = None,
) -> Vocabulary:
    vocab = Vocabulary(
        user_id=user_id,
        learning_track_id=track_id,
        word=word,
        normalized_word=word.lower().strip(),
        part_of_speech="noun",
        meaning=f"Meaning of {word}",
        translation=f"Nghia cua {word}",
        translation_language_code="vi",
        level_code="A1",
        learning_status=status,
        next_review_at=next_review_at,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(vocab)
    db.commit()
    db.refresh(vocab)
    return vocab


class FakeToolCallingProvider(ChatAIProvider):
    """Mock provider with programmed sequence of responses for testing tool calling."""

    def __init__(self, responses: list[ProviderResult | Exception] | None = None) -> None:
        self.responses = responses or []
        self.call_count = 0
        self.recorded_calls: list[dict[str, Any]] = []

    def generate_chat_response(self, messages: list[dict[str, str]]) -> str:
        raise NotImplementedError

    def generate_chat_response_with_tools(
        self,
        messages: list[Message],
        tool_definitions: list[dict],
    ) -> ProviderResult:
        self.recorded_calls.append({
            "messages": list(messages),
            "tool_definitions": list(tool_definitions),
        })
        if self.call_count < len(self.responses):
            result = self.responses[self.call_count]
            self.call_count += 1
            if isinstance(result, Exception):
                raise result
            return result
        return {"content": "Fallback answer"}


@pytest.fixture(autouse=True)
def clear_ai_guard_state():
    ai_guard._users.clear()
    yield
    ai_guard._users.clear()


# 1. Direct answer (no tool calls)
def test_single_agent_no_tool_calls_direct_answer(
    session_factory: Any,
) -> None:
    session = session_factory()
    user = create_test_user(session)
    provider = FakeToolCallingProvider(
        responses=[{"content": "Hello! I am your AI assistant."}]
    )
    reply = run_chat_agent(
        provider=provider,
        messages=[
            {"role": "system", "content": CHAT_ASSISTANT_SYSTEM_PROMPT},
            {"role": "user", "content": "Hi there!"},
        ],
        db=session,
        user_id=user.id,
    )
    assert reply == "Hello! I am your AI assistant."
    assert provider.call_count == 1
    recorded = provider.recorded_calls[0]["messages"]
    assert len(recorded) == 2  # System + User


# 2. get_learning_stats tool call
def test_single_agent_get_learning_stats_tool_call(
    session_factory: Any,
) -> None:
    session = session_factory()
    user = create_test_user(session)
    track = create_test_track(session)
    create_test_vocab(session, user_id=user.id, track_id=track.id, word="apple", status="learning")
    create_test_vocab(session, user_id=user.id, track_id=track.id, word="banana", status="mastered")

    provider = FakeToolCallingProvider(
        responses=[
            # Round 1: Model requests get_learning_stats
            {
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_stats_1",
                        "name": "get_learning_stats",
                        "arguments": "{}",
                    }
                ],
            },
            # Round 2: Model receives stats and gives final answer
            {
                "content": "You have 2 words in total: 1 learning and 1 mastered!",
            },
        ]
    )

    reply = run_chat_agent(
        provider=provider,
        messages=[
            {"role": "system", "content": CHAT_ASSISTANT_SYSTEM_PROMPT},
            {"role": "user", "content": "How am I doing?"},
        ],
        db=session,
        user_id=user.id,
    )

    assert reply == "You have 2 words in total: 1 learning and 1 mastered!"
    assert provider.call_count == 2

    round2_messages = provider.recorded_calls[1]["messages"]
    assert len(round2_messages) == 4
    assert round2_messages[2]["role"] == "assistant"
    assert round2_messages[2]["tool_calls"][0]["name"] == "get_learning_stats"
    assert round2_messages[3]["role"] == "tool"
    assert round2_messages[3]["tool_call_id"] == "call_stats_1"

    tool_result = json.loads(round2_messages[3]["content"])
    assert tool_result["total_vocabulary"] == 2
    assert tool_result["learning_words"] == 1
    assert tool_result["mastered_words"] == 1


# 3. get_due_vocabulary tool call
def test_single_agent_get_due_vocabulary_tool_call(
    session_factory: Any,
) -> None:
    session = session_factory()
    user = create_test_user(session)
    track = create_test_track(session)
    past_time = datetime.now(timezone.utc) - timedelta(days=1)
    create_test_vocab(
        session,
        user_id=user.id,
        track_id=track.id,
        word="diligent",
        status="learning",
        next_review_at=past_time,
    )

    provider = FakeToolCallingProvider(
        responses=[
            {
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_due_1",
                        "name": "get_due_vocabulary",
                        "arguments": json.dumps({"limit": 5}),
                    }
                ],
            },
            {
                "content": "You have 1 word due for review: diligent.",
            },
        ]
    )

    reply = run_chat_agent(
        provider=provider,
        messages=[
            {"role": "system", "content": CHAT_ASSISTANT_SYSTEM_PROMPT},
            {"role": "user", "content": "What words do I need to review?"},
        ],
        db=session,
        user_id=user.id,
    )

    assert reply == "You have 1 word due for review: diligent."
    assert provider.call_count == 2

    round2_messages = provider.recorded_calls[1]["messages"]
    assert round2_messages[3]["role"] == "tool"
    due_result = json.loads(round2_messages[3]["content"])
    assert "items" in due_result
    assert len(due_result["items"]) == 1
    assert due_result["items"][0]["word"] == "diligent"


# 4. Multi-round tool calling allows final answer
def test_multi_turn_tool_calling_within_rounds(
    session_factory: Any,
) -> None:
    session = session_factory()
    user = create_test_user(session)
    provider = FakeToolCallingProvider(
        responses=[
            # Round 1
            {
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_1",
                        "name": "get_learning_stats",
                        "arguments": "{}",
                    }
                ],
            },
            # Round 2
            {
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_2",
                        "name": "get_due_vocabulary",
                        "arguments": "{}",
                    }
                ],
            },
            # Round 3 (Final answer after 2 tool execution rounds)
            {
                "content": "Finished fetching stats and due words.",
            },
        ]
    )

    reply = run_chat_agent(
        provider=provider,
        messages=[
            {"role": "system", "content": CHAT_ASSISTANT_SYSTEM_PROMPT},
            {"role": "user", "content": "Check everything"},
        ],
        db=session,
        user_id=user.id,
        max_tool_rounds=3,
    )

    assert reply == "Finished fetching stats and due words."
    assert provider.call_count == 3


# 5. Exceeded max_tool_rounds raises AIProviderResponseError
def test_max_tool_rounds_bounded_limit_raises(
    session_factory: Any,
) -> None:
    session = session_factory()
    user = create_test_user(session)
    provider = FakeToolCallingProvider(
        responses=[
            {
                "content": None,
                "tool_calls": [
                    {
                        "id": f"call_{i}",
                        "name": "get_learning_stats",
                        "arguments": "{}",
                    }
                ],
            }
            for i in range(5)
        ]
    )

    with pytest.raises(AIProviderResponseError) as exc_info:
        run_chat_agent(
            provider=provider,
            messages=[
                {"role": "system", "content": CHAT_ASSISTANT_SYSTEM_PROMPT},
                {"role": "user", "content": "Loop forever"},
            ],
            db=session,
            user_id=user.id,
            max_tool_rounds=2,
        )

    assert exc_info.value.stage == "max_tool_rounds_exceeded"


# 6. Unknown tool recovers via sanitized observation
def test_unknown_tool_recovers_via_sanitized_observation(
    session_factory: Any,
) -> None:
    session = session_factory()
    user = create_test_user(session)
    provider = FakeToolCallingProvider(
        responses=[
            {
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_unknown",
                        "name": "non_existent_tool",
                        "arguments": "{}",
                    }
                ],
            },
            {
                "content": "Sorry, I could not execute that operation.",
            },
        ]
    )

    reply = run_chat_agent(
        provider=provider,
        messages=[
            {"role": "system", "content": CHAT_ASSISTANT_SYSTEM_PROMPT},
            {"role": "user", "content": "Do unknown action"},
        ],
        db=session,
        user_id=user.id,
    )

    assert reply == "Sorry, I could not execute that operation."
    round2_messages = provider.recorded_calls[1]["messages"]
    tool_turn = round2_messages[3]
    assert tool_turn["role"] == "tool"
    obs = json.loads(tool_turn["content"])
    assert obs == {"ok": False, "error": "unknown_tool"}


# 7. Malformed tool arguments recovers via sanitized observation
def test_malformed_tool_arguments_recovers_via_sanitized_observation(
    session_factory: Any,
) -> None:
    session = session_factory()
    user = create_test_user(session)
    provider = FakeToolCallingProvider(
        responses=[
            {
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_bad_args",
                        "name": "get_due_vocabulary",
                        "arguments": "{bad json",
                    }
                ],
            },
            {
                "content": "Recovered from invalid arguments.",
            },
        ]
    )

    reply = run_chat_agent(
        provider=provider,
        messages=[
            {"role": "system", "content": CHAT_ASSISTANT_SYSTEM_PROMPT},
            {"role": "user", "content": "Check words"},
        ],
        db=session,
        user_id=user.id,
    )

    assert reply == "Recovered from invalid arguments."
    round2_messages = provider.recorded_calls[1]["messages"]
    tool_turn = round2_messages[3]
    assert tool_turn["role"] == "tool"
    obs = json.loads(tool_turn["content"])
    assert obs == {"ok": False, "error": "invalid_tool_arguments"}


# 8. ToolExecutionError is a hard stop
def test_tool_execution_error_hard_stop(
    monkeypatch: pytest.MonkeyPatch,
    session_factory: Any,
) -> None:
    from app.ai import chat_agent

    def fail_execute(*args, **kwargs):
        raise ToolExecutionError("Database connection dropped during tool execution")

    monkeypatch.setattr(chat_agent, "execute_tool", fail_execute)

    session = session_factory()
    user = create_test_user(session)
    provider = FakeToolCallingProvider(
        responses=[
            {
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_err",
                        "name": "get_learning_stats",
                        "arguments": "{}",
                    }
                ],
            }
        ]
    )

    with pytest.raises(ToolExecutionError) as exc_info:
        run_chat_agent(
            provider=provider,
            messages=[
                {"role": "system", "content": CHAT_ASSISTANT_SYSTEM_PROMPT},
                {"role": "user", "content": "Stats please"},
            ],
            db=session,
            user_id=user.id,
        )

    assert "Database connection dropped" in str(exc_info.value)


# 9. Provider failure is a hard stop
def test_provider_failure_hard_stop(
    session_factory: Any,
) -> None:
    session = session_factory()
    user = create_test_user(session)
    provider = FakeToolCallingProvider(
        responses=[AIProviderError("Groq/OpenAI network failure")]
    )

    with pytest.raises(AIProviderError):
        run_chat_agent(
            provider=provider,
            messages=[
                {"role": "system", "content": CHAT_ASSISTANT_SYSTEM_PROMPT},
                {"role": "user", "content": "Hello"},
            ],
            db=session,
            user_id=user.id,
        )


# 10. Model cannot override user_id (always bound to current_user.id)
def test_model_supplied_user_id_rejected_or_ignored(
    session_factory: Any,
) -> None:
    session = session_factory()
    user1 = create_test_user(session, "user1")
    user2 = create_test_user(session, "user2")
    track = create_test_track(session)

    create_test_vocab(session, user_id=user1.id, track_id=track.id, word="user1_word")
    create_test_vocab(session, user_id=user2.id, track_id=track.id, word="user2_word")

    provider = FakeToolCallingProvider(
        responses=[
            # Attempt to inject user_id for user2 in arguments
            {
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_injection",
                        "name": "get_learning_stats",
                        "arguments": json.dumps({"user_id": str(user2.id)}),
                    }
                ],
            },
            {
                "content": "Stats retrieved.",
            },
        ]
    )

    run_chat_agent(
        provider=provider,
        messages=[
            {"role": "system", "content": CHAT_ASSISTANT_SYSTEM_PROMPT},
            {"role": "user", "content": "Give me stats"},
        ],
        db=session,
        user_id=user1.id,
    )

    round2_messages = provider.recorded_calls[1]["messages"]
    obs = json.loads(round2_messages[3]["content"])
    assert obs == {"ok": False, "error": "invalid_tool_arguments"}


# 11. Endpoint integration tests
def test_endpoint_tool_calling_success_200(
    client: TestClient,
    session_factory: Any,
) -> None:
    headers = authenticate(client, "endpoint-tool-success@example.com")

    provider = FakeToolCallingProvider(
        responses=[
            {
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_ep",
                        "name": "get_learning_stats",
                        "arguments": "{}",
                    }
                ],
            },
            {
                "content": "Endpoint: you have 0 words.",
            },
        ]
    )
    app.dependency_overrides[get_chat_ai_provider] = lambda: provider

    try:
        resp = client.post(
            "/api/v1/ai/chat",
            json={"messages": [{"role": "user", "content": "Stats?"}]},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["message"]["content"] == "Endpoint: you have 0 words."
    finally:
        app.dependency_overrides.pop(get_chat_ai_provider, None)


def test_endpoint_tool_calling_provider_error_502(
    client: TestClient,
    session_factory: Any,
) -> None:
    headers = authenticate(client, "endpoint-tool-err@example.com")

    provider = FakeToolCallingProvider(
        responses=[AIProviderResponseError("invalid_json", "Bad JSON from upstream")]
    )
    app.dependency_overrides[get_chat_ai_provider] = lambda: provider

    try:
        resp = client.post(
            "/api/v1/ai/chat",
            json={"messages": [{"role": "user", "content": "Trigger error"}]},
            headers=headers,
        )
        assert resp.status_code == 502
        assert resp.json()["detail"] == "AI service returned an invalid response."
    finally:
        app.dependency_overrides.pop(get_chat_ai_provider, None)
