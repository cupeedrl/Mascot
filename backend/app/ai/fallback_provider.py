"""Primary/secondary provider wrapper for transient provider failures.

The primary provider already retries 429s, timeouts and 5xx/network errors
with backoff. If it still fails for one of those reasons, the same call is
made once on the secondary provider. Configuration, request and response
errors are raised unchanged: switching providers would hide a misconfigured
key or model, and a rejected request or an unusable answer is not an outage.
"""

from __future__ import annotations

import logging
from typing import Any, List

from app.ai.chat_schema import Message, ProviderResult
from app.ai.provider import (
    AIProviderError,
    AIProviderQuotaError,
    AIProviderRateLimitError,
    AIProviderTimeoutError,
    ChatAIProvider,
    ExerciseAIProvider,
    VocabularyAIProvider,
)

logger = logging.getLogger(__name__)

_FALLBACK_ERRORS = (AIProviderRateLimitError, AIProviderQuotaError, AIProviderTimeoutError)


def should_fall_back(exc: AIProviderError) -> bool:
    # A bare AIProviderError is what providers raise for 5xx/network failures;
    # its subclasses not listed above are configuration/request/response errors.
    return isinstance(exc, _FALLBACK_ERRORS) or type(exc) is AIProviderError


class FallbackAIProvider(VocabularyAIProvider, ExerciseAIProvider, ChatAIProvider):
    """Delegates every call to ``primary``, retrying once on ``secondary``."""

    def __init__(
        self,
        primary: Any,
        secondary: Any,
        *,
        primary_name: str,
        secondary_name: str,
    ) -> None:
        self._primary = primary
        self._secondary = secondary
        self._primary_name = primary_name
        self._secondary_name = secondary_name

    @property
    def supports_streaming(self) -> bool:
        return bool(
            getattr(self._primary, "supports_streaming", False)
            and getattr(self._secondary, "supports_streaming", False)
        )

    def _call(self, method: str, *args: Any, **kwargs: Any) -> Any:
        try:
            return getattr(self._primary, method)(*args, **kwargs)
        except AIProviderError as exc:
            if not should_fall_back(exc):
                raise
            logger.warning(
                "AI provider fallback (method=%s, from=%s, to=%s, error=%s)",
                method,
                self._primary_name,
                self._secondary_name,
                type(exc).__name__,
            )
        on_event = kwargs.get("on_event")
        if on_event is not None:
            # The secondary starts its answer from scratch.
            on_event("discard", "")
        return getattr(self._secondary, method)(*args, **kwargs)

    def generate_vocabulary(
        self,
        word: str,
        part_of_speech: str,
        translation: str,
        learning_context: dict[str, object] | None = None,
    ) -> object:
        return self._call(
            "generate_vocabulary", word, part_of_speech, translation, learning_context
        )

    def generate_exercises(
        self,
        vocabulary_context: list[dict[str, object]],
        exercise_type: str,
        count: int,
    ) -> object:
        return self._call("generate_exercises", vocabulary_context, exercise_type, count)

    def generate_chat_response(self, messages: list[dict[str, str]]) -> str:
        return self._call("generate_chat_response", messages)

    def generate_chat_response_with_tools(
        self,
        messages: List[Message],
        tool_definitions: List[dict],
        on_event: Any = None,
    ) -> ProviderResult:
        kwargs: dict[str, Any] = {"messages": messages, "tool_definitions": tool_definitions}
        if on_event is not None:
            kwargs["on_event"] = on_event
        return self._call("generate_chat_response_with_tools", **kwargs)
