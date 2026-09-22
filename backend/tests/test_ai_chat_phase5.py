from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.action_tokens import action_replay_guard, issue_action_token
from app.ai.chat_schema import Message, ProviderResult
from app.ai.dependencies import get_chat_ai_provider
from app.ai.provider import ChatAIProvider
from app.ai.tools.executor import ToolConfirmationRequiredError, execute_tool
from app.ai.tools.registry import TOOL_REGISTRY
from app.core.config import get_settings
from app.main import app
from app.models.language import Language
from app.models.learning_track import LearningTrack
from app.models.vocabulary import Vocabulary
from app.services.ai_guard import ai_guard


PASSWORD = "StrongPassword123!"


class SequenceProvider(ChatAIProvider):
    def __init__(self, responses: list[ProviderResult]) -> None:
        self.responses = responses
        self.calls = 0

    def generate_chat_response(self, messages: list[dict[str, str]]) -> str:
        raise AssertionError("plain chat fallback must not run")

    def generate_chat_response_with_tools(
        self,
        messages: list[Message],
        tool_definitions: list[dict],
    ) -> ProviderResult:
        response = self.responses[self.calls]
        self.calls += 1
        return response


@pytest.fixture(autouse=True)
def clear_guards() -> None:
    ai_guard._users.clear()
    action_replay_guard.clear()
    yield
    ai_guard._users.clear()
    action_replay_guard.clear()
    app.dependency_overrides.pop(get_chat_ai_provider, None)


def authenticate(client: TestClient, email: str) -> tuple[dict[str, str], UUID]:
    registered = client.post(
        "/api/v1/auth/register", json={"email": email, "password": PASSWORD}
    )
    assert registered.status_code == 201
    login = client.post(
        "/api/v1/auth/login", json={"email": email, "password": PASSWORD}
    )
    assert login.status_code == 200
    return {
        "Authorization": f"Bearer {login.json()['access_token']}"
    }, UUID(registered.json()["id"])


def create_general_track(db: Session) -> LearningTrack:
    language = Language(code="en", name="English", native_name="English")
    track = LearningTrack(
        language=language,
        code="general-english",
        name="General English",
        description="General English",
        level_framework="CEFR",
    )
    db.add(track)
    db.commit()
    db.refresh(track)
    return track


def add_arguments(**overrides: object) -> dict[str, object]:
    result: dict[str, object] = {
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
    result.update(overrides)
    return result


def proposal_provider(arguments: dict[str, object]) -> SequenceProvider:
    return SequenceProvider(
        [
            {
                "tool_calls": [
                    {
                        "id": "add-vocab-1",
                        "name": "add_vocabulary",
                        "arguments": json.dumps(arguments, ensure_ascii=False),
                    }
                ]
            }
        ]
    )


def request_proposal(
    client: TestClient,
    headers: dict[str, str],
    arguments: dict[str, object] | None = None,
) -> dict[str, Any]:
    app.dependency_overrides[get_chat_ai_provider] = lambda: proposal_provider(
        arguments or add_arguments()
    )
    response = client.post(
        "/api/v1/ai/chat",
        headers=headers,
        json={"messages": [{"role": "user", "content": "Add resilient"}]},
    )
    assert response.status_code == 200, response.text
    return response.json()


def vocabulary_count(session_factory: Any, user_id: UUID) -> int:
    with session_factory() as db:
        return db.scalar(
            select(func.count()).select_from(Vocabulary).where(Vocabulary.user_id == user_id)
        ) or 0


def test_registry_has_three_reads_and_one_confirmed_write() -> None:
    assert set(TOOL_REGISTRY) == {
        "get_learning_stats",
        "get_due_vocabulary",
        "get_learning_profile",
        "add_vocabulary",
    }
    assert TOOL_REGISTRY["get_learning_stats"]["classification"] == "read"
    assert TOOL_REGISTRY["get_due_vocabulary"]["requires_confirmation"] is False
    assert TOOL_REGISTRY["add_vocabulary"]["classification"] == "write"
    assert TOOL_REGISTRY["add_vocabulary"]["requires_confirmation"] is True


def test_write_proposal_does_not_mutate_database(
    client: TestClient, session_factory: Any
) -> None:
    with session_factory() as db:
        create_general_track(db)
    headers, user_id = authenticate(client, "proposal@example.com")

    body = request_proposal(client, headers)

    assert body["confirmation_required"]["tool_name"] == "add_vocabulary"
    assert body["confirmation_required"]["vocabulary"]["word"] == "resilient"
    assert vocabulary_count(session_factory, user_id) == 0


def test_confirmation_succeeds_and_replay_is_rejected(
    client: TestClient, session_factory: Any
) -> None:
    with session_factory() as db:
        create_general_track(db)
    headers, user_id = authenticate(client, "confirm@example.com")
    proposal = request_proposal(client, headers)["confirmation_required"]

    confirmed = client.post(
        "/api/v1/ai/actions/confirm",
        headers=headers,
        json={"action_token": proposal["action_token"]},
    )
    replay = client.post(
        "/api/v1/ai/actions/confirm",
        headers=headers,
        json={"action_token": proposal["action_token"]},
    )

    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "executed"
    assert confirmed.json()["vocabulary"]["word"] == "resilient"
    assert vocabulary_count(session_factory, user_id) == 1
    assert replay.status_code == 409
    assert replay.json()["detail"] == "AI action was already handled."


def test_cancellation_does_not_mutate_database(
    client: TestClient, session_factory: Any
) -> None:
    with session_factory() as db:
        create_general_track(db)
    headers, user_id = authenticate(client, "cancel@example.com")
    proposal = request_proposal(client, headers)["confirmation_required"]

    canceled = client.post(
        "/api/v1/ai/actions/cancel",
        headers=headers,
        json={"action_token": proposal["action_token"]},
    )

    assert canceled.status_code == 200
    assert canceled.json()["status"] == "canceled"
    assert vocabulary_count(session_factory, user_id) == 0


def test_tampered_action_is_rejected(client: TestClient, session_factory: Any) -> None:
    with session_factory() as db:
        create_general_track(db)
    headers, _ = authenticate(client, "tampered@example.com")
    token = request_proposal(client, headers)["confirmation_required"]["action_token"]

    response = client.post(
        "/api/v1/ai/actions/confirm",
        headers=headers,
        json={"action_token": token + "tampered"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "AI action token is invalid."


def test_expired_action_is_rejected(client: TestClient) -> None:
    headers, user_id = authenticate(client, "expired@example.com")
    settings = get_settings()
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "sub": str(user_id),
            "type": "ai_action",
            "tool": "add_vocabulary",
            "args": add_arguments(),
            "iat": now - timedelta(minutes=2),
            "exp": now - timedelta(minutes=1),
            "jti": str(uuid4()),
            "iss": settings.jwt_issuer,
            "aud": settings.ai_action_token_audience,
        },
        settings.jwt_secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )

    response = client.post(
        "/api/v1/ai/actions/confirm",
        headers=headers,
        json={"action_token": token},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "AI action has expired."


def test_cross_user_confirmation_is_rejected(
    client: TestClient, session_factory: Any
) -> None:
    with session_factory() as db:
        create_general_track(db)
    owner_headers, owner_id = authenticate(client, "owner@example.com")
    attacker_headers, attacker_id = authenticate(client, "attacker@example.com")
    token = request_proposal(client, owner_headers)["confirmation_required"]["action_token"]

    response = client.post(
        "/api/v1/ai/actions/confirm",
        headers=attacker_headers,
        json={"action_token": token},
    )

    assert response.status_code == 403
    assert vocabulary_count(session_factory, owner_id) == 0
    assert vocabulary_count(session_factory, attacker_id) == 0


@pytest.mark.parametrize(
    "arguments",
    [
        add_arguments(user_id=str(uuid4())),
        add_arguments(level_code="Z9"),
        add_arguments(word=" "),
    ],
)
def test_model_supplied_identity_or_invalid_arguments_are_rejected_without_write(
    client: TestClient,
    session_factory: Any,
    arguments: dict[str, object],
) -> None:
    with session_factory() as db:
        create_general_track(db)
    headers, user_id = authenticate(client, f"invalid-{uuid4()}@example.com")
    provider = SequenceProvider(
        [
            proposal_provider(arguments).responses[0],
            {"content": "I could not prepare that vocabulary item."},
        ]
    )
    app.dependency_overrides[get_chat_ai_provider] = lambda: provider

    response = client.post(
        "/api/v1/ai/chat",
        headers=headers,
        json={"messages": [{"role": "user", "content": "Add this word"}]},
    )

    assert response.status_code == 200
    assert response.json()["confirmation_required"] is None
    assert vocabulary_count(session_factory, user_id) == 0


def test_duplicate_confirmation_uses_existing_business_rule(
    client: TestClient, session_factory: Any
) -> None:
    with session_factory() as db:
        create_general_track(db)
    headers, user_id = authenticate(client, "duplicate@example.com")
    first_token, _ = issue_action_token(
        tool_name="add_vocabulary", arguments=add_arguments(), user_id=user_id
    )
    second_token, _ = issue_action_token(
        tool_name="add_vocabulary", arguments=add_arguments(), user_id=user_id
    )
    first = client.post(
        "/api/v1/ai/actions/confirm", headers=headers, json={"action_token": first_token}
    )
    duplicate = client.post(
        "/api/v1/ai/actions/confirm", headers=headers, json={"action_token": second_token}
    )

    assert first.status_code == 200
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["existing_vocabulary_id"] == first.json()["vocabulary"]["id"]
    assert vocabulary_count(session_factory, user_id) == 1


def test_write_tool_cannot_bypass_confirmation(session_factory: Any) -> None:
    with session_factory() as db:
        track = create_general_track(db)
        user_id = uuid4()
        assert track.id
        with pytest.raises(ToolConfirmationRequiredError):
            execute_tool("add_vocabulary", add_arguments(), db, user_id)
        assert db.scalar(select(func.count()).select_from(Vocabulary)) == 0


def test_read_tools_remain_directly_executable(session_factory: Any) -> None:
    with session_factory() as db:
        result = execute_tool("get_learning_stats", {}, db, uuid4())
    assert result["total_vocabulary"] == 0


def test_unknown_signed_action_is_safely_rejected(client: TestClient) -> None:
    headers, user_id = authenticate(client, "unknown-action@example.com")
    token, _ = issue_action_token(
        tool_name="not_registered", arguments={}, user_id=user_id
    )

    response = client.post(
        "/api/v1/ai/actions/confirm",
        headers=headers,
        json={"action_token": token},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "AI action token is invalid."
    assert "not_registered" not in response.text


@pytest.mark.parametrize(
    ("tool_name", "arguments"),
    [
        ("get_learning_stats", {}),
        ("add_vocabulary", add_arguments(user_id=str(uuid4()))),
    ],
)
def test_confirmation_revalidates_tool_metadata_and_arguments(
    client: TestClient,
    session_factory: Any,
    tool_name: str,
    arguments: dict[str, object],
) -> None:
    with session_factory() as db:
        create_general_track(db)
    headers, user_id = authenticate(client, f"revalidate-{uuid4()}@example.com")
    token, _ = issue_action_token(
        tool_name=tool_name,
        arguments=arguments,
        user_id=user_id,
    )

    response = client.post(
        "/api/v1/ai/actions/confirm",
        headers=headers,
        json={"action_token": token},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "AI action token is invalid."
    assert vocabulary_count(session_factory, user_id) == 0


def test_agent_rejects_mixed_read_and_write_tool_round(
    client: TestClient, session_factory: Any
) -> None:
    with session_factory() as db:
        create_general_track(db)
    headers, user_id = authenticate(client, "mixed-tools@example.com")
    provider = SequenceProvider(
        [
            {
                "tool_calls": [
                    {
                        "id": "write",
                        "name": "add_vocabulary",
                        "arguments": json.dumps(add_arguments()),
                    },
                    {
                        "id": "read",
                        "name": "get_learning_stats",
                        "arguments": "{}",
                    },
                ]
            }
        ]
    )
    app.dependency_overrides[get_chat_ai_provider] = lambda: provider

    response = client.post(
        "/api/v1/ai/chat",
        headers=headers,
        json={"messages": [{"role": "user", "content": "Add and inspect"}]},
    )

    assert response.status_code == 502
    assert response.json()["detail"] == "AI service returned an invalid response."
    assert vocabulary_count(session_factory, user_id) == 0


def test_action_logs_never_include_token_or_argument_values(
    caplog: pytest.LogCaptureFixture,
    client: TestClient,
    session_factory: Any,
) -> None:
    with session_factory() as db:
        create_general_track(db)
    headers, _ = authenticate(client, "safe-log@example.com")
    marker = "SECRET_ARGUMENT_MARKER"
    proposal = request_proposal(
        client, headers, add_arguments(translation=marker)
    )["confirmation_required"]
    caplog.clear()

    with caplog.at_level(logging.INFO):
        response = client.post(
            "/api/v1/ai/actions/confirm",
            headers=headers,
            json={"action_token": proposal["action_token"]},
        )

    assert response.status_code == 200
    assert proposal["action_token"] not in caplog.text
    assert marker not in caplog.text
    assert "tool=add_vocabulary" in caplog.text
