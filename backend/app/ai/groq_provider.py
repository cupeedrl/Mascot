from app.ai.openai_compatible_provider import OpenAICompatibleVocabularyProvider


class GroqVocabularyProvider(OpenAICompatibleVocabularyProvider):
    """Groq-hosted implementation using its OpenAI-compatible Responses API."""

    provider_name = "groq"
