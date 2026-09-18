"""LangGraph migration: structure, lossless adapter, and parity with the legacy loop.

The parity tests run the same scripted provider through both engines and require
identical observable behavior: every message the provider receives, the tool
definitions, the return value or error stage, and the trace counters.
"""

from __future__ import annotations

import copy
import json
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from sqlalchemy.orm import Session

from app.ai import agent_graph, chat_agent
from app.ai.agent_graph import AGENT_GRAPH, AgentState, run_agent_graph
from app.ai.chat_schema import AgentTrace
from app.ai.langchain_chat_model import (
    ProviderChatModel,
    to_langchain_messages,
    to_provider_messages,
)
from app.ai.prompts import CHAT_ASSISTANT_SYSTEM_PROMPT
from app.ai.provider import AIProviderError, AIProviderResponseError
from app.ai.tools.executor import execute_tool
from app.models.user import User

LIMITS = {
    "max_tool_rounds": 3,
    "max_tool_calls_per_round": 4,
    "max_total_tool_calls": 8,
    "max_tool_argument_bytes": 8192,
    "max_tool_payload_bytes": 65536,
    "tool_timeout_seconds": 5.0,
}

VALID_WORD = {
    "word": "resilient",
    "part_of_speech": "adjective",
    "meaning": "able to recover quickly",
    "translation": "kien cuong",
    "level_code": "B2",
}


def call(call_id: str, name: str, arguments: Any = "{}") -> dict[str, str]:
    if not isinstance(arguments, str):
        arguments = json.dumps(arguments)
    return {"id": call_id, "name": name, "arguments": arguments}


class ScriptedProvider:
    """Returns scripted results in order and records exactly what it received."""

    def __init__(self, responses: list[Any]) -> None:
        self.responses = responses
        self.recorded: list[dict[str, Any]] = []

    def generate_chat_response_with_tools(self, messages: list, tool_definitions: list) -> Any:
        self.recorded.append(
            {
                "messages": copy.deepcopy(list(messages)),
                "tool_definitions": copy.deepcopy(list(tool_definitions)),
            }
        )
        result = self.responses[len(self.recorded) - 1]
        if isinstance(result, Exception):
            raise result
        return copy.deepcopy(result)


def create_user(db: Session) -> User:
    email = f"graph_{uuid4().hex[:8]}@example.com"
    user = User(email=email, normalized_email=email, password_hash="hashed", role="user")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def run_engine(engine: str, responses: list[Any], db: Session, user: User, **overrides: Any):
    provider = ScriptedProvider(copy.deepcopy(responses))
    trace = AgentTrace()
    options = {
        "provider": provider,
        "messages": overrides.pop(
            "messages",
            [
                {"role": "system", "content": CHAT_ASSISTANT_SYSTEM_PROMPT},
                {"role": "user", "content": "Help me study"},
            ],
        ),
        "db": db,
        "user_id": user.id,
        "trace": trace,
        "request_id": "parity",
        "learning_track_id": None,
        **LIMITS,
        **overrides,
    }
    try:
        if engine == "legacy":
            outcome: Any = chat_agent._run_legacy_chat_agent(**options)
        else:
            outcome = run_agent_graph(**options, execute_tool=execute_tool)
    except Exception as exc:  # compared, not swallowed
        outcome = ("raised", type(exc).__name__, getattr(exc, "stage", None))
    trace_summary = (
        trace.provider_calls,
        trace.tool_rounds,
        trace.total_tool_calls,
        trace.tool_names,
        len(trace.tool_latencies_ms),
    )
    return outcome, provider.recorded, trace_summary


PARITY_SCENARIOS: dict[str, tuple[list[Any], dict[str, Any]]] = {
    "direct_answer": ([{"content": "  Hello!  "}], {}),
    "stats_tool": (
        [{"content": None, "tool_calls": [call("c1", "get_learning_stats")]}, {"content": "Done."}],
        {},
    ),
    "due_vocabulary_with_args": (
        [{"tool_calls": [call("c1", "get_due_vocabulary", {"limit": 5})]}, {"content": "Due list."}],
        {},
    ),
    "content_and_tool_calls_together": (
        [{"content": "Checking...", "tool_calls": [call("c1", "get_learning_stats")]}, {"content": "Stats."}],
        {},
    ),
    "two_calls_one_round": (
        [
            {"tool_calls": [call("a", "get_learning_stats"), call("b", "get_due_vocabulary")]},
            {"content": "Both done."},
        ],
        {},
    ),
    "two_rounds": (
        [
            {"tool_calls": [call("r1", "get_learning_stats")]},
            {"tool_calls": [call("r2", "get_due_vocabulary")]},
            {"content": "Two rounds."},
        ],
        {},
    ),
    "unknown_tool": (
        [{"tool_calls": [call("u", "drop_tables")]}, {"content": "Recovered."}],
        {},
    ),
    "malformed_arguments": (
        [{"tool_calls": [call("m", "get_due_vocabulary", "{bad json")]}, {"content": "Recovered."}],
        {},
    ),
    "model_supplied_user_id": (
        [{"tool_calls": [call("i", "get_learning_stats", {"user_id": str(uuid4())})]}, {"content": "Ok."}],
        {},
    ),
    "oversized_arguments": (
        [{"tool_calls": [call("big", "get_due_vocabulary", '{"limit": 5' + " " * 400 + '}')]}, {"content": "Ok."}],
        {"max_tool_argument_bytes": 256},
    ),
    "unsafe_tool_call_id": (
        [{"tool_calls": [call("unsafe\nid", "get_learning_stats")]}, {"content": "Ok."}],
        {},
    ),
    "valid_write_becomes_proposal": (
        [{"tool_calls": [call("w", "add_vocabulary", VALID_WORD)]}],
        {},
    ),
    "invalid_write_is_observed_not_executed": (
        [{"tool_calls": [call("w", "add_vocabulary", {"word": "x"})]}, {"content": "Need more details."}],
        {},
    ),
    "mixed_write_and_read": (
        [{"tool_calls": [call("w", "add_vocabulary", VALID_WORD), call("r", "get_learning_stats")]}],
        {},
    ),
    "max_tool_rounds_exceeded": (
        [{"tool_calls": [call(f"loop{i}", "get_learning_stats")]} for i in range(4)],
        {"max_tool_rounds": 2},
    ),
    "too_many_calls_per_round": (
        [{"tool_calls": [call(f"f{i}", "get_learning_stats") for i in range(3)]}],
        {"max_tool_calls_per_round": 2},
    ),
    "too_many_total_calls": (
        [
            {"tool_calls": [call("t1", "get_learning_stats")]},
            {"tool_calls": [call("t2", "get_learning_stats")]},
        ],
        {"max_total_tool_calls": 1},
    ),
    "empty_response": ([{"content": "   "}], {}),
    "invalid_result_shape": ([{"content": "hi", "unexpected": True}], {}),
    "duplicate_tool_call_ids": (
        [{"tool_calls": [call("same", "get_learning_stats"), call("same", "get_learning_stats")]}],
        {},
    ),
    "provider_error": ([AIProviderError("network down")], {}),
    "unexpected_provider_exception": ([ValueError("boom")], {}),
    "prior_assistant_history": (
        [{"content": "Welcome back."}],
        {
            "messages": [
                {"role": "system", "content": CHAT_ASSISTANT_SYSTEM_PROMPT},
                {"role": "user", "content": "Hi"},
                {"role": "assistant", "content": "Hello!"},
                {"role": "user", "content": "Again"},
            ]
        },
    ),
}


@pytest.mark.parametrize("scenario", sorted(PARITY_SCENARIOS))
def test_langgraph_engine_matches_legacy_loop(scenario: str, session_factory: Any) -> None:
    responses, overrides = PARITY_SCENARIOS[scenario]
    with session_factory() as db:
        user = create_user(db)
        legacy = run_engine("legacy", responses, db, user, **copy.deepcopy(overrides))
        graph = run_engine("langgraph", responses, db, user, **copy.deepcopy(overrides))

    assert graph == legacy


def test_graph_has_explicit_model_tool_loop() -> None:
    drawable = AGENT_GRAPH.get_graph()
    edges = {(edge.source, edge.target, edge.conditional) for edge in drawable.edges}

    assert set(drawable.nodes) == {"__start__", "model", "tools", "__end__"}
    assert edges == {
        ("__start__", "model", False),
        ("model", "tools", True),
        ("model", "__end__", True),
        ("tools", "model", False),
    }


def test_identity_and_db_are_not_graph_state() -> None:
    assert set(AgentState.__annotations__) == {
        "messages",
        "tool_rounds",
        "total_tool_calls",
        "pending_action",
    }


def test_multiple_tool_calls_keep_ids_and_order(session_factory: Any) -> None:
    with session_factory() as db:
        user = create_user(db)
        outcome, recorded, _ = run_engine(
            "langgraph",
            [
                {"tool_calls": [call("first", "get_learning_stats"), call("second", "get_due_vocabulary")]},
                {"content": "Done."},
            ],
            db,
            user,
        )

    assert outcome == "Done."
    second_call = recorded[1]["messages"]
    assert [m["role"] for m in second_call[-3:]] == ["assistant", "tool", "tool"]
    assert [m["tool_call_id"] for m in second_call[-2:]] == ["first", "second"]


def test_write_tool_never_reaches_executor(session_factory: Any) -> None:
    executed: list[str] = []

    def spy_execute_tool(**kwargs: Any) -> dict:
        executed.append(kwargs["name"])
        return execute_tool(**kwargs)

    with session_factory() as db:
        user = create_user(db)
        provider = ScriptedProvider([{"tool_calls": [call("w", "add_vocabulary", VALID_WORD)]}])
        outcome = run_agent_graph(
            provider=provider,
            messages=[{"role": "user", "content": "Add resilient"}],
            db=db,
            user_id=user.id,
            execute_tool=spy_execute_tool,
            trace=None,
            request_id="write",
            learning_track_id=None,
            **LIMITS,
        )

    assert outcome == {"tool_name": "add_vocabulary", "arguments": outcome["arguments"]}
    assert outcome["arguments"]["word"] == "resilient"
    assert executed == []


def test_recursion_limit_backstop_maps_to_stable_error(
    monkeypatch: pytest.MonkeyPatch, session_factory: Any
) -> None:
    monkeypatch.setattr(agent_graph, "recursion_limit", lambda _max_rounds: 2)
    with session_factory() as db:
        user = create_user(db)
        outcome, _, _ = run_engine(
            "langgraph",
            [{"tool_calls": [call(f"loop{i}", "get_learning_stats")]} for i in range(5)],
            db,
            user,
            max_tool_rounds=5,
        )

    assert outcome == ("raised", "AIProviderResponseError", "max_tool_rounds_exceeded")


def test_message_round_trip_is_lossless() -> None:
    messages = [
        {"role": "system", "content": "rules"},
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "previous answer"},
        {"role": "assistant", "content": None, "tool_calls": [call("x", "get_due_vocabulary", "{bad")]},
        {"role": "tool", "tool_call_id": "x", "content": '{"ok": false}'},
    ]

    assert to_provider_messages(to_langchain_messages(messages)) == messages


def test_unsupported_role_is_rejected_with_stable_stage() -> None:
    with pytest.raises(AIProviderResponseError) as exc_info:
        to_langchain_messages([{"role": "developer", "content": "x"}])
    assert exc_info.value.stage == "unsupported_chat_role"


def test_adapter_exposes_standard_langchain_tool_calls() -> None:
    provider = ScriptedProvider(
        [{"tool_calls": [call("ok", "get_due_vocabulary", {"limit": 2}), call("bad", "get_learning_stats", "{nope")]}]
    )

    message = ProviderChatModel(provider=provider).invoke([HumanMessage("hi")])

    assert isinstance(message, AIMessage)
    assert message.tool_calls[0]["name"] == "get_due_vocabulary"
    assert message.tool_calls[0]["args"] == {"limit": 2}
    assert message.invalid_tool_calls[0]["id"] == "bad"
    assert provider.recorded[0]["messages"] == [{"role": "user", "content": "hi"}]


def test_adapter_rejects_untrusted_result_before_building_messages() -> None:
    provider = ScriptedProvider([{"content": 42}])

    with pytest.raises(AIProviderResponseError) as exc_info:
        ProviderChatModel(provider=provider).invoke([HumanMessage("hi")])
    assert exc_info.value.stage == "invalid_content"


@pytest.mark.parametrize(("engine", "expected"), [("langgraph", "graph"), ("legacy", "legacy")])
def test_engine_setting_selects_implementation(
    monkeypatch: pytest.MonkeyPatch, engine: str, expected: str
) -> None:
    used: list[str] = []
    monkeypatch.setattr(chat_agent, "get_settings", lambda: SimpleNamespace(ai_agent_engine=engine))
    monkeypatch.setattr(chat_agent, "run_agent_graph", lambda **_: used.append("graph") or "ok")
    monkeypatch.setattr(chat_agent, "_run_legacy_chat_agent", lambda **_: used.append("legacy") or "ok")

    result = chat_agent.run_chat_agent(
        provider=ScriptedProvider([]),
        messages=[{"role": "user", "content": "hi"}],
        db=None,  # type: ignore[arg-type]
        user_id=uuid4(),
    )

    assert result == "ok"
    assert used == [expected]
