"""Request-scoped sink for streamed chat drafts (POST /ai/chat/stream).

The stream route opens ``stream_events_to(callback)`` around one chat turn.
``ProviderChatModel`` picks the callback up and asks a provider that declares
``supports_streaming`` to stream; the provider then reports
``("delta", text)`` while text arrives and ``("discard", "")`` when the
draft so far is not the answer (a retry, a fallback, or a reply that turned
into tool calls).

Deltas never enter the conversation: the agent still validates the complete
provider result, and the route's final ``done`` event carries the validated,
persisted AIChatResponse. Like ``app.ai.token_usage``, this is a ContextVar so
the agent graph and both engines keep their signatures; LangGraph copies the
context into the threads that run graph nodes. The legacy engine calls the
provider directly and therefore never streams.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar

StreamCallback = Callable[[str, str], None]

_current_callback: ContextVar[StreamCallback | None] = ContextVar(
    "mascot_chat_stream_callback", default=None
)


def current_stream_callback() -> StreamCallback | None:
    return _current_callback.get()


@contextmanager
def stream_events_to(callback: StreamCallback) -> Iterator[None]:
    token = _current_callback.set(callback)
    try:
        yield
    finally:
        _current_callback.reset(token)
