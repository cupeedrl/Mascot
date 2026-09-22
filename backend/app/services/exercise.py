from __future__ import annotations

import json
import unicodedata
import uuid
from dataclasses import dataclass
from math import ceil

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.exercise import Exercise
from app.models.exercise_attempt import ExerciseAttempt


class ExerciseNotFoundError(Exception):
    pass


class InvalidStoredExerciseError(Exception):
    pass


class InvalidAttemptFormatError(Exception):
    pass


@dataclass(frozen=True)
class ExercisePage:
    items: list[Exercise]
    page: int
    page_size: int
    total: int
    total_pages: int


@dataclass(frozen=True)
class AttemptPage:
    items: list[ExerciseAttempt]
    page: int
    page_size: int
    total: int
    total_pages: int


@dataclass(frozen=True)
class GradedAttempt:
    attempt: ExerciseAttempt
    explanation: str | None
    correct_count: int | None = None
    total: int | None = None
    score_percent: int | None = None
    results: list["BlankGrade"] | None = None


@dataclass(frozen=True)
class BlankGrade:
    number: int
    is_correct: bool
    correct_answer: str
    explanation: str | None


def _normalize_text_answer(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value.strip())
    return " ".join(normalized.split()).casefold()


def _normalize_option_id(value: str) -> str:
    return unicodedata.normalize("NFKC", value.strip()).upper()


def list_owned_exercises(
    db: Session,
    user_id: uuid.UUID,
    *,
    page: int,
    page_size: int,
    exercise_type: str | None = None,
    learning_track_id: uuid.UUID | None = None,
) -> ExercisePage:
    conditions = [Exercise.user_id == user_id]
    if exercise_type is not None:
        conditions.append(Exercise.exercise_type == exercise_type)
    if learning_track_id is not None:
        conditions.append(Exercise.learning_track_id == learning_track_id)

    total = db.scalar(select(func.count()).select_from(Exercise).where(*conditions)) or 0
    statement = (
        select(Exercise)
        .options(selectinload(Exercise.vocabularies))
        .where(*conditions)
        .order_by(Exercise.created_at.asc(), Exercise.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return ExercisePage(
        items=list(db.scalars(statement)),
        page=page,
        page_size=page_size,
        total=total,
        total_pages=ceil(total / page_size) if total else 0,
    )


def get_owned_exercise(
    db: Session, user_id: uuid.UUID, exercise_id: uuid.UUID
) -> Exercise:
    exercise = db.scalar(
        select(Exercise)
        .options(selectinload(Exercise.vocabularies))
        .where(Exercise.id == exercise_id, Exercise.user_id == user_id)
    )
    if exercise is None:
        raise ExerciseNotFoundError
    return exercise


def _grade_multiple_choice(exercise: Exercise, answer: str) -> bool:
    if not exercise.options or not isinstance(exercise.options, list):
        raise InvalidStoredExerciseError
    option_ids = {
        _normalize_option_id(str(option.get("id", "")))
        for option in exercise.options
        if isinstance(option, dict)
    }
    correct_answer = _normalize_option_id(exercise.correct_answer)
    if not correct_answer or correct_answer not in option_ids:
        raise InvalidStoredExerciseError
    return _normalize_option_id(answer) == correct_answer


def _grade_fill_in_blank(exercise: Exercise, answer: str) -> bool:
    valid_answers = [exercise.correct_answer, *exercise.accepted_answers]
    normalized_answers = {
        _normalize_text_answer(candidate)
        for candidate in valid_answers
        if isinstance(candidate, str) and candidate.strip()
    }
    if not normalized_answers:
        raise InvalidStoredExerciseError
    return _normalize_text_answer(answer) in normalized_answers


def _is_passage_cloze(exercise: Exercise) -> bool:
    return (
        exercise.exercise_type == "fill_in_blank"
        and isinstance(exercise.options, list)
        and len(exercise.options) == 4
        and all(
            isinstance(blank, dict)
            and isinstance(blank.get("number"), int)
            and isinstance(blank.get("options"), list)
            for blank in exercise.options
        )
    )


def _passage_answer_key(exercise: Exercise) -> dict[str, str]:
    try:
        raw = json.loads(exercise.correct_answer)
    except (TypeError, json.JSONDecodeError) as exc:
        raise InvalidStoredExerciseError from exc
    if not isinstance(raw, dict) or set(raw) != {"1", "2", "3", "4"}:
        raise InvalidStoredExerciseError
    answer_key = {
        str(key): _normalize_option_id(str(value)) for key, value in raw.items()
    }
    if any(value not in {"A", "B", "C", "D"} for value in answer_key.values()):
        raise InvalidStoredExerciseError

    for index, blank in enumerate(exercise.options or [], start=1):
        if not isinstance(blank, dict) or blank.get("number") != index:
            raise InvalidStoredExerciseError
        options = blank.get("options")
        if not isinstance(options, list) or len(options) != 4:
            raise InvalidStoredExerciseError
        option_ids = {
            _normalize_option_id(str(option.get("id", "")))
            for option in options
            if isinstance(option, dict)
        }
        if option_ids != {"A", "B", "C", "D"} or answer_key[str(index)] not in option_ids:
            raise InvalidStoredExerciseError
    return answer_key


def _passage_explanations(exercise: Exercise) -> dict[str, str | None]:
    if not exercise.explanation:
        return {str(number): None for number in range(1, 5)}
    try:
        raw = json.loads(exercise.explanation)
    except (TypeError, json.JSONDecodeError) as exc:
        raise InvalidStoredExerciseError from exc
    if not isinstance(raw, dict):
        raise InvalidStoredExerciseError
    return {
        str(number): (
            str(raw[str(number)]).strip() if raw.get(str(number)) else None
        )
        for number in range(1, 5)
    }


def _grade_passage_cloze(
    exercise: Exercise, answers: dict[str, str]
) -> tuple[list[BlankGrade], int]:
    answer_key = _passage_answer_key(exercise)
    explanations = _passage_explanations(exercise)
    results = [
        BlankGrade(
            number=number,
            is_correct=_normalize_option_id(answers[str(number)])
            == answer_key[str(number)],
            correct_answer=answer_key[str(number)],
            explanation=explanations[str(number)],
        )
        for number in range(1, 5)
    ]
    return results, sum(result.is_correct for result in results)


def submit_attempt(
    db: Session,
    user_id: uuid.UUID,
    exercise_id: uuid.UUID,
    answer: str | None,
    answers: dict[str, str] | None = None,
) -> GradedAttempt:
    exercise = get_owned_exercise(db, user_id, exercise_id)
    if exercise.exercise_type == "multiple_choice":
        if answer is None or answers is not None:
            raise InvalidAttemptFormatError
        is_correct = _grade_multiple_choice(exercise, answer)
        stored_user_answer = answer.strip()
        results = None
        correct_count = total = score_percent = None
        response_explanation = exercise.explanation
    elif exercise.exercise_type == "fill_in_blank":
        if _is_passage_cloze(exercise):
            if answers is None or answer is not None:
                raise InvalidAttemptFormatError
            results, correct_count = _grade_passage_cloze(exercise, answers)
            total = 4
            score_percent = round(correct_count / total * 100)
            is_correct = correct_count == total
            stored_user_answer = json.dumps(
                {str(number): _normalize_option_id(answers[str(number)]) for number in range(1, 5)},
                sort_keys=True,
            )
            response_explanation = None
        else:
            # Explicit compatibility path for Phase 6 development exercises.
            if answer is None or answers is not None:
                raise InvalidAttemptFormatError
            is_correct = _grade_fill_in_blank(exercise, answer)
            stored_user_answer = answer.strip()
            results = None
            correct_count = total = score_percent = None
            response_explanation = exercise.explanation
    else:
        raise InvalidStoredExerciseError

    attempt = ExerciseAttempt(
        user_id=user_id,
        exercise_id=exercise.id,
        user_answer=stored_user_answer,
        correct_answer=exercise.correct_answer,
        is_correct=is_correct,
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    return GradedAttempt(
        attempt=attempt,
        explanation=response_explanation,
        correct_count=correct_count,
        total=total,
        score_percent=score_percent,
        results=results,
    )


def list_owned_attempts(
    db: Session,
    user_id: uuid.UUID,
    *,
    page: int,
    page_size: int,
    exercise_id: uuid.UUID | None = None,
) -> AttemptPage:
    conditions = [ExerciseAttempt.user_id == user_id]
    if exercise_id is not None:
        conditions.append(ExerciseAttempt.exercise_id == exercise_id)

    total = (
        db.scalar(select(func.count()).select_from(ExerciseAttempt).where(*conditions))
        or 0
    )
    statement = (
        select(ExerciseAttempt)
        .where(*conditions)
        .order_by(ExerciseAttempt.completed_at.desc(), ExerciseAttempt.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return AttemptPage(
        items=list(db.scalars(statement)),
        page=page,
        page_size=page_size,
        total=total,
        total_pages=ceil(total / page_size) if total else 0,
    )
