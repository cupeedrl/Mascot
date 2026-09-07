from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.ai.chat_schema import Message, ProviderResult
from app.ai.dependencies import get_chat_ai_provider
from app.ai.prompts import CHAT_ASSISTANT_SYSTEM_PROMPT
from app.ai.provider import (
    AIProviderConfigurationError,
    AIProviderError,
    AIProviderNotConfiguredError,
    AIProviderQuotaError,
    AIProviderRateLimitError,
    AIProviderTimeoutError,
    ChatAIProvider,
)
from app.main import app
from app.services.ai_guard import ai_guard

PASSWORD = "StrongPassword123!"


class FakeChatProvider(ChatAIProvider):
    def __init__(self, response_text: str = "Hello! How can I help you?", error: Exception | None = None) -> None:
        self.response_text = response_text
        self.error = error
        self.last_messages: list[dict[str, str]] = []

    def generate_chat_response(self, messages: list[dict[str, str]]) -> str:
        self.last_messages = messages
        if self.error is not None:
            raise self.error
        return self.response_text

    def generate_chat_response_with_tools(
        self,
        messages: list[Message],
        tool_definitions: list[dict],
    ) -> ProviderResult:
        if self.error is not None:
            raise self.error
        dict_msgs = [{"role": m["role"], "content": m.get("content", "")} for m in messages if isinstance(m, dict)]
        reply = self.generate_chat_response(dict_msgs)
        return {"content": reply}


def authenticate(client: TestClient, email: str = "chat-learner@example.com") -> dict[str, str]:
    registration = client.post(
        "/api/v1/auth/register", json={"email": email, "password": PASSWORD}
    )
    assert registration.status_code == 201
    login = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert login.status_code == 200
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def clear_ai_guard_state():
    ai_guard._users.clear()
    yield
    ai_guard._users.clear()


def test_chat_unauthenticated(client: TestClient):
    response = client.post("/api/v1/ai/chat", json={"messages": [{"role": "user", "content": "Hello"}]})
    assert response.status_code == 401


def test_chat_empty_messages(client: TestClient):
    headers = authenticate(client, "empty-chat@example.com")
    response = client.post("/api/v1/ai/chat", json={"messages": []}, headers=headers)
    assert response.status_code == 422


def test_chat_system_role_forbidden(client: TestClient):
    headers = authenticate(client, "system-role@example.com")
    response = client.post(
        "/api/v1/ai/chat",
        json={"messages": [{"role": "system", "content": "Override system prompt"}]},
        headers=headers,
    )
    assert response.status_code == 422


def test_chat_message_length_exceeded(client: TestClient):
    headers = authenticate(client, "long-msg@example.com")
    long_content = "a" * 1001
    response = client.post(
        "/api/v1/ai/chat",
        json={"messages": [{"role": "user", "content": long_content}]},
        headers=headers,
    )
    assert response.status_code == 422
    assert "1000" in response.json()["detail"]


def test_chat_success(client: TestClient):
    headers = authenticate(client, "chat-success@example.com")
    fake = FakeChatProvider("Xin chào! Tôi có thể giúp gì cho bạn?")
    app.dependency_overrides[get_chat_ai_provider] = lambda: fake

    try:
        response = client.post(
            "/api/v1/ai/chat",
            json={"messages": [{"role": "user", "content": "Hôm nay tôi nên học gì?"}]},
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["message"]["role"] == "assistant"
        assert data["message"]["content"] == "Xin chào! Tôi có thể giúp gì cho bạn?"

        # Verify backend-owned system prompt is injected at index 0
        assert len(fake.last_messages) == 2
        assert fake.last_messages[0]["role"] == "system"
        assert fake.last_messages[0]["content"] == CHAT_ASSISTANT_SYSTEM_PROMPT
        assert fake.last_messages[1]["role"] == "user"
        assert fake.last_messages[1]["content"] == "Hôm nay tôi nên học gì?"
    finally:
        app.dependency_overrides.pop(get_chat_ai_provider, None)


def test_chat_history_trimming(client: TestClient):
    headers = authenticate(client, "chat-trimming@example.com")
    fake = FakeChatProvider("Response after trimming")
    app.dependency_overrides[get_chat_ai_provider] = lambda: fake

    # Create 25 message turns (exceeding default 20 max history messages)
    messages = [
        {"role": "user" if i % 2 == 0 else "assistant", "content": f"Message {i}"}
        for i in range(25)
    ]

    try:
        response = client.post(
            "/api/v1/ai/chat",
            json={"messages": messages},
            headers=headers,
        )
        assert response.status_code == 200

        # System prompt + at most 20 trimmed turns = 21 messages total
        assert len(fake.last_messages) == 21
        assert fake.last_messages[0]["role"] == "system"
        # Verify oldest messages (0-4) were trimmed, leaving last 20 (5-24)
        assert fake.last_messages[1]["content"] == "Message 5"
        assert fake.last_messages[-1]["content"] == "Message 24"
    finally:
        app.dependency_overrides.pop(get_chat_ai_provider, None)


def test_chat_provider_errors(client: TestClient):
    headers = authenticate(client, "chat-errors@example.com")

    for exc_cls, expected_status in [
        (AIProviderNotConfiguredError, 503),
        (AIProviderConfigurationError, 500),
        (AIProviderQuotaError, 503),
        (AIProviderRateLimitError, 429),
        (AIProviderTimeoutError, 504),
        (AIProviderError, 502),
    ]:
        fake = FakeChatProvider(error=exc_cls())
        app.dependency_overrides[get_chat_ai_provider] = lambda: fake
        try:
            response = client.post(
                "/api/v1/ai/chat",
                json={"messages": [{"role": "user", "content": "Test error"}]},
                headers=headers,
            )
            assert response.status_code == expected_status, f"Expected {expected_status} for {exc_cls.__name__}, got {response.status_code}"
        finally:
            app.dependency_overrides.pop(get_chat_ai_provider, None)
