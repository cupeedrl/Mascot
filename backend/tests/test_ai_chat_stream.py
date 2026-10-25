from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import httpx
import openai
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.ai import chat_agent
from app.ai.dependencies import get_chat_ai_provider
from app.ai.fallback_provider import FallbackAIProvider
from app.ai.groq_provider import GroqVocabularyProvider
from app.ai.openai_compatible_provider import _consume_chat_stream
from app.ai.openai_provider import OpenAIVocabularyProvider
from app.ai.provider import AIProviderRateLimitError
from app.main import app
from app.models.ai_usage_log import AIUsageLog
from app.services.ai_guard import ai_guard

PASSWORD = "StrongPassword123!"
CHAT_STREAM = "/api/v1/ai/chat/stream"

ADD_ARGUMENTS = {
    "word": "resilient",
    "ipa": "/rɪˈzɪliənt/",
    "part_of_speech": "adjective",
    "meaning": "Able to recover quickly from difficulty.",
    "translation": "kiên cường",
    "translation_language_code": "vi",
    "example_sentences": ["She remained resilient after the setback."],
    "level_code": "B2",
    "topic": "Personal Growth",
}


# --- helpers ------------------------------------------------------------------


def parse_sse(body: str) -> list[tuple[str, dict[str, Any]]]:
    events: list[tuple[str, dict[str, Any]]] = []
    for block in body.split("\n\n"):
        if not block.strip():
            continue
        fields = dict(line.split(": ", 1) for line in block.splitlines())
        events.append((fields["event"], json.loads(fields["data"])))
    return events


def kinds(events: list[tuple[str, dict[str, Any]]]) -> list[str]:
    return [kind for kind, _ in events]


def auth_headers(client: TestClient, email: str) -> dict[str, str]:
    assert client.post(
        "/api/v1/auth/register", json={"email": email, "password": PASSWORD}
    ).status_code == 201
    login = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def text_chunk(text: str) -> Any:
    return SimpleNamespace(
        choices=[SimpleNamespace(delta=SimpleNamespace(content=text, tool_calls=None))],
        usage=None,
    )


def tool_chunk(index: int, *, call_id: str | None, name: str | None, arguments: str) -> Any:
    fragment = SimpleNamespace(
        index=index, id=call_id, function=SimpleNamespace(name=name, arguments=arguments)
    )
    return SimpleNamespace(
        choices=[SimpleNamespace(delta=SimpleNamespace(content=None, tool_calls=[fragment]))],
        usage=None,
    )


def usage_chunk(prompt: int, completion: int) -> Any:
    # OpenAI with stream_options.include_usage: a final chunk without choices.
    return SimpleNamespace(
        choices=[],
        usage=SimpleNamespace(
            prompt_tokens=prompt, completion_tokens=completion, total_tokens=prompt + completion
        ),
    )


def groq_usage_chunk(prompt: int, completion: int) -> Any:
    # Groq: usage under x_groq on the last chunk.
    return SimpleNamespace(
        choices=[],
        usage=None,
        x_groq={
            "usage": {
                "prompt_tokens": prompt,
                "completion_tokens": completion,
                "total_tokens": prompt + completion,
            }
        },
    )


def install_streams(monkeypatch: pytest.MonkeyPatch, streams: list[list[Any]]) -> list[dict]:
    """Each create(stream=True) call returns the next scripted chunk list."""
    calls: list[dict] = []

    class FakeOpenAI:
        def __init__(self, **kwargs: Any) -> None:
            def create(**request: Any) -> Any:
                calls.append(request)
                assert request.get("stream") is True
                return iter(streams.pop(0))

            self.chat = SimpleNamespace(completions=SimpleNamespace(create=create))

    monkeypatch.setattr(openai, "OpenAI", FakeOpenAI)
    monkeypatch.setattr("app.ai.openai_compatible_provider.time.sleep", lambda _: None)
    return calls


def openai_provider() -> OpenAIVocabularyProvider:
    return OpenAIVocabularyProvider(
        api_key="openai-test-key", model="gpt-test", timeout_seconds=20, max_output_tokens=800
    )


def groq_provider() -> GroqVocabularyProvider:
    return GroqVocabularyProvider(
        api_key="groq-test-key",
        model="openai/gpt-oss-20b",
        base_url="https://api.groq.com/openai/v1",
        timeout_seconds=20,
        max_output_tokens=800,
    )


def post(
    client: TestClient,
    path: str,
    headers: dict[str, str],
    provider: Any,
    body: dict[str, Any] | None = None,
) -> httpx.Response:
    ai_guard._users.clear()
    app.dependency_overrides[get_chat_ai_provider] = lambda: provider
    try:
        return client.post(
            path,
            headers=headers,
            json=body or {"message": "Xin chào"},
        )
    finally:
        app.dependency_overrides.pop(get_chat_ai_provider, None)


def latest_chat_log(session_factory: Any) -> AIUsageLog:
    with session_factory() as db:
        row = db.scalar(
            select(AIUsageLog)
            .where(AIUsageLog.feature == "ai_chat")
            .order_by(AIUsageLog.created_at.desc())
        )
    assert row is not None
    return row


# --- streaming through the real provider ------------------------------------


def test_stream_sends_draft_deltas_then_the_persisted_answer(
    monkeypatch: pytest.MonkeyPatch, client: TestClient, session_factory: Any
) -> None:
    calls = install_streams(
        monkeypatch, [[text_chunk("Xin "), text_chunk("chào!"), usage_chunk(30, 5)]]
    )
    headers = auth_headers(client, "stream-basic@example.com")

    response = post(client, CHAT_STREAM, headers, openai_provider())

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert len(response.headers["X-Request-ID"]) == 32
    events = parse_sse(response.text)
    assert events[:2] == [("delta", {"text": "Xin "}), ("delta", {"text": "chào!"})]
    assert kinds(events) == ["delta", "delta", "done"]
    done = events[-1][1]
    assert done["message"] == {"role": "assistant", "content": "Xin chào!"}
    assert done["confirmation_required"] is None
    assert calls[0]["stream_options"] == {"include_usage": True}

    detail = client.get(f"/api/v1/ai/conversations/{done['conversation_id']}", headers=headers)
    assert [m["content"] for m in detail.json()["messages"]] == ["Xin chào", "Xin chào!"]
    row = latest_chat_log(session_factory)
    assert (row.provider, row.model, row.status) == ("openai", "gpt-test", "success")
    assert (row.input_tokens, row.output_tokens, row.total_tokens) == (30, 5, 35)


def test_stream_runs_tool_rounds_and_sums_groq_usage(
    monkeypatch: pytest.MonkeyPatch, client: TestClient, session_factory: Any
) -> None:
    calls = install_streams(
        monkeypatch,
        [
            [
                tool_chunk(0, call_id="stats-1", name="get_learning_stats", arguments="{"),
                tool_chunk(0, call_id=None, name=None, arguments="}"),
                groq_usage_chunk(100, 10),
            ],
            [text_chunk("Bạn chưa có từ nào."), groq_usage_chunk(150, 20)],
        ],
    )
    headers = auth_headers(client, "stream-tools@example.com")

    response = post(client, CHAT_STREAM, headers, groq_provider())

    events = parse_sse(response.text)
    assert kinds(events) == ["discard", "delta", "done"]
    assert events[-1][1]["message"]["content"] == "Bạn chưa có từ nào."
    assert all("stream_options" not in call for call in calls)
    # The second call saw the joined tool call and its result.
    assert calls[1]["messages"][-2]["tool_calls"][0]["function"] == {
        "name": "get_learning_stats",
        "arguments": "{}",
    }
    assert calls[1]["messages"][-1]["role"] == "tool"
    row = latest_chat_log(session_factory)
    assert (row.provider, row.input_tokens, row.output_tokens) == ("groq", 250, 30)


def test_text_streamed_before_a_tool_call_is_discarded(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    install_streams(
        monkeypatch,
        [
            [
                text_chunk("Để tôi kiểm tra…"),
                tool_chunk(0, call_id="stats-1", name="get_learning_stats", arguments="{}"),
            ],
            [text_chunk("Bạn chưa có từ nào.")],
        ],
    )
    headers = auth_headers(client, "stream-discard@example.com")

    events = parse_sse(post(client, CHAT_STREAM, headers, openai_provider()).text)

    assert kinds(events) == ["delta", "discard", "delta", "done"]
    assert events[-1][1]["message"]["content"] == "Bạn chưa có từ nào."


def test_write_proposal_ends_with_a_confirmation_card(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    install_streams(
        monkeypatch,
        [[
            tool_chunk(
                0,
                call_id="add-1",
                name="add_vocabulary",
                arguments=json.dumps(ADD_ARGUMENTS, ensure_ascii=False),
            )
        ]],
    )
    headers = auth_headers(client, "stream-write@example.com")

    events = parse_sse(
        post(client, CHAT_STREAM, headers, openai_provider(), {"message": "Thêm resilient"}).text
    )

    assert kinds(events) == ["discard", "done"]
    confirmation = events[-1][1]["confirmation_required"]
    assert confirmation["tool_name"] == "add_vocabulary"
    assert confirmation["vocabulary"]["word"] == "resilient"
    assert confirmation["action_token"]


def test_provider_error_becomes_an_error_event_and_releases_the_guard(
    monkeypatch: pytest.MonkeyPatch, client: TestClient, session_factory: Any
) -> None:
    def failing_stream(**_: Any) -> Any:
        response = httpx.Response(401, request=httpx.Request("POST", "https://api.openai.com"))
        raise openai.AuthenticationError("bad key", response=response, body=None)

    class FakeOpenAI:
        def __init__(self, **kwargs: Any) -> None:
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=failing_stream))

    monkeypatch.setattr(openai, "OpenAI", FakeOpenAI)
    headers = auth_headers(client, "stream-error@example.com")

    events = parse_sse(post(client, CHAT_STREAM, headers, openai_provider()).text)

    # Same status and detail as POST /ai/chat for AIProviderConfigurationError.
    assert events == [("error", {"status": 500, "detail": "Cấu hình nhà cung cấp AI không hợp lệ."})]
    assert latest_chat_log(session_factory).error_type == "AIProviderConfigurationError"
    # The in-flight guard was released: the same message can be sent again.
    assert post(client, CHAT_STREAM, headers, openai_provider()).status_code == 200


# --- behaviour shared with POST /ai/chat ------------------------------------


class ScriptedChatProvider:
    """Non-streaming test provider, like the ones the existing chat tests use."""

    def __init__(self, results: list[dict[str, Any]]) -> None:
        self.results = list(results)

    def generate_chat_response_with_tools(self, messages: list, tool_definitions: list) -> dict:
        return self.results.pop(0)


def scripted() -> ScriptedChatProvider:
    return ScriptedChatProvider([
        {"tool_calls": [{"id": "stats-1", "name": "get_learning_stats", "arguments": "{}"}]},
        {"content": "Bạn chưa có từ nào."},
    ])


def test_non_streaming_provider_gets_a_single_done_matching_chat(client: TestClient) -> None:
    headers = auth_headers(client, "stream-parity@example.com")

    plain = post(client, "/api/v1/ai/chat", headers, scripted())
    streamed = parse_sse(post(client, CHAT_STREAM, headers, scripted()).text)

    assert plain.status_code == 200
    assert kinds(streamed) == ["done"]
    done = streamed[0][1]
    assert done["message"] == plain.json()["message"]
    assert set(done) == set(plain.json())


def test_legacy_engine_streams_only_the_final_answer(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    install_streams(monkeypatch, [[text_chunk("never streamed")]])
    monkeypatch.setattr(chat_agent, "get_settings", lambda: SimpleNamespace(ai_agent_engine="legacy"))
    headers = auth_headers(client, "stream-legacy@example.com")

    # The legacy loop calls the provider without on_event, i.e. not streamed.
    class NonStreamingOpenAI:
        def __init__(self, **kwargs: Any) -> None:
            def create(**request: Any) -> Any:
                assert "stream" not in request
                return SimpleNamespace(
                    choices=[SimpleNamespace(message=SimpleNamespace(content="Legacy answer.", tool_calls=None))],
                    usage=None,
                )

            self.chat = SimpleNamespace(completions=SimpleNamespace(create=create))

    monkeypatch.setattr(openai, "OpenAI", NonStreamingOpenAI)

    events = parse_sse(post(client, CHAT_STREAM, headers, openai_provider()).text)

    assert kinds(events) == ["done"]
    assert events[0][1]["message"]["content"] == "Legacy answer."


@pytest.mark.parametrize(
    ("body", "status_code"),
    [
        ({"message": "x" * 1001}, 422),
        ({"message": "hi", "conversation_id": "00000000-0000-0000-0000-000000000000"}, 404),
    ],
)
def test_request_rejections_are_plain_http_errors_before_streaming(
    client: TestClient, body: dict[str, Any], status_code: int
) -> None:
    headers = auth_headers(client, f"stream-reject-{status_code}@example.com")

    response = post(client, CHAT_STREAM, headers, scripted(), body)

    assert response.status_code == status_code
    assert response.headers["content-type"].startswith("application/json")


def test_stream_requires_authentication(client: TestClient) -> None:
    assert client.post(CHAT_STREAM, json={"message": "hi"}).status_code == 401


# --- provider and wrapper units ---------------------------------------------


def test_consume_stream_joins_interleaved_tool_call_fragments() -> None:
    events: list[tuple[str, str]] = []
    content, tool_calls, usage = _consume_chat_stream(
        iter([
            tool_chunk(1, call_id="b", name="get_due_vocabulary", arguments='{"li'),
            tool_chunk(0, call_id="a", name="get_learning_stats", arguments="{"),
            tool_chunk(1, call_id=None, name=None, arguments='mit": 5}'),
            tool_chunk(0, call_id=None, name=None, arguments="}"),
            usage_chunk(1, 2),
        ]),
        lambda kind, text: events.append((kind, text)),
    )

    assert content is None
    assert tool_calls == [
        {"id": "a", "name": "get_learning_stats", "arguments": "{}"},
        {"id": "b", "name": "get_due_vocabulary", "arguments": '{"limit": 5}'},
    ]
    assert usage.usage.total_tokens == 3
    assert events == []


def test_retry_after_a_dropped_stream_discards_the_partial_draft(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def dropped() -> Any:
        yield text_chunk("partial")
        raise openai.APIConnectionError(request=httpx.Request("POST", "https://api.openai.com"))

    streams = [dropped(), iter([text_chunk("final")])]

    class FakeOpenAI:
        def __init__(self, **kwargs: Any) -> None:
            self.chat = SimpleNamespace(
                completions=SimpleNamespace(create=lambda **_: streams.pop(0))
            )

    monkeypatch.setattr(openai, "OpenAI", FakeOpenAI)
    monkeypatch.setattr("app.ai.openai_compatible_provider.time.sleep", lambda _: None)
    events: list[tuple[str, str]] = []

    result = openai_provider().generate_chat_response_with_tools(
        messages=[{"role": "user", "content": "hi"}],
        tool_definitions=[],
        on_event=lambda kind, text: events.append((kind, text)),
    )

    assert result == {"content": "final"}
    assert events == [("delta", "partial"), ("discard", ""), ("delta", "final")]


def test_fallback_discards_the_primary_draft_before_the_secondary_answers() -> None:
    class StreamingScript:
        supports_streaming = True

        def __init__(self, error: Exception | None, text: str) -> None:
            self.error, self.text = error, text

        def generate_chat_response_with_tools(self, messages, tool_definitions, on_event=None):
            on_event("delta", self.text)
            if self.error:
                raise self.error
            return {"content": self.text}

    events: list[tuple[str, str]] = []
    provider = FallbackAIProvider(
        StreamingScript(AIProviderRateLimitError(), "groq draft"),
        StreamingScript(None, "openai answer"),
        primary_name="groq",
        secondary_name="openai",
    )

    result = provider.generate_chat_response_with_tools(
        messages=[], tool_definitions=[], on_event=lambda k, t: events.append((k, t))
    )

    assert provider.supports_streaming is True
    assert result == {"content": "openai answer"}
    assert events == [("delta", "groq draft"), ("discard", ""), ("delta", "openai answer")]
