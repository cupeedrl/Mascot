from app.ai.openai_compatible_provider import OpenAICompatibleVocabularyProvider


class GroqVocabularyProvider(OpenAICompatibleVocabularyProvider):
    """Groq-hosted implementation using its OpenAI-compatible Responses API."""

    provider_name = "groq"
    # Groq puts streaming usage in x_groq.usage on the last chunk, so the
    # OpenAI stream_options parameter is not needed.
    stream_include_usage = False
