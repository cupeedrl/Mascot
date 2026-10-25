"""Characterization tests for the provider's retry and error mapping.

They pin down what each provider method does for every SDK error today,
including where the methods differ, so the shared retry helper must keep
exactly this behavior:

- structured calls (vocabulary, exercises) map other 4xx responses to
  AIProviderRequestError and log each retry;
- chat calls map them to a bare AIProviderError and do not log retries.
"""

from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import Any, Callable

import httpx
import openai
import pytest
from pydantic import BaseModel, ValidationError

from app.ai.openai_compatible_provider import OpenAICompatibleVocabularyProvider
from app.ai.provider import (
    AIProviderConfigurationError,
    AIProviderError,
    AIProviderQuotaError,
    AIProviderRateLimitError,
    AIProviderRequestError,
    AIProviderResponseError,
    AIProviderTimeoutError,
)

URL = "https://api.example.test/v1/chat/completions"


def status_error(cls: type, status_code: int, body: object = None) -> Exception:
    response = httpx.Response(status_code, request=httpx.Request("POST", URL))
    return cls("provider error", response=response, body=body)


def timeout_error() -> Exception:
    return openai.APITimeoutError(request=httpx.Request("POST", URL))


def connection_error() -> Exception:
    return openai.APIConnectionError(request=httpx.Request("POST", URL))


def validation_error() -> ValidationError:
    class Shape(BaseModel):
        value: int

    try:
        Shape.model_validate({"value": "not a number"})
    except ValidationError as exc:
        return exc
    raise AssertionError("expected a ValidationError")


STRUCTURED_OK = SimpleNamespace(
    output_parsed=SimpleNamespace(model_dump=lambda **_: {"word": "ok"}),
    status="completed",
    usage=None,
)
CHAT_OK = SimpleNamespace(
    choices=[SimpleNamespace(message=SimpleNamespace(content="ok", tool_calls=None))],
    usage=None,
)


def call_structured(provider: OpenAICompatibleVocabularyProvider) -> Any:
    return provider.generate_vocabulary("word", "noun", "từ")


def call_chat(provider: OpenAICompatibleVocabularyProvider) -> Any:
    return provider.generate_chat_response([{"role": "user", "content": "hi"}])


def call_tools(provider: OpenAICompatibleVocabularyProvider) -> Any:
    return provider.generate_chat_response_with_tools(
        messages=[{"role": "user", "content": "hi"}], tool_definitions=[]
    )


# (name, invoke, successful SDK response, value returned on success, feature in logs)
METHODS = [
    ("structured", call_structured, STRUCTURED_OK, {"word": "ok"}, "vocabulary_enrichment"),
    ("chat", call_chat, CHAT_OK, "ok", "ai_chat"),
    ("chat_tools", call_tools, CHAT_OK, {"content": "ok"}, "ai_chat_tools"),
]
METHOD_IDS = [method[0] for method in METHODS]


class Harness:
    def __init__(self, monkeypatch: pytest.MonkeyPatch, script: list[Any]) -> None:
        self.script = list(script)
        self.calls = 0
        self.sleeps: list[float] = []

        def answer(**_: Any) -> Any:
            self.calls += 1
            step = self.script.pop(0)
            if isinstance(step, BaseException):
                raise step
            return step

        harness = self

        class FakeOpenAI:
            def __init__(self, **kwargs: Any) -> None:
                harness.client_options = kwargs
                self.responses = SimpleNamespace(parse=answer)
                self.chat = SimpleNamespace(completions=SimpleNamespace(create=answer))

        monkeypatch.setattr(openai, "OpenAI", FakeOpenAI)
        monkeypatch.setattr(
            "app.ai.openai_compatible_provider.time.sleep", self.sleeps.append
        )


def provider() -> OpenAICompatibleVocabularyProvider:
    return OpenAICompatibleVocabularyProvider(
        api_key="test-key",
        model="test-model",
        base_url="https://api.example.test/v1/",
        timeout_seconds=7,
        max_output_tokens=500,
    )


@pytest.mark.parametrize(("name", "invoke", "ok", "expected", "feature"), METHODS, ids=METHOD_IDS)
def test_success_on_first_call_uses_one_client_without_sdk_retries(
    monkeypatch: pytest.MonkeyPatch, name: str, invoke: Callable, ok: Any, expected: Any, feature: str, caplog: Any
) -> None:
    harness = Harness(monkeypatch, [ok])
    with caplog.at_level(logging.INFO, logger="ai_usage"):
        assert invoke(provider()) == expected
    assert harness.calls == 1
    assert harness.client_options == {
        "api_key": "test-key",
        "timeout": 7,
        "max_retries": 0,
        "base_url": "https://api.example.test/v1",
    }
    assert f"AI call success: feature={feature}, model=test-model" in caplog.text
    assert "attempts=1" in caplog.text


@pytest.mark.parametrize(
    "transient",
    [
        lambda: status_error(openai.RateLimitError, 429),
        timeout_error,
        lambda: status_error(openai.InternalServerError, 500),
        connection_error,
    ],
    ids=["rate_limit", "timeout", "server_error", "connection"],
)
@pytest.mark.parametrize(("name", "invoke", "ok", "expected", "feature"), METHODS, ids=METHOD_IDS)
def test_transient_errors_retry_with_backoff_then_succeed(
    monkeypatch: pytest.MonkeyPatch, name: str, invoke: Callable, ok: Any, expected: Any, feature: str,
    transient: Callable[[], Exception], caplog: Any,
) -> None:
    harness = Harness(monkeypatch, [transient(), transient(), ok])
    with caplog.at_level(logging.INFO):
        assert invoke(provider()) == expected
    assert harness.calls == 3
    assert harness.sleeps == [0.5, 1.0]
    assert "attempts=3" in caplog.text
    # Only the structured path logs each retry.
    assert ("Retrying AI call after" in caplog.text) is (name == "structured")


@pytest.mark.parametrize(
    ("transient", "expected_error", "log_kind"),
    [
        (lambda: status_error(openai.RateLimitError, 429), AIProviderRateLimitError, "rate_limit"),
        (timeout_error, AIProviderTimeoutError, "timeout"),
        (lambda: status_error(openai.InternalServerError, 503), AIProviderError, "provider_network_or_5xx"),
        (connection_error, AIProviderError, "provider_network_or_5xx"),
    ],
    ids=["rate_limit", "timeout", "server_error", "connection"],
)
@pytest.mark.parametrize(("name", "invoke", "ok", "expected", "feature"), METHODS, ids=METHOD_IDS)
def test_transient_errors_give_up_after_three_attempts(
    monkeypatch: pytest.MonkeyPatch, name: str, invoke: Callable, ok: Any, expected: Any, feature: str,
    transient: Callable[[], Exception], expected_error: type, log_kind: str, caplog: Any,
) -> None:
    harness = Harness(monkeypatch, [transient(), transient(), transient()])
    with caplog.at_level(logging.WARNING, logger="ai_usage"), pytest.raises(expected_error) as raised:
        invoke(provider())
    assert type(raised.value) is expected_error
    assert harness.calls == 3
    assert harness.sleeps == [0.5, 1.0]
    assert f"AI call error: {log_kind}, feature={feature}, model=test-model" in caplog.text
    assert "attempts=3" in caplog.text


@pytest.mark.parametrize(
    ("error", "expected_error", "log_kind"),
    [
        (lambda: status_error(openai.AuthenticationError, 401), AIProviderConfigurationError, "config/auth"),
        (lambda: status_error(openai.PermissionDeniedError, 403), AIProviderConfigurationError, "config/auth"),
        (lambda: status_error(openai.NotFoundError, 404), AIProviderConfigurationError, "config/auth"),
        (
            lambda: status_error(openai.RateLimitError, 429, {"code": "insufficient_quota"}),
            AIProviderQuotaError,
            "quota_exhausted",
        ),
        (lambda: openai.OpenAIError("sdk failure"), AIProviderError, "general_openai_error"),
    ],
    ids=["auth", "permission", "not_found", "quota", "generic_sdk_error"],
)
@pytest.mark.parametrize(("name", "invoke", "ok", "expected", "feature"), METHODS, ids=METHOD_IDS)
def test_terminal_errors_are_mapped_without_retry(
    monkeypatch: pytest.MonkeyPatch, name: str, invoke: Callable, ok: Any, expected: Any, feature: str,
    error: Callable[[], Exception], expected_error: type, log_kind: str, caplog: Any,
) -> None:
    harness = Harness(monkeypatch, [error()])
    with caplog.at_level(logging.WARNING, logger="ai_usage"), pytest.raises(expected_error) as raised:
        invoke(provider())
    assert type(raised.value) is expected_error
    assert harness.calls == 1
    assert harness.sleeps == []
    assert f"AI call error: {log_kind}, feature={feature}, model=test-model" in caplog.text


@pytest.mark.parametrize(("name", "invoke", "ok", "expected", "feature"), METHODS, ids=METHOD_IDS)
def test_other_client_errors_differ_between_structured_and_chat_calls(
    monkeypatch: pytest.MonkeyPatch, name: str, invoke: Callable, ok: Any, expected: Any, feature: str, caplog: Any,
) -> None:
    body = {"error": {"type": "invalid_request_error", "message": "bad schema", "param": "x", "code": "bad"}}
    harness = Harness(monkeypatch, [status_error(openai.BadRequestError, 400, body)])

    with caplog.at_level(logging.WARNING, logger="ai_usage"), pytest.raises(AIProviderError) as raised:
        invoke(provider())

    assert harness.calls == 1
    if name == "structured":
        assert type(raised.value) is AIProviderRequestError
        assert raised.value.status_code == 400
        assert raised.value.details == {
            "type": "invalid_request_error",
            "message": "bad schema",
            "param": "x",
            "code": "bad",
        }
        assert f"AI call error: provider_request, feature={feature}" in caplog.text
    else:
        assert type(raised.value) is AIProviderError
        assert f"AI call error: provider_network_or_5xx, feature={feature}" in caplog.text


def test_structured_schema_mismatch_is_a_response_error_without_retry(
    monkeypatch: pytest.MonkeyPatch, caplog: Any
) -> None:
    harness = Harness(monkeypatch, [validation_error()])
    with caplog.at_level(logging.WARNING), pytest.raises(AIProviderResponseError) as raised:
        call_structured(provider())
    assert raised.value.stage == "provider_parse"
    assert harness.calls == 1
    assert "AI call error: validation_error, feature=vocabulary_enrichment" in caplog.text


def test_structured_empty_parse_is_a_response_error_without_retry(
    monkeypatch: pytest.MonkeyPatch, caplog: Any
) -> None:
    empty = SimpleNamespace(output_parsed=None, status="incomplete", usage=None)
    harness = Harness(monkeypatch, [empty])
    with caplog.at_level(logging.WARNING), pytest.raises(AIProviderResponseError) as raised:
        call_structured(provider())
    assert raised.value.stage == "provider_parse"
    assert harness.calls == 1
    assert "AI call error: empty_parsed, feature=vocabulary_enrichment" in caplog.text


def test_chat_without_content_is_a_response_error_without_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    empty = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=None, tool_calls=None))], usage=None
    )
    harness = Harness(monkeypatch, [empty])
    with pytest.raises(AIProviderResponseError) as raised:
        call_chat(provider())
    assert raised.value.stage == "chat_completion"
    assert harness.calls == 1


def test_exercise_logs_keep_the_chat_model_name(monkeypatch: pytest.MonkeyPatch, caplog: Any) -> None:
    exercise_provider = OpenAICompatibleVocabularyProvider(
        api_key="test-key",
        model="chat-model",
        exercise_model="exercise-model",
        timeout_seconds=7,
        max_output_tokens=500,
    )
    batch = SimpleNamespace(
        output_parsed=SimpleNamespace(model_dump=lambda **_: {"items": []}), usage=None
    )
    Harness(monkeypatch, [batch])
    with caplog.at_level(logging.INFO, logger="ai_usage"):
        exercise_provider.generate_exercises([{"word": "w"}], "multiple_choice", 4)
    assert "AI call success: feature=exercise_multiple_choice, model=chat-model" in caplog.text


def test_missing_api_key_never_creates_a_client(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.ai.provider import AIProviderNotConfiguredError

    harness = Harness(monkeypatch, [])
    no_key = OpenAICompatibleVocabularyProvider(
        api_key="  ", model="m", timeout_seconds=7, max_output_tokens=500
    )
    for invoke in (call_structured, call_chat, call_tools):
        with pytest.raises(AIProviderNotConfiguredError):
            invoke(no_key)
    assert harness.calls == 0
    assert not hasattr(harness, "client_options")
