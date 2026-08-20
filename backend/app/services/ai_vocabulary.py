from __future__ import annotations

import unicodedata

from pydantic import ValidationError

from app.ai.provider import VocabularyAIProvider
from app.schemas.ai_vocabulary import VocabularyCandidate


class InvalidAIVocabularyResponseError(Exception):
    pass


def _normalized(value: str) -> str:
    return unicodedata.normalize("NFKC", value.strip()).casefold()


def generate_vocabulary_candidate(
    provider: VocabularyAIProvider,
    word: str,
    part_of_speech: str,
    translation: str,
) -> VocabularyCandidate:
    raw_candidate = provider.generate_vocabulary(
        word=word,
        part_of_speech=part_of_speech,
        translation=translation,
    )
    try:
        candidate = VocabularyCandidate.model_validate(raw_candidate)
    except (ValidationError, TypeError, ValueError) as exc:
        raise InvalidAIVocabularyResponseError from exc

    # Enforce strictly that user inputs are never overwritten by AI
    return candidate.model_copy(
        update={
            "word": word.strip(),
            "part_of_speech": part_of_speech.strip().lower(),
            "translation": translation.strip(),
            "topic": candidate.topic if candidate.topic and candidate.topic.strip() else "Khác",
        }
    )

