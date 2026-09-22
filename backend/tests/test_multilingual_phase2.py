from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi.testclient import TestClient

from app.ai.dependencies import get_vocabulary_ai_provider
from app.ai.tools.learning_tools import (
    handle_get_due_vocabulary,
    handle_get_learning_stats,
)
from app.ai.tools.schemas import GetDueVocabArgs, GetLearningStatsArgs
from app.catalog.loader import load_catalog_from_dir
from app.main import app
from app.models.exercise import Exercise
from app.schemas.ai_exercise import AIMultipleChoiceCandidate
from app.services.dashboard import get_dashboard_snapshot
from app.services.exercise import submit_attempt
from tests.test_multilingual_foundation import (
    Tracks,
    authenticate,
    multilingual_tracks,
    vocabulary_create,
    vocabulary_payload,
)
from app.services.vocabulary import create_vocabulary


class ChineseVocabularyProvider:
    def __init__(self, level: str = "HSK1") -> None:
        self.level = level
        self.context: dict[str, object] | None = None

    def generate_vocabulary(
        self,
        word: str,
        part_of_speech: str,
        translation: str,
        learning_context: dict[str, object] | None = None,
    ) -> object:
        self.context = learning_context
        return {
            "word": word,
            "part_of_speech": part_of_speech,
            "translation": translation,
            "ipa": "xuéxí",
            "definition": "to study or learn",
            "cefr_level": self.level,
            "examples": ["我每天学习中文。"],
            "topic": "Education",
        }


def test_track_scoped_listing_preserves_user_and_language_isolation(
    client: TestClient, multilingual_tracks: Tracks
) -> None:
    owner, _ = authenticate(client, "phase2-list-owner@example.com")
    other, _ = authenticate(client, "phase2-list-other@example.com")
    client.post(
        "/api/v1/vocabularies",
        headers=owner,
        json=vocabulary_payload(multilingual_tracks.english.id, level_code="A1", word="hello"),
    )
    client.post(
        "/api/v1/vocabularies",
        headers=owner,
        json=vocabulary_payload(multilingual_tracks.chinese.id, level_code="HSK1", word="你好"),
    )

    chinese = client.get(
        f"/api/v1/vocabularies?learning_track_id={multilingual_tracks.chinese.id}",
        headers=owner,
    )
    other_user = client.get(
        f"/api/v1/vocabularies?learning_track_id={multilingual_tracks.chinese.id}",
        headers=other,
    )

    assert [item["word"] for item in chinese.json()["items"]] == ["你好"]
    assert other_user.json()["items"] == []


def test_dashboard_and_chat_read_tools_are_track_scoped(
    session_factory: Any, multilingual_tracks: Tracks
) -> None:
    user_id = uuid4()
    with session_factory() as db:
        create_vocabulary(
            db, user_id,
            vocabulary_create(multilingual_tracks.english.id, level_code="A1", word="hello"),
        )
        create_vocabulary(
            db, user_id,
            vocabulary_create(multilingual_tracks.chinese.id, level_code="HSK1", word="你好"),
        )
        snapshot = get_dashboard_snapshot(
            db, user_id, learning_track_id=multilingual_tracks.chinese.id
        )
        stats = handle_get_learning_stats(
            GetLearningStatsArgs(), db, user_id, multilingual_tracks.chinese.id
        )
        due = handle_get_due_vocabulary(
            GetDueVocabArgs(limit=20), db, user_id, multilingual_tracks.chinese.id
        )

    assert snapshot.total_vocabulary == stats.total_vocabulary == 1
    assert [item.word for item in due.items] == ["你好"]
    assert [item.word for item in stats.recent_vocabulary] == ["你好"]


def test_study_calendar_activity_is_track_and_user_scoped(
    client: TestClient, session_factory: Any, multilingual_tracks: Tracks
) -> None:
    owner_headers, owner_id = authenticate(client, "calendar-owner@example.com")
    other_headers, _ = authenticate(client, "calendar-other@example.com")
    with session_factory() as db:
        english = create_vocabulary(
            db,
            owner_id,
            vocabulary_create(
                multilingual_tracks.english.id,
                level_code="A1",
                word="calendar english",
            ),
        )
        chinese = create_vocabulary(
            db,
            owner_id,
            vocabulary_create(
                multilingual_tracks.chinese.id,
                level_code="HSK1",
                word="日历",
            ),
        )
        english.created_at = datetime(2026, 8, 4, 6, tzinfo=UTC)
        chinese.created_at = datetime(2026, 8, 8, 6, tzinfo=UTC)
        db.commit()

    endpoint = "/api/v1/dashboard/study-calendar"
    chinese_calendar = client.get(
        endpoint,
        headers=owner_headers,
        params={
            "learning_track_id": str(multilingual_tracks.chinese.id),
            "year": 2026,
            "month": 8,
        },
    )
    english_calendar = client.get(
        endpoint,
        headers=owner_headers,
        params={
            "learning_track_id": str(multilingual_tracks.english.id),
            "year": 2026,
            "month": 8,
        },
    )
    other_calendar = client.get(
        endpoint,
        headers=other_headers,
        params={
            "learning_track_id": str(multilingual_tracks.chinese.id),
            "year": 2026,
            "month": 8,
        },
    )

    assert chinese_calendar.status_code == 200
    assert chinese_calendar.json()["active_dates"] == ["2026-08-08"]
    assert english_calendar.json()["active_dates"] == ["2026-08-04"]
    assert other_calendar.json()["active_dates"] == []


def test_chinese_ai_generation_receives_metadata_and_validates_hsk(
    client: TestClient, multilingual_tracks: Tracks
) -> None:
    headers, _ = authenticate(client, "phase2-ai-zh@example.com")
    provider = ChineseVocabularyProvider()
    app.dependency_overrides[get_vocabulary_ai_provider] = lambda: provider
    response = client.post(
        "/api/v1/ai/vocabulary",
        headers=headers,
        json={
            "word": "学习",
            "part_of_speech": "verb",
            "translation": "học tập",
            "learning_track_id": str(multilingual_tracks.chinese.id),
        },
    )

    assert response.status_code == 200
    assert response.json()["ipa"] == "xuéxí"
    assert response.json()["cefr_level"] == "HSK1"
    assert provider.context == {
        "language_code": "zh",
        "language_name": "Chinese",
        "level_framework": "HSK",
        "valid_levels": [f"HSK{number}" for number in range(1, 10)],
        "translation_language": "Vietnamese",
    }


def test_chinese_ai_generation_rejects_cross_framework_level(
    client: TestClient, multilingual_tracks: Tracks
) -> None:
    headers, _ = authenticate(client, "phase2-ai-invalid@example.com")
    app.dependency_overrides[get_vocabulary_ai_provider] = lambda: ChineseVocabularyProvider("B2")
    response = client.post(
        "/api/v1/ai/vocabulary",
        headers=headers,
        json={
            "word": "学习",
            "part_of_speech": "verb",
            "translation": "học tập",
            "learning_track_id": str(multilingual_tracks.chinese.id),
        },
    )
    assert response.status_code == 502
    assert response.json()["detail"] == "AI trả về dữ liệu từ vựng không hợp lệ."


def test_chinese_multiple_choice_grading_remains_deterministic(
    session_factory: Any, multilingual_tracks: Tracks
) -> None:
    user_id = uuid4()
    with session_factory() as db:
        exercise = Exercise(
            user_id=user_id,
            learning_track_id=multilingual_tracks.chinese.id,
            exercise_type="multiple_choice",
            prompt="我每天都 _______ 中文。",
            options=[
                {"id": "A", "text": "学习"}, {"id": "B", "text": "水"},
                {"id": "C", "text": "家"}, {"id": "D", "text": "朋友"},
            ],
            correct_answer="A",
            accepted_answers=[],
            source="manual",
        )
        db.add(exercise)
        db.commit()
        result = submit_attempt(db, user_id, exercise.id, "a", None)
    assert result.attempt.is_correct is True


def test_chinese_multiple_choice_schema_accepts_natural_punctuation() -> None:
    vocabulary_id = uuid4()
    candidate = AIMultipleChoiceCandidate.model_validate(
        {
            "exercise_type": "multiple_choice",
            "prompt": "我每天都 _______ 中文。",
            "options": [
                {"id": "A", "text": "学习"},
                {"id": "B", "text": "水"},
                {"id": "C", "text": "家"},
                {"id": "D", "text": "朋友"},
            ],
            "correct_answer": "A",
            "explanation": "学习 phù hợp với ngữ cảnh học tiếng Trung.",
            "target_vocabulary_id": vocabulary_id,
        }
    )
    assert candidate.prompt.endswith("。")


def test_chinese_cloze_grading_remains_deterministic(
    session_factory: Any, multilingual_tracks: Tracks
) -> None:
    user_id = uuid4()
    option_rows = [
        {"id": "A", "text": "学习"}, {"id": "B", "text": "喜欢"},
        {"id": "C", "text": "朋友"}, {"id": "D", "text": "水"},
    ]
    with session_factory() as db:
        exercise = Exercise(
            user_id=user_id,
            learning_track_id=multilingual_tracks.chinese.id,
            exercise_type="fill_in_blank",
            prompt="中文学习\n\n我 (1) ______ 中文，也 (2) ______ 茶。我的 (3) ______ 来我 (4) ______。",
            options=[{"number": number, "options": option_rows} for number in range(1, 5)],
            correct_answer=json.dumps({"1": "A", "2": "B", "3": "C", "4": "D"}),
            accepted_answers=[],
            explanation=json.dumps({str(number): "Giải thích" for number in range(1, 5)}),
            source="manual",
        )
        db.add(exercise)
        db.commit()
        result = submit_attempt(
            db, user_id, exercise.id, None,
            {"1": "a", "2": "b", "3": "c", "4": "d"},
        )
    assert result.attempt.is_correct is True
    assert result.score_percent == 100


def test_chinese_catalog_fixture_is_framework_aware() -> None:
    data_dir = Path(__file__).parents[1] / "app" / "catalog" / "data" / "zh"
    sets = load_catalog_from_dir(data_dir)
    assert len(sets) == 1
    assert sets[0].level_framework == "HSK"
    assert sets[0].level_code == "HSK1"
    assert sets[0].entries[0].ipa == "xuéxí"
