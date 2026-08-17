from __future__ import annotations

import unicodedata
import uuid

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.ai.provider import ExerciseAIProvider
from app.models.exercise import Exercise
from app.models.vocabulary import Vocabulary
from app.schemas.ai_exercise import (
    AIExerciseGenerationRequest,
    AIFillInBlankBatch,
    AIMultipleChoiceBatch,
)


class VocabularySelectionNotFoundError(Exception):
    pass


class VocabularyTrackMismatchError(Exception):
    pass


class InsufficientVocabularyError(Exception):
    pass


class InvalidAIExerciseResponseError(Exception):
    pass


class AIExercisePersistenceError(Exception):
    pass


AI_CONTEXT_MEANING_MAX_CHARS = 1000
AI_CONTEXT_EXAMPLE_MAX_CHARS = 300
AI_CONTEXT_EXAMPLE_LIMIT = 2


def _normalized(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value.strip())
    return " ".join(normalized.split()).casefold()


def _load_owned_vocabularies(
    db: Session,
    user_id: uuid.UUID,
    vocabulary_ids: list[uuid.UUID],
) -> list[Vocabulary]:
    rows = list(
        db.scalars(
            select(Vocabulary).where(
                Vocabulary.user_id == user_id,
                Vocabulary.id.in_(vocabulary_ids),
            )
        )
    )
    by_id = {item.id: item for item in rows}
    if len(by_id) != len(vocabulary_ids):
        raise VocabularySelectionNotFoundError
    return [by_id[vocabulary_id] for vocabulary_id in vocabulary_ids]


def _validate_selection(
    vocabularies: list[Vocabulary], exercise_type: str
) -> uuid.UUID:
    track_ids = {item.learning_track_id for item in vocabularies}
    if len(track_ids) != 1:
        raise VocabularyTrackMismatchError

    if exercise_type == "multiple_choice":
        distinct_words = {_normalized(item.word) for item in vocabularies}
        if len(distinct_words) < 4:
            raise InsufficientVocabularyError
    return next(iter(track_ids))


def _provider_context(vocabularies: list[Vocabulary]) -> list[dict[str, object]]:
    return [
        {
            "id": str(item.id),
            "word": item.word,
            "part_of_speech": item.part_of_speech,
            "meaning": item.meaning[:AI_CONTEXT_MEANING_MAX_CHARS],
            "example_sentences": [
                example[:AI_CONTEXT_EXAMPLE_MAX_CHARS]
                for example in item.example_sentences[:AI_CONTEXT_EXAMPLE_LIMIT]
            ],
        }
        for item in vocabularies
    ]


def _parse_batch(raw: object, exercise_type: str):
    try:
        if exercise_type == "multiple_choice":
            return AIMultipleChoiceBatch.model_validate(raw)
        return AIFillInBlankBatch.model_validate(raw)
    except (ValidationError, TypeError, ValueError) as exc:
        raise InvalidAIExerciseResponseError from exc


def _validate_candidate_semantics(
    batch: AIMultipleChoiceBatch | AIFillInBlankBatch,
    *,
    exercise_type: str,
    requested_count: int,
    selected_by_id: dict[uuid.UUID, Vocabulary],
) -> None:
    if len(batch.exercises) != requested_count:
        raise InvalidAIExerciseResponseError

    selected_ids = set(selected_by_id)
    selected_words = {_normalized(item.word) for item in selected_by_id.values()}

    for candidate in batch.exercises:
        source_ids = set(candidate.source_vocabulary_ids)
        if not source_ids or not source_ids.issubset(selected_ids):
            raise InvalidAIExerciseResponseError
        source_words = {
            _normalized(selected_by_id[source_id].word) for source_id in source_ids
        }

        if exercise_type == "multiple_choice":
            option_words = {_normalized(option.text) for option in candidate.options}
            if not option_words.issubset(selected_words):
                raise InvalidAIExerciseResponseError
            correct_option = next(
                (
                    option
                    for option in candidate.options
                    if option.id == candidate.correct_answer
                ),
                None,
            )
            if (
                correct_option is None
                or _normalized(correct_option.text) not in source_words
            ):
                raise InvalidAIExerciseResponseError
        elif _normalized(candidate.correct_answer) not in source_words:
            raise InvalidAIExerciseResponseError


def generate_and_store_exercises(
    db: Session,
    provider: ExerciseAIProvider,
    user_id: uuid.UUID,
    payload: AIExerciseGenerationRequest,
) -> list[Exercise]:
    vocabularies = _load_owned_vocabularies(db, user_id, payload.vocabulary_ids)
    learning_track_id = _validate_selection(vocabularies, payload.exercise_type)
    context = _provider_context(vocabularies)

    # End the read transaction before waiting on the external provider.
    db.rollback()
    raw = provider.generate_exercises(context, payload.exercise_type, payload.count)
    batch = _parse_batch(raw, payload.exercise_type)

    # Re-check ownership after the provider call so stale/deleted records cannot be used.
    vocabularies = _load_owned_vocabularies(db, user_id, payload.vocabulary_ids)
    if _validate_selection(vocabularies, payload.exercise_type) != learning_track_id:
        raise VocabularyTrackMismatchError
    selected_by_id = {item.id: item for item in vocabularies}
    _validate_candidate_semantics(
        batch,
        exercise_type=payload.exercise_type,
        requested_count=payload.count,
        selected_by_id=selected_by_id,
    )

    exercises: list[Exercise] = []
    for candidate in batch.exercises:
        if payload.exercise_type == "multiple_choice":
            options = [option.model_dump() for option in candidate.options]
            accepted_answers: list[str] = []
        else:
            options = None
            accepted_answers = candidate.accepted_answers

        exercise = Exercise(
            user_id=user_id,
            learning_track_id=learning_track_id,
            exercise_type=payload.exercise_type,
            prompt=candidate.prompt,
            options=options,
            correct_answer=candidate.correct_answer,
            accepted_answers=accepted_answers,
            explanation=candidate.explanation,
            source="ai",
            vocabularies=[selected_by_id[item_id] for item_id in candidate.source_vocabulary_ids],
        )
        exercises.append(exercise)

    try:
        db.add_all(exercises)
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise AIExercisePersistenceError from exc
    return exercises
