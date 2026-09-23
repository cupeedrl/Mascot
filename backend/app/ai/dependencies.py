from __future__ import annotations

from functools import lru_cache

from app.ai.groq_provider import GroqVocabularyProvider
from app.ai.openai_provider import OpenAIVocabularyProvider
from app.ai.provider import ChatAIProvider, ExerciseAIProvider, VocabularyAIProvider
from app.core.config import get_settings


@lru_cache
def get_vocabulary_ai_provider() -> VocabularyAIProvider:
    settings = get_settings()
    if settings.ai_provider == "groq":
        api_key = (
            settings.groq_api_key.get_secret_value()
            if settings.groq_api_key is not None
            else ""
        )
        return GroqVocabularyProvider(
            api_key=api_key,
            model=settings.groq_model,
            base_url=settings.groq_base_url,
            timeout_seconds=settings.ai_request_timeout_seconds,
            max_output_tokens=settings.ai_max_output_tokens,
            exercise_max_output_tokens=settings.ai_exercise_max_output_tokens,
            exercise_reasoning_effort=settings.ai_exercise_reasoning_effort,
            exercise_model=settings.groq_exercise_model,
        )

    api_key = settings.openai_api_key.get_secret_value() if settings.openai_api_key else ""
    return OpenAIVocabularyProvider(
        api_key=api_key,
        model=settings.openai_model,
        timeout_seconds=settings.ai_request_timeout_seconds,
        max_output_tokens=settings.ai_max_output_tokens,
        exercise_max_output_tokens=settings.ai_exercise_max_output_tokens,
    )


def get_exercise_ai_provider() -> ExerciseAIProvider:
    """Reuse the configured provider instance without creating a second adapter."""

    return get_vocabulary_ai_provider()


def get_chat_ai_provider() -> ChatAIProvider:
    """Reuse the configured provider instance for conversational chat."""

    return get_vocabulary_ai_provider()  # type: ignore[return-value]

