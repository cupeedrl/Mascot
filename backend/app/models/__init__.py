"""SQLAlchemy persistence models."""

from app.models.ai_usage_log import AIUsageLog
from app.models.ai_conversation import AIConversation, AIMessage
from app.models.exercise import Exercise, exercise_vocabularies
from app.models.exercise_attempt import ExerciseAttempt
from app.models.hsk_catalog import (
    CatalogRelease,
    CatalogSourceEntry,
    CatalogSourceEntryLevel,
    CatalogSourceMapping,
    LexicalEntry,
    LexicalPronunciation,
    LexicalSense,
    LexicalSenseExample,
    LexicalSensePos,
    LexicalSensePronunciation,
    LexicalVariant,
)
from app.models.language import Language
from app.models.learning_track import LearningTrack
from app.models.password_reset_token import PasswordResetToken
from app.models.user import User
from app.models.user_learning_preference import UserLearningPreference
from app.models.vocabulary import Vocabulary
from app.models.vocabulary_entry import VocabularyEntry
from app.models.vocabulary_set import VocabularySet

__all__ = [
    "AIUsageLog",
    "AIConversation",
    "AIMessage",
    "CatalogRelease",
    "CatalogSourceEntry",
    "CatalogSourceEntryLevel",
    "CatalogSourceMapping",
    "Exercise",
    "ExerciseAttempt",
    "Language",
    "LearningTrack",
    "LexicalEntry",
    "LexicalPronunciation",
    "LexicalSense",
    "LexicalSenseExample",
    "LexicalSensePos",
    "LexicalSensePronunciation",
    "LexicalVariant",
    "PasswordResetToken",
    "User",
    "UserLearningPreference",
    "Vocabulary",
    "VocabularyEntry",
    "VocabularySet",
    "exercise_vocabularies",
]

