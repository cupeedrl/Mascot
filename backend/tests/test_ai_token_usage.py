from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import openai
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.ai import chat_agent
from app.ai.dependencies import get_chat_ai_provider, get_vocabulary_ai_provider
from app.ai.groq_provider import GroqVocabularyProvider
from app.ai.token_usage import (
    TokenUsage,
    current_token_usage,
    record_provider_usage,
    tracks_token_usage,
)
from app.core.config import get_settings
from app.main import app
from app.models.ai_usage_log import AIUsageLog
from app.schemas.ai_vocabulary import VocabularyCandidate
from app.services.ai_guard import ai_guard
from app.services.ai_logger import record_ai_usage

PASSWORD = "StrongPassword123!"


def _auth_headers(client: TestClient, email: str) -> dict[str, str]:
    assert client.post(
        "/api/v1/auth/register", json={"email": email, "password": PASSWORD}
    ).status_code == 201
    login = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def _latest_usage_log(session_factory: Any, feature: str) -> AIUsageLog:
    with session_factory() as db:
        row = db.scalar(
            select(AIUsageLog)
            .where(AIUsageLog.feature == feature)
            .order_by(AIUsageLog.created_at.desc())
        )
    assert row is not None
    return row


def _provider(model: str = "openai/gpt-oss-20b") -> GroqVocabularyProvider:
    return GroqVocabularyProvider(
        api_key="groq-test-key",
        model=model,
        base_url="https://api.groq.com/openai/v1",
        timeout_seconds=20,
        max_output_tokens=800,
    )


# --- record_provider_usage -------------------------------------------------


def test_reads_chat_completions_usage_names() -> None:
    response = SimpleNamespace(
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=4, total_tokens=14)
    )
    assert record_provider_usage(response, "m") == {
        "prompt_tokens": 10,
        "completion_tokens": 4,
        "total_tokens": 14,
    }


def test_reads_responses_api_usage_names() -> None:
    # responses.parse() reports input_tokens/output_tokens, not prompt/completion.
    response = SimpleNamespace(
        usage=SimpleNamespace(input_tokens=30, output_tokens=12, total_tokens=42)
    )
    assert record_provider_usage(response, "m") == {
        "prompt_tokens": 30,
        "completion_tokens": 12,
        "total_tokens": 42,
    }


@pytest.mark.parametrize(
    "usage",
    [
        None,
        MagicMock(),  # attribute access returns mocks, not ints
        SimpleNamespace(prompt_tokens=True, completion_tokens=-1, total_tokens="9"),
    ],
)
def test_ignores_missing_or_untrusted_usage(usage: Any) -> None:
    tracker_calls: list[TokenUsage] = []

    @tracks_token_usage
    def endpoint() -> None:
        assert record_provider_usage(SimpleNamespace(usage=usage), "m") == {}
        tracker = current_token_usage()
        assert tracker is not None
        tracker_calls.append(tracker)

    endpoint()
    assert tracker_calls[0].provider_calls == 0


def test_tracker_accumulates_calls_and_is_reset_after_endpoint() -> None:
    seen: list[TokenUsage] = []

    @tracks_token_usage
    def endpoint() -> None:
        record_provider_usage(
            SimpleNamespace(usage=SimpleNamespace(prompt_tokens=5, completion_tokens=2, total_tokens=7)),
            "model-a",
        )
        # total_tokens missing: derived from input + output.
        record_provider_usage(
            SimpleNamespace(usage=SimpleNamespace(input_tokens=8, output_tokens=3)),
            "model-b",
        )
        tracker = current_token_usage()
        assert tracker is not None
        seen.append(tracker)

    assert current_token_usage() is None
    endpoint()
    assert current_token_usage() is None
    assert seen[0] == TokenUsage(
        input_tokens=13, output_tokens=5, total_tokens=18, provider_calls=2, model="model-b"
    )


def test_usage_without_active_tracker_is_still_returned_for_logging() -> None:
    response = SimpleNamespace(
        usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1, total_tokens=2)
    )
    assert record_provider_usage(response, "m")["total_tokens"] == 2


# --- record_ai_usage ---------------------------------------------------------


def test_record_ai_usage_explicit_tokens_win_over_tracker(session_factory: Any) -> None:
    @tracks_token_usage
    def endpoint() -> None:
        record_provider_usage(
            SimpleNamespace(usage=SimpleNamespace(prompt_tokens=99, completion_tokens=99, total_tokens=198)),
            "tracked-model",
        )
        with session_factory() as db:
            record_ai_usage(
                db,
                user_id=None,
                feature="explicit_tokens",
                model="explicit-model",
                status="success",
                input_tokens=1,
                output_tokens=2,
                total_tokens=3,
            )

    endpoint()
    row = _latest_usage_log(session_factory, "explicit_tokens")
    assert (row.input_tokens, row.output_tokens, row.total_tokens) == (1, 2, 3)
    assert row.model == "explicit-model"


def test_record_ai_usage_without_calls_uses_configured_model(session_factory: Any) -> None:
    with session_factory() as db:
        record_ai_usage(db, user_id=None, feature="no_calls", status="rate_limited")

    row = _latest_usage_log(session_factory, "no_calls")
    settings = get_settings()
    assert row.provider == settings.ai_provider
    assert row.model == (
        settings.groq_model if settings.ai_provider == "groq" else settings.openai_model
    )
    assert row.input_tokens is None and row.total_tokens is None


# --- end to end through the real provider ----------------------------------


def _chat_completion(*, content: str | None, tool_calls: list | None, usage: tuple[int, int, int]) -> Any:
    prompt, completion, total = usage
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content, tool_calls=tool_calls))],
        usage=SimpleNamespace(prompt_tokens=prompt, completion_tokens=completion, total_tokens=total),
    )


@pytest.mark.parametrize("engine", ["langgraph", "legacy"])
def test_chat_route_records_tokens_summed_over_tool_rounds(
    monkeypatch: pytest.MonkeyPatch,
    client: TestClient,
    session_factory: Any,
    engine: str,
) -> None:
    replies = [
        _chat_completion(
            content=None,
            tool_calls=[
                SimpleNamespace(
                    id="stats-1",
                    function=SimpleNamespace(name="get_learning_stats", arguments="{}"),
                )
            ],
            usage=(100, 20, 120),
        ),
        _chat_completion(content="You have no vocabulary yet.", tool_calls=None, usage=(150, 30, 180)),
    ]

    class FakeOpenAI:
        def __init__(self, **kwargs: Any) -> None:
            self.chat = SimpleNamespace(
                completions=SimpleNamespace(create=lambda **_: replies.pop(0))
            )

    monkeypatch.setattr(openai, "OpenAI", FakeOpenAI)
    monkeypatch.setattr(chat_agent, "get_settings", lambda: SimpleNamespace(ai_agent_engine=engine))
    provider = _provider()
    headers = _auth_headers(client, f"token-usage-chat-{engine}@example.com")
    ai_guard._users.clear()
    app.dependency_overrides[get_chat_ai_provider] = lambda: provider

    try:
        response = client.post(
            "/api/v1/ai/chat",
            headers=headers,
            json={"messages": [{"role": "user", "content": "Show my stats"}]},
        )
    finally:
        app.dependency_overrides.pop(get_chat_ai_provider, None)
        ai_guard._users.clear()

    assert response.status_code == 200, response.text
    assert replies == []
    row = _latest_usage_log(session_factory, "ai_chat")
    assert (row.input_tokens, row.output_tokens, row.total_tokens) == (250, 50, 300)


def _vocabulary_candidate() -> VocabularyCandidate:
    return VocabularyCandidate(
        word="solely",
        part_of_speech="adverb",
        translation="chỉ, duy nhất",
        ipa="/ˈsəʊl.li/",
        definition="Only and not involving anything else.",
        cefr_level="B2",
        examples=["The decision was based solely on cost."],
        topic="Khác",
    )


@pytest.mark.parametrize(
    ("output_parsed", "expected_status"),
    [(_vocabulary_candidate(), 200), (None, 502)],
)
def test_vocabulary_route_records_responses_api_tokens_and_used_model(
    monkeypatch: pytest.MonkeyPatch,
    client: TestClient,
    session_factory: Any,
    output_parsed: Any,
    expected_status: int,
) -> None:
    class FakeOpenAI:
        def __init__(self, **kwargs: Any) -> None:
            self.responses = SimpleNamespace(
                parse=lambda **_: SimpleNamespace(
                    output_parsed=output_parsed,
                    status="completed",
                    usage=SimpleNamespace(input_tokens=40, output_tokens=60, total_tokens=100),
                )
            )

    monkeypatch.setattr(openai, "OpenAI", FakeOpenAI)
    provider = _provider(model="tracked/model")
    headers = _auth_headers(client, f"token-usage-vocab-{expected_status}@example.com")
    ai_guard._users.clear()
    app.dependency_overrides[get_vocabulary_ai_provider] = lambda: provider

    try:
        response = client.post(
            "/api/v1/ai/vocabulary",
            headers=headers,
            json={"word": "solely", "part_of_speech": "adverb", "translation": "chỉ, duy nhất"},
        )
    finally:
        app.dependency_overrides.pop(get_vocabulary_ai_provider, None)
        ai_guard._users.clear()

    assert response.status_code == expected_status, response.text
    row = _latest_usage_log(session_factory, "vocabulary_enrichment")
    # Tokens are recorded even when the output is unusable: the call was billed.
    assert (row.input_tokens, row.output_tokens, row.total_tokens) == (40, 60, 100)
    assert row.model == "tracked/model"
