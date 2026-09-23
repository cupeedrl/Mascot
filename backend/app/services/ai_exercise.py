from __future__ import annotations

import json
import random
import logging
import unicodedata
import uuid
from datetime import datetime, timedelta, timezone

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.ai.provider import (
    AIProviderRequestError,
    AIProviderResponseError,
    ExerciseAIProvider,
)
from app.models.exercise import Exercise
from app.models.learning_track import LearningTrack
from app.models.vocabulary import Vocabulary
from app.schemas.ai_exercise import (
    AIExerciseGenerationRequest,
    AIFillInBlankBatch,
    AIMultipleChoiceBatch,
    CLOZE_BLANK_COUNT,
)
from app.services.ai_guard import ai_guard, AICooldownError, AIDuplicateRequestError
from app.services.normalization import normalize_topic


logger = logging.getLogger(__name__)

# One retry: enough for a resampled draft, still a bounded number of AI calls.
GENERATION_ATTEMPTS = 2


class VocabularySelectionNotFoundError(Exception):
    pass


class VocabularyTrackMismatchError(Exception):
    pass


class InsufficientVocabularyError(Exception):
    pass


class VocabularySourceEmptyError(Exception):
    pass


class InvalidAIExerciseResponseError(Exception):
    """Raised only after untrusted AI output fails a safe backend check."""


class AIExercisePersistenceError(Exception):
    pass


AI_CONTEXT_MEANING_MAX_CHARS = 1000
AI_CONTEXT_EXAMPLE_MAX_CHARS = 300
AI_CONTEXT_EXAMPLE_LIMIT = 1
RECENT_SOURCE_LIMIT = 20
AI_SOURCE_CONTEXT_LIMIT = 20
# One passage only needs a handful of candidate words, and a short prompt keeps
# the whole request inside a small provider tokens-per-minute allowance.
AI_CLOZE_SOURCE_CONTEXT_LIMIT = 10
AI_CLOZE_MEANING_MAX_CHARS = 160


def _normalized(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value.strip())
    return " ".join(normalized.split()).casefold()


def get_active_unfinished_exercises(
    db: Session,
    user_id: uuid.UUID,
    learning_track_id: uuid.UUID | None = None,
) -> list[Exercise]:
    """Return active unfinished AI exercises for the user, if any."""
    conditions = [Exercise.user_id == user_id, Exercise.source == "ai"]
    if learning_track_id is not None:
        conditions.append(Exercise.learning_track_id == learning_track_id)
    latest_exercise = db.scalar(
        select(Exercise)
        .where(*conditions)
        .order_by(Exercise.created_at.desc(), Exercise.id.desc())
        .limit(1)
    )
    if latest_exercise is None or latest_exercise.created_at is None:
        return []

    time_min = latest_exercise.created_at - timedelta(seconds=10)
    time_max = latest_exercise.created_at + timedelta(seconds=10)

    statement = (
        select(Exercise)
        .options(selectinload(Exercise.vocabularies), selectinload(Exercise.attempts))
        .where(
            Exercise.user_id == user_id,
            Exercise.source == "ai",
            *(
                [Exercise.learning_track_id == learning_track_id]
                if learning_track_id is not None
                else []
            ),
            Exercise.created_at >= time_min,
            Exercise.created_at <= time_max,
        )
        .order_by(Exercise.created_at.asc(), Exercise.id.asc())
    )
    batch = list(db.scalars(statement))
    if not batch:
        return []

    # If any exercise in this batch has not been attempted, the session is unfinished
    unattempted = [item for item in batch if len(item.attempts) == 0]
    if unattempted:
        return batch
    return []


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
    if payload.learning_track_id is not None:
        statement = statement.where(
            Vocabulary.learning_track_id == payload.learning_track_id
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
    limit: int = AI_SOURCE_CONTEXT_LIMIT,
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
        if len(selected) == limit:
            return selected
    return (selected + deferred)[:limit]


def _validate_selection(
    vocabularies: list[Vocabulary], exercise_type: str
) -> uuid.UUID:
    track_ids = {item.learning_track_id for item in vocabularies}
    if len(track_ids) != 1:
        raise VocabularyTrackMismatchError

    distinct_words = {_normalized(item.word) for item in vocabularies}
    if exercise_type == "multiple_choice":
        if len(distinct_words) < 4:
            raise InsufficientVocabularyError
    elif len(distinct_words) < CLOZE_BLANK_COUNT:
        # One passage needs a different target word for each blank.
        raise InsufficientVocabularyError
    return next(iter(track_ids))


def _provider_context(
    vocabularies: list[Vocabulary],
    track: LearningTrack | None = None,
    *,
    compact: bool = False,
) -> list[dict[str, object]]:
    context = []
    meaning_limit = (
        AI_CLOZE_MEANING_MAX_CHARS if compact else AI_CONTEXT_MEANING_MAX_CHARS
    )
    example_limit = 0 if compact else AI_CONTEXT_EXAMPLE_LIMIT
    for item in vocabularies:
        record: dict[str, object] = {
            "id": str(item.id),
            "word": item.word,
            "part_of_speech": item.part_of_speech,
            "meaning": item.meaning[:meaning_limit],
            "cefr_level": item.level_code,
            "example_sentences": [
                example[:AI_CONTEXT_EXAMPLE_MAX_CHARS]
                for example in item.example_sentences[:example_limit]
            ],
        }
        if track is not None:
            record.update(
                {
                    "level_code": item.level_code,
                    "target_language": track.language.name,
                    "target_language_code": track.language.code,
                    "level_framework": track.level_framework,
                    "translation_language": "Vietnamese",
                }
            )
        context.append(record)
    return context


def _parse_batch(raw: object, exercise_type: str):
    try:
        if exercise_type == "multiple_choice":
            return AIMultipleChoiceBatch.model_validate(raw)
        return AIFillInBlankBatch.model_validate(raw)
    except (ValidationError, TypeError, ValueError) as exc:
        logger.warning(
            "AI exercise batch schema validation failed (type=%s, errors=%s)",
            exercise_type,
            len(exc.errors()) if isinstance(exc, ValidationError) else "unavailable",
        )
        raise InvalidAIExerciseResponseError("schema validation failed") from exc


def _validate_candidate_semantics(
    batch: AIMultipleChoiceBatch | AIFillInBlankBatch,
    *,
    exercise_type: str,
    requested_count: int,
    selected_by_id: dict[uuid.UUID, Vocabulary],
) -> None:
    if len(batch.exercises) != requested_count:
        raise InvalidAIExerciseResponseError("unexpected exercise count")

    prompts = [
        _normalized(
            candidate.prompt
            if exercise_type == "multiple_choice"
            else candidate.passage
        )
        for candidate in batch.exercises
    ]
    if len(set(prompts)) != len(prompts):
        raise InvalidAIExerciseResponseError("duplicate generated prompt")

    if exercise_type == "fill_in_blank":
        for candidate in batch.exercises:
            option_texts = [
                _normalized(option.text)
                for blank in candidate.blanks
                for option in blank.options
            ]
            if len(set(option_texts)) != len(option_texts):
                raise InvalidAIExerciseResponseError(
                    "cloze options repeat across blanks"
                )

    selected_ids = set(selected_by_id)
    for candidate in batch.exercises:
        if exercise_type == "multiple_choice":
            if candidate.target_vocabulary_id not in selected_ids:
                raise InvalidAIExerciseResponseError("multiple-choice target is outside source pool")
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
                raise InvalidAIExerciseResponseError("multiple-choice target does not match correct option")
        else:
            for blank in candidate.blanks:
                if blank.target_vocabulary_id not in selected_ids:
                    raise InvalidAIExerciseResponseError("cloze target is outside source pool")
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
                    raise InvalidAIExerciseResponseError("cloze target does not match correct option")


def _repair_cloze_option_duplicates(
    candidate,
    vocabularies: list[Vocabulary],
) -> None:
    """Make every option in a passage unique, in place.

    A learner sees all CLOZE_BLANK_COUNT x 4 choices at once, so a word must not
    appear twice. Providers slip on this, and swapping the repeat for an unused
    word from the learner's own pool is cheaper - and keeps the level right -
    than asking for a whole new passage. Correct answers are reserved first so a
    distractor never squats on another blank's answer.
    """

    answers: dict[int, str] = {}
    for blank in candidate.blanks:
        correct = next(
            (option for option in blank.options if option.id == blank.correct_answer),
            None,
        )
        if correct is None:
            raise InvalidAIExerciseResponseError("cloze blank has no correct option")
        answers[blank.number] = _normalized(correct.text)

    if len(set(answers.values())) != len(answers):
        raise InvalidAIExerciseResponseError("cloze answers repeat a word")

    used = set(answers.values())
    spare = [item for item in vocabularies if _normalized(item.word) not in used]

    for blank in candidate.blanks:
        for option in blank.options:
            if option.id == blank.correct_answer:
                continue
            normalized = _normalized(option.text)
            if normalized not in used:
                used.add(normalized)
                continue
            replacement = next(
                (item for item in spare if _normalized(item.word) not in used),
                None,
            )
            if replacement is None:
                raise InvalidAIExerciseResponseError(
                    "not enough distinct words for one passage"
                )
            option.text = replacement.word
            used.add(_normalized(replacement.word))


def _shuffled_options(candidate) -> tuple[list[dict[str, object]], str]:
    """Spread the answer over A-D.

    Providers park the correct option at A almost every time, which turns the
    exercise into a guessing game, so the texts are dealt out again here and the
    answer id follows the text it belongs to.
    """

    ids = [option.id for option in candidate.options]
    texts = [option.text for option in candidate.options]
    correct_text = next(
        option.text
        for option in candidate.options
        if option.id == candidate.correct_answer
    )
    random.shuffle(texts)
    options = [
        {"id": option_id, "text": text} for option_id, text in zip(ids, texts)
    ]
    correct_answer = next(
        option["id"] for option in options if option["text"] == correct_text
    )
    return options, str(correct_answer)


def generate_and_store_exercises(
    db: Session,
    provider: ExerciseAIProvider,
    user_id: uuid.UUID,
    payload: AIExerciseGenerationRequest,
) -> tuple[list[Exercise], bool]:
    """Generate and store AI exercises.

    Returns (exercises, resumed). If an unfinished active session exists, it is
    returned directly without calling AI.
    """
    # 1. Check for active unfinished practice session
    active_exercises = get_active_unfinished_exercises(
        db, user_id, payload.learning_track_id
    )
    if active_exercises:
        logger.info(
            "Resuming existing unfinished practice session (user_id=%s, count=%s)",
            user_id,
            len(active_exercises),
        )
        return active_exercises, True

    # 2. Acquire generation guard (rate limit & in-flight deduplication)
    payload_dict = {
        "source_mode": payload.source_mode,
        "topic": payload.topic,
        "vocabulary_ids": [str(v) for v in payload.vocabulary_ids],
        "exercise_type": payload.exercise_type,
        "count": payload.count,
        "learning_track_id": str(payload.learning_track_id or "all"),
    }
    fingerprint = ai_guard.compute_fingerprint(user_id, "exercise_generation", payload_dict)
    ai_guard.check_and_acquire(user_id, "exercise_generation", fingerprint, cooldown_seconds=30)

    try:
        source_vocabularies = _resolve_vocabulary_source(db, user_id, payload)
        learning_track_id = _validate_selection(source_vocabularies, payload.exercise_type)
        if (
            payload.learning_track_id is not None
            and learning_track_id != payload.learning_track_id
        ):
            raise VocabularyTrackMismatchError
        track = db.scalar(
            select(LearningTrack)
            .options(selectinload(LearningTrack.language))
            .where(LearningTrack.id == learning_track_id)
        )
        if track is None:
            raise VocabularyTrackMismatchError
        is_cloze = payload.exercise_type == "fill_in_blank"
        provider_vocabularies = _select_provider_vocabularies(
            source_vocabularies,
            AI_CLOZE_SOURCE_CONTEXT_LIMIT if is_cloze else AI_SOURCE_CONTEXT_LIMIT,
        )
        provider_vocabulary_ids = [item.id for item in provider_vocabularies]
        context = _provider_context(provider_vocabularies, track, compact=is_cloze)

        # End the read transaction before waiting on the external provider.
        db.rollback()
        requested_count = 1 if payload.exercise_type == "fill_in_blank" else payload.count
        last_error: Exception | None = None
        batch = None
        vocabularies: list[Vocabulary] = []
        selected_by_id: dict[uuid.UUID, Vocabulary] = {}
        for attempt in range(1, GENERATION_ATTEMPTS + 1):
            try:
                raw = provider.generate_exercises(
                    context, payload.exercise_type, requested_count
                )
                candidate_batch = _parse_batch(raw, payload.exercise_type)

                # Re-check ownership after the provider call so stale or deleted
                # records cannot be used.
                vocabularies = _load_owned_vocabularies(
                    db, user_id, provider_vocabulary_ids
                )
                if (
                    _validate_selection(vocabularies, payload.exercise_type)
                    != learning_track_id
                ):
                    raise VocabularyTrackMismatchError
                selected_by_id = {item.id: item for item in vocabularies}
                if payload.exercise_type == "fill_in_blank":
                    for candidate in candidate_batch.exercises:
                        _repair_cloze_option_duplicates(candidate, vocabularies)
                _validate_candidate_semantics(
                    candidate_batch,
                    exercise_type=payload.exercise_type,
                    requested_count=requested_count,
                    selected_by_id=selected_by_id,
                )
            except (
                AIProviderResponseError,
                AIProviderRequestError,
                InvalidAIExerciseResponseError,
            ) as exc:
                last_error = exc
                logger.warning(
                    "AI exercise draft rejected (type=%s, attempt=%s/%s, reason=%s)",
                    payload.exercise_type,
                    attempt,
                    GENERATION_ATTEMPTS,
                    type(exc).__name__,
                )
                db.rollback()
                continue
            batch = candidate_batch
            break

        if batch is None:
            assert last_error is not None
            raise last_error

        now = datetime.now(timezone.utc)
        exercises: list[Exercise] = []
        for candidate in batch.exercises:
            if payload.exercise_type == "multiple_choice":
                options, candidate_correct = _shuffled_options(candidate)
                accepted_answers: list[object] = []
                correct_answer = candidate_correct
                explanation = candidate.explanation
                word_to_vocabulary = {
                    _normalized(item.word): item for item in vocabularies
                }
                linked_vocabularies = list(
                    {
                        item.id: item
                        for option in candidate.options
                        if (item := word_to_vocabulary.get(_normalized(option.text)))
                        is not None
                    }.values()
                )
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
                created_at=now,
                updated_at=now,
                vocabularies=linked_vocabularies,
            )
            exercises.append(exercise)

        try:
            db.add_all(exercises)
            db.commit()
        except SQLAlchemyError as exc:
            db.rollback()
            logger.exception(
                "Storing generated exercises failed (user_id=%s, type=%s, count=%s)",
                user_id,
                payload.exercise_type,
                len(exercises),
            )
            raise AIExercisePersistenceError from exc

        ai_guard.release(user_id, "exercise_generation", fingerprint, mark_success=True)
        return exercises, False

    except Exception:
        ai_guard.release(user_id, "exercise_generation", fingerprint, mark_success=False)
        raise
