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
) -> VocabularyCandidate:
    raw_candidate = provider.generate_vocabulary(word)
    try:
        candidate = VocabularyCandidate.model_validate(raw_candidate)
    except (ValidationError, TypeError, ValueError) as exc:
        raise InvalidAIVocabularyResponseError from exc

    if _normalized(candidate.word) != _normalized(word):
        raise InvalidAIVocabularyResponseError
    return candidate

