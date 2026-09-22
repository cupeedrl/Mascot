from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.learning_levels import CEFR_LEVEL_CODES, HSK_LEVEL_CODES, get_level_codes
from app.models.language import Language
from app.models.learning_track import LearningTrack
from app.schemas.vocabulary import VocabularyCreate
from app.services.dashboard import get_dashboard_snapshot
from app.services.review import list_due_vocabularies
from app.services.vocabulary import (
    VocabularyNotFoundError,
    create_vocabulary,
    get_owned_vocabulary,
    list_owned_vocabularies,
)

PASSWORD = "StrongPassword123!"


@dataclass(frozen=True)
class Tracks:
    english: LearningTrack
    chinese: LearningTrack


@pytest.fixture
def multilingual_tracks(session_factory: Any) -> Tracks:
    with session_factory() as db:
        english = LearningTrack(
            language=Language(code="en", name="English", native_name="English"),
            code="general-english",
            name="General English",
            description="English vocabulary",
            level_framework="CEFR",
        )
        chinese = LearningTrack(
            language=Language(code="zh", name="Chinese", native_name="中文"),
            code="general-chinese",
            name="General Chinese",
            description="Mandarin Chinese vocabulary",
            level_framework="HSK",
        )
        db.add_all([english, chinese])
        db.commit()
        db.refresh(english)
        db.refresh(chinese)
        return Tracks(english=english, chinese=chinese)


def authenticate(client: TestClient, email: str) -> tuple[dict[str, str], UUID]:
    registered = client.post(
        "/api/v1/auth/register", json={"email": email, "password": PASSWORD}
    )
    assert registered.status_code == 201
    login = client.post(
        "/api/v1/auth/login", json={"email": email, "password": PASSWORD}
    )
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}, UUID(
        registered.json()["id"]
    )


def vocabulary_payload(
    track_id: UUID,
    *,
    level_code: str,
    word: str = "学习",
    meaning: str = "To acquire knowledge through study.",
    translation: str = "học tập",
) -> dict[str, object]:
    return {
        "learning_track_id": str(track_id),
        "word": word,
        "ipa": "xuéxí",
        "part_of_speech": "verb",
        "meaning": meaning,
        "translation": translation,
        "translation_language_code": "vi",
        "example_sentences": ["我每天学习中文。"],
        "level_code": level_code,
        "topic": "Education",
        "learning_status": "new",
    }


def vocabulary_create(
    track_id: UUID,
    *,
    level_code: str,
    word: str,
    meaning: str = "Shared test sense.",
    translation: str = "nghĩa thử nghiệm",
) -> VocabularyCreate:
    return VocabularyCreate.model_validate(
        vocabulary_payload(
            track_id,
            level_code=level_code,
            word=word,
            meaning=meaning,
            translation=translation,
        )
    )


def test_framework_level_registry_preserves_cefr_and_adds_hsk() -> None:
    assert get_level_codes("CEFR") == CEFR_LEVEL_CODES == (
        "A1", "A2", "B1", "B2", "C1", "C2"
    )
    assert get_level_codes("hsk") == HSK_LEVEL_CODES == tuple(
        f"HSK{number}" for number in range(1, 10)
    )
    assert get_level_codes("unknown") == ()


def test_language_and_track_api_exposes_framework_metadata(
    client: TestClient, multilingual_tracks: Tracks
) -> None:
    headers, _ = authenticate(client, "multilingual-catalog@example.com")

    languages = client.get("/api/v1/catalog/languages", headers=headers)
    chinese_tracks = client.get(
        "/api/v1/catalog/learning-tracks?language_code=zh", headers=headers
    )

    assert languages.status_code == 200
    assert {item["code"] for item in languages.json()} == {"en", "zh"}
    assert chinese_tracks.status_code == 200
    assert chinese_tracks.json() == [
        {
            "id": str(multilingual_tracks.chinese.id),
            "code": "general-chinese",
            "name": "General Chinese",
            "description": "Mandarin Chinese vocabulary",
            "level_framework": "HSK",
            "level_codes": list(HSK_LEVEL_CODES),
            "language": {
                "id": str(multilingual_tracks.chinese.language_id),
                "code": "zh",
                "name": "Chinese",
                "native_name": "中文",
            },
        }
    ]


@pytest.mark.parametrize("level_code", HSK_LEVEL_CODES)
def test_all_hsk_levels_are_accepted_for_chinese(
    level_code: str,
    client: TestClient,
    multilingual_tracks: Tracks,
) -> None:
    headers, _ = authenticate(client, f"{level_code.lower()}@example.com")
    response = client.post(
        "/api/v1/vocabularies",
        headers=headers,
        json=vocabulary_payload(
            multilingual_tracks.chinese.id,
            level_code=level_code.lower(),
            word=f"词{level_code[-1]}",
        ),
    )

    assert response.status_code == 201
    assert response.json()["level_code"] == level_code
    assert response.json()["learning_track"]["level_framework"] == "HSK"


@pytest.mark.parametrize(
    ("track_name", "invalid_level"),
    [("english", "HSK1"), ("chinese", "B2")],
)
def test_cross_framework_levels_are_rejected(
    track_name: str,
    invalid_level: str,
    client: TestClient,
    multilingual_tracks: Tracks,
) -> None:
    headers, _ = authenticate(client, f"invalid-{track_name}@example.com")
    track = getattr(multilingual_tracks, track_name)

    response = client.post(
        "/api/v1/vocabularies",
        headers=headers,
        json=vocabulary_payload(track.id, level_code=invalid_level),
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Level is not valid for the selected learning track"


def test_chinese_vocabulary_uses_generic_fields_and_track_relationship(
    client: TestClient, multilingual_tracks: Tracks
) -> None:
    headers, _ = authenticate(client, "chinese-vocabulary@example.com")
    response = client.post(
        "/api/v1/vocabularies",
        headers=headers,
        json=vocabulary_payload(multilingual_tracks.chinese.id, level_code="HSK3"),
    )

    assert response.status_code == 201
    item = response.json()
    assert item["word"] == "学习"
    assert item["ipa"] == "xuéxí"
    assert item["translation"] == "học tập"
    assert item["learning_track"]["language"]["code"] == "zh"


def test_same_sense_is_isolated_by_learning_track(
    session_factory: Any, multilingual_tracks: Tracks
) -> None:
    user_id = uuid4()
    with session_factory() as db:
        english = create_vocabulary(
            db,
            user_id,
            vocabulary_create(multilingual_tracks.english.id, level_code="A1", word="shared"),
        )
        chinese = create_vocabulary(
            db,
            user_id,
            vocabulary_create(multilingual_tracks.chinese.id, level_code="HSK1", word="shared"),
        )

        english_items = list_owned_vocabularies(
            db, user_id, page=1, page_size=20, learning_track_id=multilingual_tracks.english.id
        )
        chinese_items = list_owned_vocabularies(
            db, user_id, page=1, page_size=20, learning_track_id=multilingual_tracks.chinese.id
        )

    assert [item.id for item in english_items.items] == [english.id]
    assert [item.id for item in chinese_items.items] == [chinese.id]


def test_vocabulary_ownership_remains_enforced(
    session_factory: Any, multilingual_tracks: Tracks
) -> None:
    owner_id = uuid4()
    other_user_id = uuid4()
    with session_factory() as db:
        item = create_vocabulary(
            db,
            owner_id,
            vocabulary_create(multilingual_tracks.chinese.id, level_code="HSK2", word="朋友"),
        )
        with pytest.raises(VocabularyNotFoundError):
            get_owned_vocabulary(db, other_user_id, item.id)


def test_review_track_filter_and_dashboard_lifecycle_remain_generic(
    session_factory: Any, multilingual_tracks: Tracks
) -> None:
    user_id = uuid4()
    with session_factory() as db:
        create_vocabulary(
            db,
            user_id,
            vocabulary_create(multilingual_tracks.english.id, level_code="A1", word="hello"),
        )
        create_vocabulary(
            db,
            user_id,
            vocabulary_create(multilingual_tracks.chinese.id, level_code="HSK1", word="你好"),
        )

        english_queue = list_due_vocabularies(
            db, user_id, limit=20, learning_track_id=multilingual_tracks.english.id
        )
        chinese_queue = list_due_vocabularies(
            db, user_id, limit=20, learning_track_id=multilingual_tracks.chinese.id
        )
        dashboard = get_dashboard_snapshot(db, user_id)

    assert [item.word for item in english_queue.items] == ["hello"]
    assert [item.word for item in chinese_queue.items] == ["你好"]
    assert dashboard.total_vocabulary == 2
    assert dashboard.new_words == 2
