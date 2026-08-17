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
        self.calls: list[str] = []

    def generate_vocabulary(self, word: str) -> object:
        self.calls.append(word)
        if self.error is not None:
            raise self.error
        return self.result


def valid_candidate(**overrides: object) -> dict[str, object]:
    candidate: dict[str, object] = {
        "word": "solely",
        "part_of_speech": "adverb",
        "definition": "Only and not involving anyone or anything else.",
        "translation": "chỉ, duy nhất",
        "cefr_level": "B2",
        "examples": ["The decision was based solely on cost."],
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
        json={"word": "  solely  "},
    )

    assert response.status_code == 200
    assert response.json() == valid_candidate()
    assert provider.calls == ["solely"]


def test_generation_requires_authentication(client: TestClient) -> None:
    provider = FakeVocabularyProvider()
    use_fake_provider(provider)

    response = client.post("/api/v1/ai/vocabulary", json={"word": "solely"})

    assert response.status_code == 401
    assert provider.calls == []


@pytest.mark.parametrize(
    "payload",
    [
        {"word": ""},
        {"word": "   "},
        {"word": "two words"},
        {"word": "word!"},
        {"word": "a" * 81},
        {},
    ],
)
def test_invalid_word_is_rejected(client: TestClient, payload: dict[str, str]) -> None:
    headers = authenticate(client, f"invalid-{uuid.uuid4()}@example.com")
    provider = FakeVocabularyProvider()
    use_fake_provider(provider)

    response = client.post("/api/v1/ai/vocabulary", headers=headers, json=payload)

    assert response.status_code == 422
    assert provider.calls == []


def test_malformed_provider_output_returns_safe_error(client: TestClient) -> None:
    headers = authenticate(client)
    use_fake_provider(FakeVocabularyProvider(result={"word": "solely"}))

    response = client.post(
        "/api/v1/ai/vocabulary", headers=headers, json={"word": "solely"}
    )

    assert response.status_code == 502
    assert response.json()["detail"] == "AI trả về dữ liệu từ vựng không hợp lệ."


def test_invalid_cefr_output_returns_safe_error(client: TestClient) -> None:
    headers = authenticate(client)
    use_fake_provider(FakeVocabularyProvider(result=valid_candidate(cefr_level="Z9")))

    response = client.post(
        "/api/v1/ai/vocabulary", headers=headers, json={"word": "solely"}
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
        "/api/v1/ai/vocabulary", headers=headers, json={"word": "solely"}
    )
    assert response.status_code == 502


def test_provider_failure_returns_safe_error(client: TestClient) -> None:
    headers = authenticate(client)
    use_fake_provider(FakeVocabularyProvider(error=AIProviderError()))

    response = client.post(
        "/api/v1/ai/vocabulary", headers=headers, json={"word": "solely"}
    )

    assert response.status_code == 502
    assert response.json()["detail"] == "Dịch vụ AI tạm thời không khả dụng."


def test_provider_timeout_returns_safe_error(client: TestClient) -> None:
    headers = authenticate(client)
    use_fake_provider(FakeVocabularyProvider(error=AIProviderTimeoutError()))

    response = client.post(
        "/api/v1/ai/vocabulary", headers=headers, json={"word": "solely"}
    )

    assert response.status_code == 504
    assert "quá thời gian chờ" in response.json()["detail"]


def test_missing_provider_configuration_returns_safe_error(client: TestClient) -> None:
    headers = authenticate(client)
    use_fake_provider(FakeVocabularyProvider(error=AIProviderNotConfiguredError()))

    response = client.post(
        "/api/v1/ai/vocabulary", headers=headers, json={"word": "solely"}
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "AI chưa được cấu hình trên máy chủ."


def test_provider_quota_failure_returns_actionable_error(client: TestClient) -> None:
    headers = authenticate(client)
    use_fake_provider(FakeVocabularyProvider(error=AIProviderQuotaError()))

    response = client.post(
        "/api/v1/ai/vocabulary", headers=headers, json={"word": "solely"}
    )

    assert response.status_code == 503
    assert "Usage" in response.json()["detail"]
    assert "quota" in response.json()["detail"]


def test_provider_rate_limit_returns_retryable_error(client: TestClient) -> None:
    headers = authenticate(client)
    use_fake_provider(FakeVocabularyProvider(error=AIProviderRateLimitError()))

    response = client.post(
        "/api/v1/ai/vocabulary", headers=headers, json={"word": "solely"}
    )

    assert response.status_code == 429
    assert "thử lại sau" in response.json()["detail"]


def test_invalid_provider_credentials_return_configuration_error(
    client: TestClient,
) -> None:
    headers = authenticate(client)
    use_fake_provider(FakeVocabularyProvider(error=AIProviderConfigurationError()))

    response = client.post(
        "/api/v1/ai/vocabulary", headers=headers, json={"word": "solely"}
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
        "/api/v1/ai/vocabulary", headers=headers, json={"word": "solely"}
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
        "/api/v1/ai/vocabulary", headers=headers, json={"word": "solely"}
    ).json()

    response = client.post(
        "/api/v1/vocabularies",
        headers=headers,
        json={
            "learning_track_id": str(general_english_track_id),
            "word": preview["word"],
            "part_of_speech": preview["part_of_speech"],
            "meaning": "An edited definition.",
            "translation": preview["translation"],
            "translation_language_code": "vi",
            "example_sentences": preview["examples"],
            "level_code": preview["cefr_level"],
            "topic": None,
            "learning_status": "new",
        },
    )

    assert response.status_code == 201
    assert response.json()["meaning"] == "An edited definition."
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(Vocabulary)) == 1


def test_ai_assisted_save_uses_normal_duplicate_validation(
    client: TestClient,
    general_english_track_id: uuid.UUID,
) -> None:
    headers = authenticate(client)
    use_fake_provider(FakeVocabularyProvider())
    preview = client.post(
        "/api/v1/ai/vocabulary", headers=headers, json={"word": "solely"}
    ).json()
    payload = {
        "learning_track_id": str(general_english_track_id),
        "word": preview["word"],
        "part_of_speech": preview["part_of_speech"],
        "meaning": preview["definition"],
        "translation": preview["translation"],
        "example_sentences": preview["examples"],
        "level_code": preview["cefr_level"],
        "topic": None,
        "learning_status": "new",
    }
    assert client.post("/api/v1/vocabularies", headers=headers, json=payload).status_code == 201
    duplicate = client.post("/api/v1/vocabularies", headers=headers, json=payload)
    assert duplicate.status_code == 409
