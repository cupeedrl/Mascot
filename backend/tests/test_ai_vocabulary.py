from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.ai.dependencies import get_vocabulary_ai_provider
from app.ai.provider import (
    AIProviderConfigurationError,
    AIProviderError,
    AIProviderNotConfiguredError,
    AIProviderQuotaError,
    AIProviderRateLimitError,
    AIProviderTimeoutError,
)
from app.main import app
from app.models import Language, LearningTrack, Vocabulary

PASSWORD = "StrongPassword123!"


class FakeVocabularyProvider:
    def __init__(self, result: object | None = None, error: Exception | None = None) -> None:
        self.result = result if result is not None else valid_candidate()
        self.error = error
        self.calls: list[tuple[str, str, str]] = []

    def generate_vocabulary(
        self, word: str, part_of_speech: str, translation: str
    ) -> object:
        self.calls.append((word, part_of_speech, translation))
        if self.error is not None:
            raise self.error
        return self.result


def valid_candidate(**overrides: object) -> dict[str, object]:
    candidate: dict[str, object] = {
        "word": "solely",
        "part_of_speech": "adverb",
        "translation": "chỉ, duy nhất",
        "ipa": "/ˈsəʊl.li/",
        "definition": "Only and not involving anyone or anything else.",
        "cefr_level": "B2",
        "examples": ["The decision was based solely on cost."],
        "topic": "Khác",
    }
    candidate.update(overrides)
    return candidate


def authenticate(client: TestClient, email: str = "ai-learner@example.com") -> dict[str, str]:
    registration = client.post(
        "/api/v1/auth/register", json={"email": email, "password": PASSWORD}
    )
    assert registration.status_code == 201
    login = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def use_fake_provider(provider: FakeVocabularyProvider) -> None:
    app.dependency_overrides[get_vocabulary_ai_provider] = lambda: provider


@pytest.fixture
def general_english_track_id(session_factory: sessionmaker[Session]) -> uuid.UUID:
    with session_factory() as db:
        language = Language(code="en", name="English", native_name="English")
        track = LearningTrack(
            language=language,
            code="general-english",
            name="General English",
            description="General English learning for V1",
            level_framework="CEFR",
        )
        db.add(track)
        db.commit()
        return track.id


def test_authenticated_generation_returns_valid_structured_preview(client: TestClient) -> None:
    headers = authenticate(client)
    provider = FakeVocabularyProvider()
    use_fake_provider(provider)

    response = client.post(
        "/api/v1/ai/vocabulary",
        headers=headers,
        json={
            "word": "  solely  ",
            "part_of_speech": "adverb",
            "translation": "chỉ, duy nhất",
        },
    )

    assert response.status_code == 200
    assert response.json() == valid_candidate()
    assert provider.calls == [("solely", "adverb", "chỉ, duy nhất")]


def test_generation_requires_authentication(client: TestClient) -> None:
    provider = FakeVocabularyProvider()
    use_fake_provider(provider)

    response = client.post(
        "/api/v1/ai/vocabulary",
        json={"word": "solely", "part_of_speech": "adverb", "translation": "chỉ"},
    )

    assert response.status_code == 401
    assert provider.calls == []


@pytest.mark.parametrize(
    "payload",
    [
        {"word": "", "part_of_speech": "adverb", "translation": "chỉ"},
        {"word": "   ", "part_of_speech": "adverb", "translation": "chỉ"},
        {"word": "two words", "part_of_speech": "noun", "translation": "hai từ"},
        {"word": "word!", "part_of_speech": "noun", "translation": "từ"},
        {"word": "a" * 81, "part_of_speech": "noun", "translation": "dài"},
        {"word": "solely", "part_of_speech": "", "translation": "chỉ"},
        {"word": "solely", "part_of_speech": "adverb", "translation": ""},
        {},
    ],
)
def test_invalid_request_is_rejected(client: TestClient, payload: dict[str, str]) -> None:
    headers = authenticate(client, f"invalid-{uuid.uuid4()}@example.com")
    provider = FakeVocabularyProvider()
    use_fake_provider(provider)

    response = client.post("/api/v1/ai/vocabulary", headers=headers, json=payload)

    assert response.status_code == 422
    assert provider.calls == []


def test_sense_constraints_preserved_and_not_overwritten(client: TestClient) -> None:
    headers = authenticate(client)
    # Even if provider attempts to return a different word/POS/translation
    use_fake_provider(
        FakeVocabularyProvider(
            result={
                "word": "bank",
                "part_of_speech": "verb",
                "translation": "gửi tiền",
                "ipa": "/bæŋk/",
                "definition": "The land alongside a body of water.",
                "cefr_level": "B1",
                "examples": ["They had a picnic on the river bank."],
                "topic": "Nature",
            }
        )
    )

    response = client.post(
        "/api/v1/ai/vocabulary",
        headers=headers,
        json={"word": "bank", "part_of_speech": "noun", "translation": "bờ sông"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["word"] == "bank"
    assert data["part_of_speech"] == "noun"  # User choice preserved
    assert data["translation"] == "bờ sông"  # User choice preserved
    assert data["ipa"] == "/bæŋk/"
    assert data["definition"] == "The land alongside a body of water."


def test_malformed_provider_output_returns_safe_error(client: TestClient) -> None:
    headers = authenticate(client)
    use_fake_provider(FakeVocabularyProvider(result={"word": "solely"}))

    response = client.post(
        "/api/v1/ai/vocabulary",
        headers=headers,
        json={"word": "solely", "part_of_speech": "adverb", "translation": "chỉ"},
    )

    assert response.status_code == 502
    assert response.json()["detail"] == "AI trả về dữ liệu từ vựng không hợp lệ."


def test_invalid_cefr_output_returns_safe_error(client: TestClient) -> None:
    headers = authenticate(client)
    use_fake_provider(FakeVocabularyProvider(result=valid_candidate(cefr_level="Z9")))

    response = client.post(
        "/api/v1/ai/vocabulary",
        headers=headers,
        json={"word": "solely", "part_of_speech": "adverb", "translation": "chỉ"},
    )

    assert response.status_code == 502


def test_multiple_ai_examples_are_rejected(client: TestClient) -> None:
    headers = authenticate(client)
    use_fake_provider(
        FakeVocabularyProvider(
            result=valid_candidate(
                examples=["First natural example.", "Second natural example."]
            )
        )
    )
    response = client.post(
        "/api/v1/ai/vocabulary",
        headers=headers,
        json={"word": "solely", "part_of_speech": "adverb", "translation": "chỉ"},
    )
    assert response.status_code == 502


def test_provider_failure_returns_safe_error(client: TestClient) -> None:
    headers = authenticate(client)
    use_fake_provider(FakeVocabularyProvider(error=AIProviderError()))

    response = client.post(
        "/api/v1/ai/vocabulary",
        headers=headers,
        json={"word": "solely", "part_of_speech": "adverb", "translation": "chỉ"},
    )

    assert response.status_code == 502
    assert response.json()["detail"] == "Dịch vụ AI tạm thời không khả dụng."


def test_provider_timeout_returns_safe_error(client: TestClient) -> None:
    headers = authenticate(client)
    use_fake_provider(FakeVocabularyProvider(error=AIProviderTimeoutError()))

    response = client.post(
        "/api/v1/ai/vocabulary",
        headers=headers,
        json={"word": "solely", "part_of_speech": "adverb", "translation": "chỉ"},
    )

    assert response.status_code == 504
    assert "quá thời gian chờ" in response.json()["detail"]


def test_missing_provider_configuration_returns_safe_error(client: TestClient) -> None:
    headers = authenticate(client)
    use_fake_provider(FakeVocabularyProvider(error=AIProviderNotConfiguredError()))

    response = client.post(
        "/api/v1/ai/vocabulary",
        headers=headers,
        json={"word": "solely", "part_of_speech": "adverb", "translation": "chỉ"},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "AI chưa được cấu hình trên máy chủ."


def test_provider_quota_failure_returns_actionable_error(client: TestClient) -> None:
    headers = authenticate(client)
    use_fake_provider(FakeVocabularyProvider(error=AIProviderQuotaError()))

    response = client.post(
        "/api/v1/ai/vocabulary",
        headers=headers,
        json={"word": "solely", "part_of_speech": "adverb", "translation": "chỉ"},
    )

    assert response.status_code == 503
    assert "Usage" in response.json()["detail"]
    assert "quota" in response.json()["detail"]


def test_provider_rate_limit_returns_retryable_error(client: TestClient) -> None:
    headers = authenticate(client)
    use_fake_provider(FakeVocabularyProvider(error=AIProviderRateLimitError()))

    response = client.post(
        "/api/v1/ai/vocabulary",
        headers=headers,
        json={"word": "solely", "part_of_speech": "adverb", "translation": "chỉ"},
    )

    assert response.status_code == 429
    assert "thử lại sau" in response.json()["detail"]


def test_invalid_provider_credentials_return_configuration_error(
    client: TestClient,
) -> None:
    headers = authenticate(client)
    use_fake_provider(FakeVocabularyProvider(error=AIProviderConfigurationError()))

    response = client.post(
        "/api/v1/ai/vocabulary",
        headers=headers,
        json={"word": "solely", "part_of_speech": "adverb", "translation": "chỉ"},
    )

    assert response.status_code == 503
    assert "không hợp lệ" in response.json()["detail"]


def test_generated_preview_is_not_automatically_persisted(
    client: TestClient,
    session_factory: sessionmaker[Session],
) -> None:
    headers = authenticate(client)
    use_fake_provider(FakeVocabularyProvider())

    response = client.post(
        "/api/v1/ai/vocabulary",
        headers=headers,
        json={"word": "solely", "part_of_speech": "adverb", "translation": "chỉ"},
    )

    assert response.status_code == 200
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(Vocabulary)) == 0


def test_ai_preview_can_be_edited_and_saved_through_existing_vocabulary_api(
    client: TestClient,
    general_english_track_id: uuid.UUID,
    session_factory: sessionmaker[Session],
) -> None:
    headers = authenticate(client)
    use_fake_provider(FakeVocabularyProvider())
    preview = client.post(
        "/api/v1/ai/vocabulary",
        headers=headers,
        json={"word": "solely", "part_of_speech": "adverb", "translation": "chỉ"},
    ).json()

    response = client.post(
        "/api/v1/vocabularies",
        headers=headers,
        json={
            "learning_track_id": str(general_english_track_id),
            "word": preview["word"],
            "ipa": preview["ipa"],
            "part_of_speech": preview["part_of_speech"],
            "meaning": "An edited definition.",
            "translation": preview["translation"],
            "translation_language_code": "vi",
            "example_sentences": preview["examples"],
            "level_code": preview["cefr_level"],
            "topic": preview["topic"],
            "learning_status": "new",
        },
    )

    assert response.status_code == 201
    assert response.json()["meaning"] == "An edited definition."
    assert response.json()["ipa"] == "/ˈsəʊl.li/"
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(Vocabulary)) == 1


def test_ai_assisted_save_uses_normal_duplicate_validation(
    client: TestClient,
    general_english_track_id: uuid.UUID,
) -> None:
    headers = authenticate(client)
    use_fake_provider(FakeVocabularyProvider())
    preview = client.post(
        "/api/v1/ai/vocabulary",
        headers=headers,
        json={"word": "solely", "part_of_speech": "adverb", "translation": "chỉ"},
    ).json()
    payload = {
        "learning_track_id": str(general_english_track_id),
        "word": preview["word"],
        "ipa": preview["ipa"],
        "part_of_speech": preview["part_of_speech"],
        "meaning": preview["definition"],
        "translation": preview["translation"],
        "example_sentences": preview["examples"],
        "level_code": preview["cefr_level"],
        "topic": preview["topic"],
        "learning_status": "new",
    }
    assert client.post("/api/v1/vocabularies", headers=headers, json=payload).status_code == 201
    duplicate = client.post("/api/v1/vocabularies", headers=headers, json=payload)
    assert duplicate.status_code == 409
