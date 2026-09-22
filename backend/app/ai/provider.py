from __future__ import annotations

from typing import List, Protocol

from app.ai.chat_schema import Message, ProviderResult


class AIProviderError(Exception):
    pass


class AIProviderNotConfiguredError(AIProviderError):
    pass


class AIProviderAuthenticationError(AIProviderError):
    pass


class AIProviderTimeoutError(AIProviderError):
    pass


class AIProviderQuotaError(AIProviderError):
    pass


class AIProviderRateLimitError(AIProviderError):
    pass


class AIProviderConfigurationError(AIProviderError):
    pass


class AIProviderRequestError(AIProviderError):
    """Non-retryable provider request rejection with safe diagnostic metadata."""

    def __init__(self, status_code: int | None = None, details: dict[str, object] | None = None) -> None:
        super().__init__("provider rejected the request")
        self.status_code = status_code
        self.details = details or {}


class AIProviderResponseError(AIProviderError):
    """The provider replied, but no safe structured candidate could be read."""

    def __init__(
        self,
        stage: str = "provider_response",
        summary: str = "provider returned no parseable structured result",
    ) -> None:
        super().__init__(summary)
        self.stage = stage
        self.summary = summary


class VocabularyAIProvider(Protocol):
    def generate_vocabulary(
        self,
        word: str,
        part_of_speech: str,
        translation: str,
        learning_context: dict[str, object] | None = None,
    ) -> object:
        """Return untrusted structured candidate data for final service validation."""


class ExerciseAIProvider(Protocol):
    def generate_exercises(
        self,
        vocabulary_context: list[dict[str, object]],
        exercise_type: str,
        count: int,
    ) -> object:
        """Return untrusted structured exercise candidates for validation."""


class ChatAIProvider(Protocol):
    def generate_chat_response(
        self,
        messages: list[dict[str, str]],
    ) -> str:
        """Return conversational completion text for user/assistant message turns."""

    def generate_chat_response_with_tools(
        self,
        messages: List[Message],
        tool_definitions: List[dict],
    ) -> ProviderResult:
        """Return either plain content or tool_calls (or both) for a single provider turn."""
