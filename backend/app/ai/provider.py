from __future__ import annotations

from typing import Protocol


class AIProviderNotConfiguredError(Exception):
    pass


class AIProviderTimeoutError(Exception):
    pass


class AIProviderError(Exception):
    pass


class AIProviderResponseError(Exception):
    """The provider replied, but no safe structured candidate could be read."""

    def __init__(
        self,
        stage: str = "provider_response",
        summary: str = "provider returned no parseable structured result",
    ) -> None:
        super().__init__(summary)
        self.stage = stage
        self.summary = summary


class AIProviderQuotaError(Exception):
    pass


class AIProviderRateLimitError(Exception):
    pass


class AIProviderConfigurationError(Exception):
    pass


class VocabularyAIProvider(Protocol):
    def generate_vocabulary(self, word: str) -> object:
        """Return untrusted structured candidate data for final service validation."""


class ExerciseAIProvider(Protocol):
    def generate_exercises(
        self,
        vocabulary_context: list[dict[str, object]],
        exercise_type: str,
        count: int,
    ) -> object:
        """Return untrusted structured exercise candidates for validation."""
