from __future__ import annotations

import logging
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.ai.chat_agent import run_chat_agent
from app.ai.chat_schema import AgentTrace
from app.ai.dependencies import get_chat_ai_provider
from app.core.config import get_settings
from app.main import app
from app.models.ai_usage_log import AIUsageLog
from app.services.ai_guard import ai_guard
from evals.chatbot_eval import build_eval_cases, run_eval_case

PASSWORD = "StrongPassword123!"


def test_offline_eval_catalog_has_required_scope() -> None:
    cases = build_eval_cases()
    assert 30 <= len(cases) <= 50
    assert {case.category for case in cases} == {
        "normal_learning",
        "read_tool_routing",
        "ambiguous",
        "write_action",
        "injection",
        "guardrail",
        "confirmation_security",
    }


def test_all_offline_eval_cases_pass(session_factory: Any) -> None:
    results = [run_eval_case(case, session_factory) for case in build_eval_cases()]
    failures = [result for result in results if not result.passed]
    assert not failures, failures


def test_agent_trace_collects_sanitized_metrics(
    caplog: Any, session_factory: Any
) -> None:
    class Provider:
        def __init__(self) -> None:
            self.calls = 0

        def generate_chat_response_with_tools(self, messages: list, tool_definitions: list) -> dict:
            self.calls += 1
            if self.calls == 1:
                return {"tool_calls": [{"id": "unsafe\nvalue", "name": "get_learning_stats", "arguments": "{}"}]}
            return {"content": "Done."}

    trace = AgentTrace()
    with session_factory() as db, caplog.at_level(logging.INFO):
        result = run_chat_agent(
            Provider(), [{"role": "user", "content": "stats"}], db,
            __import__("uuid").uuid4(), trace=trace, request_id="request-safe",
        )

    assert result == "Done."
    assert trace.provider_calls == 2
    assert trace.tool_rounds == 1
    assert trace.total_tool_calls == 1
    assert trace.tool_names == ["get_learning_stats"]
    assert len(trace.tool_latencies_ms) == 1
    assert "unsafe\nvalue" not in caplog.text
    assert "tool_call_id=sha256:" in caplog.text


def test_chat_route_logs_request_summary_and_records_provider_identity(
    caplog: Any, client: TestClient, session_factory: Any
) -> None:
    class Provider:
        def __init__(self) -> None:
            self.calls = 0

        def generate_chat_response_with_tools(self, messages: list, tool_definitions: list) -> dict:
            self.calls += 1
            if self.calls == 1:
                return {"tool_calls": [{"id": "stats-1", "name": "get_learning_stats", "arguments": "{}"}]}
            return {"content": "You have no vocabulary yet."}

    email = "phase6-observability@example.com"
    assert client.post("/api/v1/auth/register", json={"email": email, "password": PASSWORD}).status_code == 201
    login = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    ai_guard._users.clear()
    app.dependency_overrides[get_chat_ai_provider] = Provider

    try:
        with caplog.at_level(logging.INFO):
            response = client.post(
                "/api/v1/ai/chat",
                headers=headers,
                json={"messages": [{"role": "user", "content": "Show my stats"}]},
            )
    finally:
        app.dependency_overrides.pop(get_chat_ai_provider, None)
        ai_guard._users.clear()

    assert response.status_code == 200
    assert len(response.headers["X-Request-ID"]) == 32
    for field in (
        "request_id=", "provider=", "model=", "latency_ms=", "provider_calls=2",
        "tool_rounds=1", "total_tool_calls=1", "tools=get_learning_stats",
        "tool_latencies_ms=", "final_status=success", "error_type=none",
    ):
        assert field in caplog.text

    with session_factory() as db:
        usage = db.scalar(select(AIUsageLog).order_by(AIUsageLog.created_at.desc()))
    settings = get_settings()
    assert usage is not None
    assert usage.provider == settings.ai_provider
    assert usage.model == (
        settings.groq_model if settings.ai_provider == "groq" else settings.openai_model
    )
