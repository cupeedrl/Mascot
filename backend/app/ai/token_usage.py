"""Request-scoped token usage accounting.

Providers are process-wide singletons (``lru_cache`` in ``ai/dependencies.py``),
so they cannot keep per-request usage on ``self``. Instead a route opens a
``TokenUsage`` tracker in a ContextVar, every provider call adds what the SDK
reported, and ``record_ai_usage`` reads the totals when it writes the log row.

A ContextVar is isolated per request because FastAPI runs each sync endpoint in
its own copy of the context. LangGraph also copies the context into the
threads that run graph nodes; those copies share the same ``TokenUsage``
object, so mutations made by provider calls are visible to the route.
"""

from __future__ import annotations

import functools
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Callable, TypeVar

F = TypeVar("F", bound=Callable[..., Any])


@dataclass
class TokenUsage:
    """Token totals of every provider call made while handling one request."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    provider_calls: int = 0
    # Provider and model of the most recent call that reported usage. With a
    # fallback provider configured this is the one that actually answered.
    model: str | None = None
    provider: str | None = None

    def add(
        self,
        *,
        model: str | None,
        input_tokens: int | None,
        output_tokens: int | None,
        total_tokens: int | None,
        provider: str | None = None,
    ) -> None:
        self.provider_calls += 1
        if provider:
            self.provider = provider
        self.input_tokens += input_tokens or 0
        self.output_tokens += output_tokens or 0
        if total_tokens is None:
            total_tokens = (input_tokens or 0) + (output_tokens or 0)
        self.total_tokens += total_tokens
        if model:
            self.model = model


_current_usage: ContextVar[TokenUsage | None] = ContextVar(
    "mascot_token_usage", default=None
)


def current_token_usage() -> TokenUsage | None:
    return _current_usage.get()


def tracks_token_usage(endpoint: F) -> F:
    """Open a fresh TokenUsage tracker for the duration of a sync endpoint."""

    @functools.wraps(endpoint)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        token = _current_usage.set(TokenUsage())
        try:
            return endpoint(*args, **kwargs)
        finally:
            _current_usage.reset(token)

    return wrapper  # type: ignore[return-value]


def _token_count(raw_usage: Any, *names: str) -> int | None:
    # Provider output is untrusted: accept only real non-negative integers.
    for name in names:
        value = getattr(raw_usage, name, None)
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            return value
    return None


def record_provider_usage(
    response: Any, model: str | None, provider: str | None = None
) -> dict[str, int | None]:
    """Add one SDK response's usage to the active tracker and return it for logging.

    Chat Completions reports ``prompt_tokens``/``completion_tokens``; the
    Responses API reports ``input_tokens``/``output_tokens``. Both are read.
    """
    raw_usage = getattr(response, "usage", None)
    if raw_usage is None:
        return {}
    usage = {
        "prompt_tokens": _token_count(raw_usage, "prompt_tokens", "input_tokens"),
        "completion_tokens": _token_count(
            raw_usage, "completion_tokens", "output_tokens"
        ),
        "total_tokens": _token_count(raw_usage, "total_tokens"),
    }
    if all(value is None for value in usage.values()):
        return {}

    tracker = _current_usage.get()
    if tracker is not None:
        tracker.add(
            model=model,
            input_tokens=usage["prompt_tokens"],
            output_tokens=usage["completion_tokens"],
            total_tokens=usage["total_tokens"],
            provider=provider,
        )
    return usage
