from __future__ import annotations

from types import SimpleNamespace

from pydantic import SecretStr

from app.ai import dependencies
from app.ai.groq_provider import GroqVocabularyProvider
from app.ai.openai_provider import OpenAIVocabularyProvider
from app.schemas.ai_vocabulary import VocabularyCandidate


def provider_settings(provider: str) -> SimpleNamespace:
    return SimpleNamespace(
        ai_provider=provider,
        groq_api_key=SecretStr("groq-test-key"),
        groq_model="openai/gpt-oss-20b",
        groq_base_url="https://api.groq.com/openai/v1",
        openai_api_key=SecretStr("openai-test-key"),
        openai_model="gpt-5.4-nano",
        ai_request_timeout_seconds=20.0,
        ai_max_output_tokens=800,
        ai_exercise_max_output_tokens=4000,
    )


def test_provider_factory_selects_groq(monkeypatch) -> None:
    dependencies.get_vocabulary_ai_provider.cache_clear()
    monkeypatch.setattr(dependencies, "get_settings", lambda: provider_settings("groq"))

    provider = dependencies.get_vocabulary_ai_provider()

    assert isinstance(provider, GroqVocabularyProvider)
    assert provider._model == "openai/gpt-oss-20b"
    assert provider._base_url == "https://api.groq.com/openai/v1"
    dependencies.get_vocabulary_ai_provider.cache_clear()


def test_provider_factory_keeps_openai_as_optional_provider(monkeypatch) -> None:
    dependencies.get_vocabulary_ai_provider.cache_clear()
    monkeypatch.setattr(dependencies, "get_settings", lambda: provider_settings("openai"))

    provider = dependencies.get_vocabulary_ai_provider()

    assert isinstance(provider, OpenAIVocabularyProvider)
    assert provider._model == "gpt-5.4-nano"
    assert provider._base_url is None
    dependencies.get_vocabulary_ai_provider.cache_clear()


def test_groq_provider_uses_responses_parse_and_configured_base_url(
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}
    candidate = VocabularyCandidate(
        word="solely",
        part_of_speech="adverb",
        definition="Only and not involving anything else.",
        translation="chỉ, duy nhất",
        cefr_level="B2",
        examples=[
            "The decision was based solely on cost.",
            "She is solely responsible for the project.",
        ],
    )

    class FakeResponses:
        def parse(self, **kwargs):
            captured["parse"] = kwargs
            return SimpleNamespace(output_parsed=candidate)

    class FakeOpenAI:
        def __init__(self, **kwargs) -> None:
            captured["client"] = kwargs
            self.responses = FakeResponses()

    import openai

    monkeypatch.setattr(openai, "OpenAI", FakeOpenAI)
    provider = GroqVocabularyProvider(
        api_key="groq-test-key",
        model="openai/gpt-oss-20b",
        base_url="https://api.groq.com/openai/v1/",
        timeout_seconds=20,
        max_output_tokens=800,
    )

    result = provider.generate_vocabulary("solely")

    assert captured["client"] == {
        "api_key": "groq-test-key",
        "timeout": 20,
        "max_retries": 0,
        "base_url": "https://api.groq.com/openai/v1",
    }
    parse_options = captured["parse"]
    assert isinstance(parse_options, dict)
    assert parse_options["model"] == "openai/gpt-oss-20b"
    assert parse_options["text_format"] is VocabularyCandidate
    assert result["word"] == "solely"
