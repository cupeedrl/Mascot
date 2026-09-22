from __future__ import annotations

from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.ai.chat_schema import Message, ProviderResult
from app.ai.action_tokens import issue_action_token
from app.ai.dependencies import get_chat_ai_provider
from app.ai.provider import ChatAIProvider
from app.main import app
from app.models.ai_conversation import AIConversation, AIMessage
from app.services.ai_conversation import (
    append_visible_messages,
    create_conversation,
    derive_conversation_title,
)
from app.services.ai_guard import ai_guard

PASSWORD = "StrongPassword123!"


class RecordingProvider(ChatAIProvider):
    def __init__(self, responses: list[ProviderResult] | None = None) -> None:
        self.responses = responses or [{"content": "Persisted assistant response"}]
        self.calls: list[list[Message]] = []

    def generate_chat_response(self, messages: list[dict[str, str]]) -> str:
        raise AssertionError("plain chat fallback must not run")

    def generate_chat_response_with_tools(
        self, messages: list[Message], tool_definitions: list[dict[str, Any]]
    ) -> ProviderResult:
        self.calls.append(messages)
        return self.responses[len(self.calls) - 1]


@pytest.fixture(autouse=True)
def clear_guards() -> None:
    ai_guard._users.clear()
    yield
    ai_guard._users.clear()
    app.dependency_overrides.pop(get_chat_ai_provider, None)


def authenticate(client: TestClient, email: str) -> tuple[dict[str, str], UUID]:
    registration = client.post(
        "/api/v1/auth/register", json={"email": email, "password": PASSWORD}
    )
    login = client.post(
        "/api/v1/auth/login", json={"email": email, "password": PASSWORD}
    )
    return {
        "Authorization": f"Bearer {login.json()['access_token']}"
    }, UUID(registration.json()["id"])


def test_create_list_load_and_delete_owned_conversation(client: TestClient) -> None:
    headers, _ = authenticate(client, "conversation-crud@example.com")

    created = client.post("/api/v1/ai/conversations", headers=headers)
    assert created.status_code == 201
    conversation_id = created.json()["id"]
    assert created.json()["title"] == "New conversation"

    listed = client.get("/api/v1/ai/conversations", headers=headers)
    assert [item["id"] for item in listed.json()] == [conversation_id]

    loaded = client.get(
        f"/api/v1/ai/conversations/{conversation_id}", headers=headers
    )
    assert loaded.status_code == 200
    assert loaded.json()["messages"] == []

    deleted = client.delete(
        f"/api/v1/ai/conversations/{conversation_id}", headers=headers
    )
    assert deleted.status_code == 204
    assert client.get(
        f"/api/v1/ai/conversations/{conversation_id}", headers=headers
    ).status_code == 404


def test_conversation_queries_and_append_are_owner_scoped(client: TestClient) -> None:
    owner_headers, _ = authenticate(client, "conversation-owner@example.com")
    other_headers, _ = authenticate(client, "conversation-other@example.com")
    conversation_id = client.post(
        "/api/v1/ai/conversations", headers=owner_headers
    ).json()["id"]

    assert client.get(
        f"/api/v1/ai/conversations/{conversation_id}", headers=other_headers
    ).status_code == 404
    assert client.delete(
        f"/api/v1/ai/conversations/{conversation_id}", headers=other_headers
    ).status_code == 404

    provider = RecordingProvider()
    app.dependency_overrides[get_chat_ai_provider] = lambda: provider
    appended = client.post(
        "/api/v1/ai/chat",
        headers=other_headers,
        json={"conversation_id": conversation_id, "message": "Attempted append"},
    )
    assert appended.status_code == 404
    assert client.get("/api/v1/ai/conversations", headers=other_headers).json() == []
    assert provider.calls == []


def test_chat_auto_creates_and_persists_visible_messages(client: TestClient) -> None:
    headers, _ = authenticate(client, "conversation-chat@example.com")
    provider = RecordingProvider()
    app.dependency_overrides[get_chat_ai_provider] = lambda: provider

    response = client.post(
        "/api/v1/ai/chat",
        headers=headers,
        json={"message": "  Explain   resilient to me  "},
    )
    assert response.status_code == 200
    conversation_id = response.json()["conversation_id"]

    restored = client.get(
        f"/api/v1/ai/conversations/{conversation_id}", headers=headers
    ).json()
    assert restored["title"] == "Explain resilient to me"
    assert [(item["role"], item["content"]) for item in restored["messages"]] == [
        ("user", "  Explain   resilient to me  "),
        ("assistant", "Persisted assistant response"),
    ]


def test_existing_conversation_uses_server_history_and_bounded_context(
    client: TestClient, session_factory: Any
) -> None:
    headers, user_id = authenticate(client, "conversation-history@example.com")
    with session_factory() as db:
        conversation = create_conversation(db, user_id)
        append_visible_messages(
            db,
            conversation,
            [
                ("user" if index % 2 == 0 else "assistant", f"Stored {index}")
                for index in range(25)
            ],
        )
        conversation_id = conversation.id

    provider = RecordingProvider()
    app.dependency_overrides[get_chat_ai_provider] = lambda: provider
    response = client.post(
        "/api/v1/ai/chat",
        headers=headers,
        json={"conversation_id": str(conversation_id), "message": "Latest question"},
    )
    assert response.status_code == 200

    visible_context = [
        item for item in provider.calls[0] if item["role"] in {"user", "assistant"}
    ]
    assert len(visible_context) == 20
    assert visible_context[0]["content"] == "Stored 6"
    assert visible_context[-1]["content"] == "Latest question"


def test_internal_tool_protocol_is_not_persisted(client: TestClient) -> None:
    headers, _ = authenticate(client, "conversation-tools@example.com")
    provider = RecordingProvider(
        [
            {
                "tool_calls": [
                    {"id": "unknown-1", "name": "not_registered", "arguments": "{}"}
                ]
            },
            {"content": "I could not use that tool safely."},
        ]
    )
    app.dependency_overrides[get_chat_ai_provider] = lambda: provider

    response = client.post(
        "/api/v1/ai/chat", headers=headers, json={"message": "Use a bad tool"}
    )
    assert response.status_code == 200
    restored = client.get(
        f"/api/v1/ai/conversations/{response.json()['conversation_id']}",
        headers=headers,
    ).json()
    assert [(item["role"], item["content"]) for item in restored["messages"]] == [
        ("user", "Use a bad tool"),
        ("assistant", "I could not use that tool safely."),
    ]


def test_legacy_history_contract_remains_supported(client: TestClient) -> None:
    headers, _ = authenticate(client, "conversation-legacy@example.com")
    provider = RecordingProvider()
    app.dependency_overrides[get_chat_ai_provider] = lambda: provider

    response = client.post(
        "/api/v1/ai/chat",
        headers=headers,
        json={
            "messages": [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi"},
                {"role": "user", "content": "Continue"},
            ]
        },
    )
    assert response.status_code == 200
    restored = client.get(
        f"/api/v1/ai/conversations/{response.json()['conversation_id']}",
        headers=headers,
    ).json()
    assert [message["content"] for message in restored["messages"]] == [
        "Hello",
        "Hi",
        "Continue",
        "Persisted assistant response",
    ]


def test_user_id_injection_and_ambiguous_message_sources_are_rejected(
    client: TestClient,
) -> None:
    headers, _ = authenticate(client, "conversation-injection@example.com")
    assert client.post(
        "/api/v1/ai/chat",
        headers=headers,
        json={"message": "Hello", "user_id": "00000000-0000-0000-0000-000000000000"},
    ).status_code == 422
    assert client.post(
        "/api/v1/ai/chat",
        headers=headers,
        json={"message": "Hello", "messages": [{"role": "user", "content": "Hi"}]},
    ).status_code == 422


def test_title_generation_is_deterministic_and_bounded() -> None:
    assert derive_conversation_title("  Xin   chào\nMascot  ") == "Xin chào Mascot"
    title = derive_conversation_title("word " * 40)
    assert len(title) <= 120
    assert title.endswith("...")


def test_delete_cascades_visible_messages(
    client: TestClient, session_factory: Any
) -> None:
    headers, _ = authenticate(client, "conversation-cascade@example.com")
    provider = RecordingProvider()
    app.dependency_overrides[get_chat_ai_provider] = lambda: provider
    conversation_id = client.post(
        "/api/v1/ai/chat", headers=headers, json={"message": "Persist me"}
    ).json()["conversation_id"]

    assert client.delete(
        f"/api/v1/ai/conversations/{conversation_id}", headers=headers
    ).status_code == 204
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(AIConversation)) == 0
        assert db.scalar(select(func.count()).select_from(AIMessage)) == 0


def test_action_result_is_persisted_without_the_signed_token(client: TestClient) -> None:
    headers, _ = authenticate(client, "conversation-action-result@example.com")
    conversation_id = client.post(
        "/api/v1/ai/conversations", headers=headers
    ).json()["id"]
    action_token, _ = issue_action_token(
        tool_name="add_vocabulary",
        user_id=UUID(client.get("/api/v1/auth/me", headers=headers).json()["id"]),
        arguments={
            "word": "resilient",
            "ipa": "/rɪˈzɪliənt/",
            "part_of_speech": "adjective",
            "meaning": "Able to recover quickly.",
            "translation": "kiên cường",
            "translation_language_code": "vi",
            "example_sentences": ["She remained resilient."],
            "level_code": "B2",
            "topic": "Personal Growth",
        },
    )

    canceled = client.post(
        "/api/v1/ai/actions/cancel",
        headers=headers,
        json={"action_token": action_token, "conversation_id": conversation_id},
    )
    assert canceled.status_code == 200
    restored = client.get(
        f"/api/v1/ai/conversations/{conversation_id}", headers=headers
    ).json()
    assert restored["messages"][-1]["content"] == "Vocabulary addition canceled."
    assert action_token not in restored["messages"][-1]["content"]
