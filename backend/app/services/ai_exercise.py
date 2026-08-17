from __future__ import annotations

import json
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
from app.services.normalization import normalize_topic


class VocabularySelectionNotFoundError(Exception):
    pass


class VocabularyTrackMismatchError(Exception):
    pass


class InsufficientVocabularyError(Exception):
    pass


class VocabularySourceEmptyError(Exception):
    pass


class InvalidAIExerciseResponseError(Exception):
    pass


class AIExercisePersistenceError(Exception):
    pass


AI_CONTEXT_MEANING_MAX_CHARS = 1000
AI_CONTEXT_EXAMPLE_MAX_CHARS = 300
AI_CONTEXT_EXAMPLE_LIMIT = 1
RECENT_SOURCE_LIMIT = 20
AI_SOURCE_CONTEXT_LIMIT = 20


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
                Vocabulary.learning_status != "mastered",
            )
        )
    )
    by_id = {item.id: item for item in rows}
    if len(by_id) != len(vocabulary_ids):
        raise VocabularySelectionNotFoundError
    return [by_id[vocabulary_id] for vocabulary_id in vocabulary_ids]


def _resolve_vocabulary_source(
    db: Session,
    user_id: uuid.UUID,
    payload: AIExerciseGenerationRequest,
) -> list[Vocabulary]:
    if payload.source_mode == "custom":
        return _load_owned_vocabularies(db, user_id, payload.vocabulary_ids)

    statement = (
        select(Vocabulary)
        .where(
            Vocabulary.user_id == user_id,
            Vocabulary.learning_status != "mastered",
        )
        .order_by(Vocabulary.created_at.desc(), Vocabulary.id.desc())
    )
    if payload.source_mode == "recent":
        vocabularies = list(db.scalars(statement.limit(RECENT_SOURCE_LIMIT)))
    else:
        requested_topic = normalize_topic(payload.topic or "")
        vocabularies = [
            item
            for item in db.scalars(statement.where(Vocabulary.topic.is_not(None)))
            if normalize_topic(item.topic or "") == requested_topic
        ]

    if not vocabularies:
        raise VocabularySourceEmptyError
    return vocabularies


def _select_provider_vocabularies(
    vocabularies: list[Vocabulary],
) -> list[Vocabulary]:
    selected: list[Vocabulary] = []
    seen_words: set[str] = set()
    deferred: list[Vocabulary] = []
    for item in vocabularies:
        normalized_word = _normalized(item.word)
        if normalized_word in seen_words:
            deferred.append(item)
            continue
        selected.append(item)
        seen_words.add(normalized_word)
        if len(selected) == AI_SOURCE_CONTEXT_LIMIT:
            return selected
    return (selected + deferred)[:AI_SOURCE_CONTEXT_LIMIT]


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
            "cefr_level": item.level_code,
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

    prompts = [
        _normalized(
            candidate.prompt
            if exercise_type == "multiple_choice"
            else candidate.passage
        )
        for candidate in batch.exercises
    ]
    if len(set(prompts)) != len(prompts):
        raise InvalidAIExerciseResponseError

    selected_ids = set(selected_by_id)
    selected_words = {_normalized(item.word) for item in selected_by_id.values()}

    for candidate in batch.exercises:
        if exercise_type == "multiple_choice":
            if candidate.target_vocabulary_id not in selected_ids:
                raise InvalidAIExerciseResponseError
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
                or _normalized(correct_option.text)
                != _normalized(
                    selected_by_id[candidate.target_vocabulary_id].word
                )
            ):
                raise InvalidAIExerciseResponseError
        else:
            for blank in candidate.blanks:
                if blank.target_vocabulary_id not in selected_ids:
                    raise InvalidAIExerciseResponseError
                correct_option = next(
                    (
                        option
                        for option in blank.options
                        if option.id == blank.correct_answer
                    ),
                    None,
                )
                if (
                    correct_option is None
                    or _normalized(correct_option.text)
                    != _normalized(
                        selected_by_id[blank.target_vocabulary_id].word
                    )
                ):
                    raise InvalidAIExerciseResponseError


def generate_and_store_exercises(
    db: Session,
    provider: ExerciseAIProvider,
    user_id: uuid.UUID,
    payload: AIExerciseGenerationRequest,
) -> list[Exercise]:
    source_vocabularies = _resolve_vocabulary_source(db, user_id, payload)
    learning_track_id = _validate_selection(source_vocabularies, payload.exercise_type)
    provider_vocabularies = _select_provider_vocabularies(source_vocabularies)
    provider_vocabulary_ids = [item.id for item in provider_vocabularies]
    context = _provider_context(provider_vocabularies)

    # End the read transaction before waiting on the external provider.
    db.rollback()
    requested_count = 1 if payload.exercise_type == "fill_in_blank" else payload.count
    raw = provider.generate_exercises(context, payload.exercise_type, requested_count)
    batch = _parse_batch(raw, payload.exercise_type)

    # Re-check ownership after the provider call so stale/deleted records cannot be used.
    vocabularies = _load_owned_vocabularies(db, user_id, provider_vocabulary_ids)
    if _validate_selection(vocabularies, payload.exercise_type) != learning_track_id:
        raise VocabularyTrackMismatchError
    selected_by_id = {item.id: item for item in vocabularies}
    _validate_candidate_semantics(
        batch,
        exercise_type=payload.exercise_type,
        requested_count=requested_count,
        selected_by_id=selected_by_id,
    )

    exercises: list[Exercise] = []
    for candidate in batch.exercises:
        if payload.exercise_type == "multiple_choice":
            options = [option.model_dump() for option in candidate.options]
            accepted_answers: list[object] = []
            correct_answer = candidate.correct_answer
            explanation = candidate.explanation
            word_to_vocabulary = {
                _normalized(item.word): item for item in vocabularies
            }
            linked_vocabularies = [
                word_to_vocabulary[_normalized(option.text)]
                for option in candidate.options
            ]
            if candidate.target_vocabulary_id not in {
                item.id for item in linked_vocabularies
            }:
                linked_vocabularies.append(
                    selected_by_id[candidate.target_vocabulary_id]
                )
            prompt = candidate.prompt
        else:
            options = [
                {
                    "number": blank.number,
                    "options": [option.model_dump() for option in blank.options],
                }
                for blank in candidate.blanks
            ]
            answer_key = {
                str(blank.number): blank.correct_answer for blank in candidate.blanks
            }
            correct_answer = json.dumps(answer_key, sort_keys=True)
            accepted_answers = []
            explanation = json.dumps(
                {
                    str(blank.number): blank.explanation
                    for blank in candidate.blanks
                },
                ensure_ascii=False,
                sort_keys=True,
            )
            linked_vocabularies = list(
                {
                    blank.target_vocabulary_id: selected_by_id[
                        blank.target_vocabulary_id
                    ]
                    for blank in candidate.blanks
                }.values()
            )
            prompt = f"{candidate.title}\n\n{candidate.passage}"

        exercise = Exercise(
            user_id=user_id,
            learning_track_id=learning_track_id,
            exercise_type=payload.exercise_type,
            prompt=prompt,
            options=options,
            correct_answer=correct_answer,
            accepted_answers=accepted_answers,
            explanation=explanation,
            source="ai",
            vocabularies=linked_vocabularies,
        )
        exercises.append(exercise)

    try:
        db.add_all(exercises)
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise AIExercisePersistenceError from exc
    return exercises
