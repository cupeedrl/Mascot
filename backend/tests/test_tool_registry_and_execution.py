import pytest
from uuid import uuid4
from sqlalchemy.orm import Session
from app.models.user import User
from app.models.language import Language
from app.models.learning_track import LearningTrack
from app.models.vocabulary import Vocabulary
from datetime import datetime, timezone, timedelta

from app.ai.tools.executor import execute_tool, ToolNotFoundError, ToolValidationError, ToolExecutionError
from app.ai.tools.registry import TOOL_REGISTRY

def create_user(db: Session) -> User:
    user = User(
        email=f"test_{uuid4().hex[:8]}@example.com",
        normalized_email=f"test_{uuid4().hex[:8]}@example.com",
        password_hash="hashed",
        role="user",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def create_learning_track(db: Session, user_id=None) -> LearningTrack:
    lang = db.query(Language).filter(Language.code == "en").first()
    if not lang:
        lang = Language(code="en", name="English")
        db.add(lang)
        db.commit()
        db.refresh(lang)
    track = db.query(LearningTrack).filter(LearningTrack.code == "en-default").first()
    if not track:
        track = LearningTrack(
            language_id=lang.id,
            code="en-default",
            name="General English",
            level_framework="CEFR",
        )
        db.add(track)
        db.commit()
        db.refresh(track)
    return track

def create_vocab(db: Session, user_id, track_id, word, status="new", next_review=None):
    vocab = Vocabulary(
        user_id=user_id,
        learning_track_id=track_id,
        word=word,
        normalized_word=word.lower(),
        ipa=None,
        part_of_speech="noun",
        meaning="meaning of " + word,
        translation="translation of " + word,
        translation_language_code="vi",
        example_sentences=[],
        level_code="A1",
        topic=None,
        learning_status=status,
        review_count=0,
        correct_count=0,
        incorrect_count=0,
        last_reviewed_at=None,
        next_review_at=next_review,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(vocab)
    db.commit()
    db.refresh(vocab)
    return vocab

def test_registry_contains_expected_tools():
    assert "get_learning_stats" in TOOL_REGISTRY
    assert "get_due_vocabulary" in TOOL_REGISTRY
    assert len(TOOL_REGISTRY) == 2

def test_execute_get_learning_stats(session_factory):
    session = session_factory()
    user = create_user(session)
    track = create_learning_track(session, user.id)
    for i in range(3):
        create_vocab(session, user.id, track.id, f"word{i}")
    result = execute_tool("get_learning_stats", {}, session, user.id)
    expected_keys = {
        "total_vocabulary",
        "new_words",
        "learning_words",
        "review_words",
        "mastered_words",
        "words_due_for_review",
        "exercises_completed",
        "correct_exercise_attempts",
        "incorrect_exercise_attempts",
        "exercise_accuracy",
        "current_streak",
        "longest_streak",
        "recent_active_dates",
        "recent_vocabulary",
    }
    assert set(result.keys()) == expected_keys
    for item in result["recent_vocabulary"]:
        assert set(item.keys()) == {"id", "word", "meaning", "translation", "created_at"}
        assert isinstance(item["id"], str)
        assert isinstance(item["created_at"], str)

def test_execute_get_due_vocabulary(session_factory):
    session = session_factory()
    user = create_user(session)
    track = create_learning_track(session, user.id)
    now = datetime.now(timezone.utc)
    create_vocab(session, user.id, track.id, "dueword", status="learning", next_review=now - timedelta(hours=1))
    create_vocab(session, user.id, track.id, "laterword", status="learning", next_review=now + timedelta(days=1))
    result = execute_tool("get_due_vocabulary", {"limit": 10}, session, user.id)
    assert set(result.keys()) == {"items", "total", "limit"}
    assert len(result["items"]) == 1
    item = result["items"][0]
    assert item["word"] == "dueword"
    assert isinstance(item["id"], str)
    assert isinstance(item["next_review_at"], str) or item["next_review_at"] is None
    assert isinstance(item["last_reviewed_at"], str) or item["last_reviewed_at"] is None

def test_tool_not_found(session_factory):
    session = session_factory()
    user = create_user(session)
    with pytest.raises(ToolNotFoundError):
        execute_tool("nonexistent_tool", {}, session, user.id)

def test_tool_validation_error(session_factory):
    session = session_factory()
    user = create_user(session)
    with pytest.raises(ToolValidationError):
        execute_tool("get_due_vocabulary", {"limit": 10, "extra": "nope"}, session, user.id)
    with pytest.raises(ToolValidationError):
        execute_tool("get_due_vocabulary", {"limit": 0}, session, user.id)

def test_cross_user_isolation(session_factory):
    session = session_factory()
    user_a = create_user(session)
    user_b = create_user(session)
    track_a = create_learning_track(session, user_a.id)
    track_b = create_learning_track(session, user_b.id)
    now = datetime.now(timezone.utc)
    create_vocab(session, user_a.id, track_a.id, "a_word", status="learning", next_review=now - timedelta(hours=1))
    create_vocab(session, user_b.id, track_b.id, "b_word", status="learning", next_review=now - timedelta(hours=1))
    result_a = execute_tool("get_due_vocabulary", {"limit": 10}, session, user_a.id)
    assert len(result_a["items"]) == 1
    assert result_a["items"][0]["word"] == "a_word"
    result_b = execute_tool("get_due_vocabulary", {"limit": 10}, session, user_b.id)
    assert len(result_b["items"]) == 1
    assert result_b["items"][0]["word"] == "b_word"
