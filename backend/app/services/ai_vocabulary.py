from __future__ import annotations

import inspect
import unicodedata
import uuid

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.ai.provider import VocabularyAIProvider
from app.learning_levels import get_level_codes, is_valid_level
from app.models.language import Language
from app.models.learning_track import LearningTrack
from app.schemas.ai_vocabulary import VocabularyCandidate


class InvalidAIVocabularyResponseError(Exception):
    pass


class AIVocabularyTrackUnavailableError(Exception):
    pass


def _normalized(value: str) -> str:
    return unicodedata.normalize("NFKC", value.strip()).casefold()


def generate_vocabulary_candidate(
    db: Session,
    provider: VocabularyAIProvider,
    word: str,
    part_of_speech: str,
    translation: str,
    learning_track_id: uuid.UUID | None = None,
) -> VocabularyCandidate:
    if learning_track_id is None:
        level_framework = "CEFR"
        learning_context = {
            "language_code": "en",
            "language_name": "English",
            "level_framework": level_framework,
            "valid_levels": list(get_level_codes(level_framework)),
            "translation_language": "Vietnamese",
        }
    else:
        track = db.scalar(
            select(LearningTrack)
            .join(LearningTrack.language)
            .options(joinedload(LearningTrack.language))
            .where(
                LearningTrack.id == learning_track_id,
                LearningTrack.is_active.is_(True),
                Language.is_active.is_(True),
            )
        )
        if track is None:
            raise AIVocabularyTrackUnavailableError
        level_framework = track.level_framework
        learning_context = {
            "language_code": track.language.code,
            "language_name": track.language.name,
            "level_framework": level_framework,
            "valid_levels": list(get_level_codes(level_framework)),
            "translation_language": "Vietnamese",
        }
    generate = provider.generate_vocabulary
    if "learning_context" in inspect.signature(generate).parameters:
        raw_candidate = generate(
            word=word,
            part_of_speech=part_of_speech,
            translation=translation,
            learning_context=learning_context,
        )
    else:
        raw_candidate = generate(
            word=word,
            part_of_speech=part_of_speech,
            translation=translation,
        )
    try:
        candidate = VocabularyCandidate.model_validate(raw_candidate)
    except (ValidationError, TypeError, ValueError) as exc:
        raise InvalidAIVocabularyResponseError from exc
    if not is_valid_level(level_framework, candidate.cefr_level):
        raise InvalidAIVocabularyResponseError

    # Enforce strictly that user inputs are never overwritten by AI
    return candidate.model_copy(
        update={
            "word": word.strip(),
            "part_of_speech": part_of_speech.strip().lower(),
            "translation": translation.strip(),
            "topic": candidate.topic if candidate.topic and candidate.topic.strip() else "Khác",
            "cefr_level": candidate.cefr_level.strip().upper(),
        }
    )

