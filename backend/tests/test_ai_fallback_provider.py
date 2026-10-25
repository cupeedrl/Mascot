from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import httpx
import openai
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError
from sqlalchemy import select

from app.ai import dependencies
from app.ai.dependencies import get_chat_ai_provider
from app.ai.fallback_provider import FallbackAIProvider, should_fall_back
from app.ai.groq_provider import GroqVocabularyProvider
from app.ai.openai_provider import OpenAIVocabularyProvider
from app.ai.provider import (
    AIProviderAuthenticationError,
    AIProviderConfigurationError,
    AIProviderError,
    AIProviderNotConfiguredError,
    AIProviderQuotaError,
    AIProviderRateLimitError,
    AIProviderRequestError,
    AIProviderResponseError,
    AIProviderTimeoutError,
)
from app.core.config import Settings
from app.main import app
from app.models.ai_usage_log import AIUsageLog
from app.services.ai_guard import ai_guard

PASSWORD = "StrongPassword123!"

FALLBACK_ERRORS = [
    AIProviderRateLimitError(),
    AIProviderQuotaError(),
    AIProviderTimeoutError(),
    AIProviderError(),  # 5xx / network after the primary's own retries
]
NON_FALLBACK_ERRORS = [
    AIProviderConfigurationError(),
    AIProviderNotConfiguredError(),
    AIProviderAuthenticationError(),
    AIProviderRequestError(400),
    AIProviderResponseError(),
]
CALLS = [
    ("generate_vocabulary", ("solely", "adverb", "chỉ", None), {}),
    ("generate_exercises", ([{"word": "solely"}], "multiple_choice", 4), {}),
    ("generate_chat_response", ([{"role": "user", "content": "hi"}],), {}),
    (
        "generate_chat_response_with_tools",
        (),
        {"messages": [{"role": "user", "content": "hi"}], "tool_definitions": []},
    ),
]


class ScriptedProvider:
    """Answers every provider method with its own name, or raises ``error``."""

    def __init__(self, name: str, error: Exception | None = None) -> None:
        self.name = name
        self.error = error
        self.calls: list[str] = []

    def _answer(self, method: str) -> Any:
        self.calls.append(method)
        if self.error is not None:
            raise self.error
        return {"content": self.name}

    def generate_vocabulary(self, *args: Any, **kwargs: Any) -> Any:
        return self._answer("generate_vocabulary")

    def generate_exercises(self, *args: Any, **kwargs: Any) -> Any:
        return self._answer("generate_exercises")

    def generate_chat_response(self, *args: Any, **kwargs: Any) -> Any:
        return self._answer("generate_chat_response")

    def generate_chat_response_with_tools(self, *args: Any, **kwargs: Any) -> Any:
        return self._answer("generate_chat_response_with_tools")


def _wrap(primary: ScriptedProvider, secondary: ScriptedProvider) -> FallbackAIProvider:
    return FallbackAIProvider(
        primary, secondary, primary_name="groq", secondary_name="openai"
    )


# --- wrapper behaviour ------------------------------------------------------


@pytest.mark.parametrize(("method", "args", "kwargs"), CALLS)
def test_primary_success_never_calls_secondary(method: str, args: tuple, kwargs: dict) -> None:
    primary, secondary = ScriptedProvider("groq"), ScriptedProvider("openai")
    assert getattr(_wrap(primary, secondary), method)(*args, **kwargs) == {"content": "groq"}
    assert primary.calls == [method]
    assert secondary.calls == []


@pytest.mark.parametrize("error", FALLBACK_ERRORS, ids=lambda e: type(e).__name__)
@pytest.mark.parametrize(("method", "args", "kwargs"), CALLS)
def test_transient_primary_errors_fall_back_once(
    method: str, args: tuple, kwargs: dict, error: Exception, caplog: Any
) -> None:
    primary, secondary = ScriptedProvider("groq", error), ScriptedProvider("openai")
    with caplog.at_level("WARNING"):
        result = getattr(_wrap(primary, secondary), method)(*args, **kwargs)

    assert result == {"content": "openai"}
    assert primary.calls == [method]
    assert secondary.calls == [method]
    assert f"from=groq, to=openai, error={type(error).__name__}" in caplog.text


@pytest.mark.parametrize("error", NON_FALLBACK_ERRORS, ids=lambda e: type(e).__name__)
@pytest.mark.parametrize(("method", "args", "kwargs"), CALLS)
def test_configuration_request_and_response_errors_do_not_fall_back(
    method: str, args: tuple, kwargs: dict, error: Exception
) -> None:
    primary, secondary = ScriptedProvider("groq", error), ScriptedProvider("openai")
    with pytest.raises(type(error)):
        getattr(_wrap(primary, secondary), method)(*args, **kwargs)
    assert secondary.calls == []


def test_secondary_failure_is_raised() -> None:
    primary = ScriptedProvider("groq", AIProviderRateLimitError())
    secondary = ScriptedProvider("openai", AIProviderTimeoutError())
    with pytest.raises(AIProviderTimeoutError):
        _wrap(primary, secondary).generate_chat_response([{"role": "user", "content": "hi"}])


def test_should_fall_back_matches_error_lists() -> None:
    assert all(should_fall_back(error) for error in FALLBACK_ERRORS)
    assert not any(should_fall_back(error) for error in NON_FALLBACK_ERRORS)


# --- settings and provider factory -----------------------------------------


@pytest.mark.parametrize(("raw", "expected"), [("", None), ("  ", None), ("openai", "openai")])
def test_fallback_setting_parses_empty_as_disabled(raw: str, expected: str | None) -> None:
    assert Settings(ai_fallback_provider=raw).ai_fallback_provider == expected


def test_fallback_setting_rejects_unknown_provider() -> None:
    with pytest.raises(ValidationError):
        Settings(ai_fallback_provider="gemini")


def _factory_settings(*, fallback: str | None, openai_key: str | None = "openai-test-key") -> SimpleNamespace:
    return SimpleNamespace(
        ai_provider="groq",
        ai_fallback_provider=fallback,
        groq_api_key=SecretStr("groq-test-key"),
        groq_model="openai/gpt-oss-20b",
        groq_exercise_model="openai/gpt-oss-120b",
        groq_base_url="https://api.groq.com/openai/v1",
        openai_api_key=SecretStr(openai_key) if openai_key else None,
        openai_model="gpt-5.4-nano",
        ai_request_timeout_seconds=20.0,
        ai_max_output_tokens=800,
        ai_exercise_max_output_tokens=5000,
        ai_exercise_reasoning_effort="low",
    )


@pytest.mark.parametrize(
    ("settings", "expected_type"),
    [
        (_factory_settings(fallback=None), GroqVocabularyProvider),
        (_factory_settings(fallback="groq"), GroqVocabularyProvider),  # same as primary
        (_factory_settings(fallback="openai", openai_key=None), GroqVocabularyProvider),
        (_factory_settings(fallback="openai"), FallbackAIProvider),
    ],
    ids=["disabled", "same-provider", "missing-key", "enabled"],
)
def test_factory_wraps_only_a_usable_fallback(
    monkeypatch: pytest.MonkeyPatch, settings: SimpleNamespace, expected_type: type
) -> None:
    dependencies.get_vocabulary_ai_provider.cache_clear()
    monkeypatch.setattr(dependencies, "get_settings", lambda: settings)
    try:
        provider = dependencies.get_vocabulary_ai_provider()
    finally:
        dependencies.get_vocabulary_ai_provider.cache_clear()

    assert type(provider) is expected_type
    if isinstance(provider, FallbackAIProvider):
        assert isinstance(provider._primary, GroqVocabularyProvider)
        assert isinstance(provider._secondary, OpenAIVocabularyProvider)


# --- end to end through the chat route --------------------------------------


def _status_error(cls: type, status_code: int, url: str) -> Exception:
    response = httpx.Response(status_code, request=httpx.Request("POST", url))
    return cls("provider error", response=response, body=None)


def _completion(content: str, usage: tuple[int, int, int]) -> Any:
    prompt, completion, total = usage
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content, tool_calls=None))],
        usage=SimpleNamespace(prompt_tokens=prompt, completion_tokens=completion, total_tokens=total),
    )


def _install_fake_openai(monkeypatch: pytest.MonkeyPatch, groq_error: Exception) -> dict[str, int]:
    calls = {"groq": 0, "openai": 0}

    class FakeOpenAI:
        def __init__(self, **kwargs: Any) -> None:
            is_groq = "groq.com" in str(kwargs.get("base_url"))

            def create(**_: Any) -> Any:
                if is_groq:
                    calls["groq"] += 1
                    raise groq_error
                calls["openai"] += 1
                return _completion("Answered by OpenAI.", (70, 10, 80))

            self.chat = SimpleNamespace(completions=SimpleNamespace(create=create))

    monkeypatch.setattr(openai, "OpenAI", FakeOpenAI)
    # Skip the primary's retry backoff.
    monkeypatch.setattr("app.ai.openai_compatible_provider.time.sleep", lambda _: None)
    return calls


def _fallback_provider() -> FallbackAIProvider:
    common = {"timeout_seconds": 20, "max_output_tokens": 800}
    return FallbackAIProvider(
        GroqVocabularyProvider(
            api_key="groq-test-key",
            model="openai/gpt-oss-20b",
            base_url="https://api.groq.com/openai/v1",
            **common,
        ),
        OpenAIVocabularyProvider(api_key="openai-test-key", model="gpt-test", **common),
        primary_name="groq",
        secondary_name="openai",
    )


def _post_chat(client: TestClient, email: str) -> httpx.Response:
    assert client.post(
        "/api/v1/auth/register", json={"email": email, "password": PASSWORD}
    ).status_code == 201
    login = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    provider = _fallback_provider()
    ai_guard._users.clear()
    app.dependency_overrides[get_chat_ai_provider] = lambda: provider
    try:
        return client.post(
            "/api/v1/ai/chat",
            headers=headers,
            json={"messages": [{"role": "user", "content": "Hello"}]},
        )
    finally:
        app.dependency_overrides.pop(get_chat_ai_provider, None)
        ai_guard._users.clear()


def test_chat_route_falls_back_to_openai_and_logs_what_answered(
    monkeypatch: pytest.MonkeyPatch, client: TestClient, session_factory: Any
) -> None:
    rate_limited = _status_error(
        openai.RateLimitError, 429, "https://api.groq.com/openai/v1/chat/completions"
    )
    calls = _install_fake_openai(monkeypatch, rate_limited)

    response = _post_chat(client, "fallback-rate-limit@example.com")

    assert response.status_code == 200, response.text
    assert response.json()["message"]["content"] == "Answered by OpenAI."
    # The primary used its own retries (1 + 2) before the single fallback call.
    assert calls == {"groq": 3, "openai": 1}
    with session_factory() as db:
        row = db.scalar(
            select(AIUsageLog)
            .where(AIUsageLog.feature == "ai_chat")
            .order_by(AIUsageLog.created_at.desc())
        )
    assert row is not None
    assert (row.provider, row.model, row.status) == ("openai", "gpt-test", "success")
    assert (row.input_tokens, row.output_tokens, row.total_tokens) == (70, 10, 80)


def test_chat_route_does_not_fall_back_on_a_rejected_request(
    monkeypatch: pytest.MonkeyPatch, client: TestClient, session_factory: Any
) -> None:
    bad_request = _status_error(
        openai.BadRequestError, 400, "https://api.groq.com/openai/v1/chat/completions"
    )
    calls = _install_fake_openai(monkeypatch, bad_request)

    response = _post_chat(client, "fallback-bad-request@example.com")

    # Sending the same rejected request to another provider would not help.
    assert response.status_code == 502
    assert calls == {"groq": 1, "openai": 0}
    with session_factory() as db:
        row = db.scalar(
            select(AIUsageLog)
            .where(AIUsageLog.feature == "ai_chat")
            .order_by(AIUsageLog.created_at.desc())
        )
    assert row is not None
    assert row.error_type == "AIProviderRequestError"


def test_chat_route_does_not_hide_a_primary_auth_error(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    bad_key = _status_error(
        openai.AuthenticationError, 401, "https://api.groq.com/openai/v1/chat/completions"
    )
    calls = _install_fake_openai(monkeypatch, bad_key)

    response = _post_chat(client, "fallback-auth@example.com")

    # AIProviderConfigurationError keeps its existing status code.
    assert response.status_code == 500
    assert calls == {"groq": 1, "openai": 0}
