from __future__ import annotations

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


def submit_attempt(
    db: Session,
    user_id: uuid.UUID,
    exercise_id: uuid.UUID,
    answer: str,
) -> GradedAttempt:
    exercise = get_owned_exercise(db, user_id, exercise_id)
    if exercise.exercise_type == "multiple_choice":
        is_correct = _grade_multiple_choice(exercise, answer)
    elif exercise.exercise_type == "fill_in_blank":
        is_correct = _grade_fill_in_blank(exercise, answer)
    else:
        raise InvalidStoredExerciseError

    attempt = ExerciseAttempt(
        user_id=user_id,
        exercise_id=exercise.id,
        user_answer=answer.strip(),
        correct_answer=exercise.correct_answer,
        is_correct=is_correct,
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    return GradedAttempt(attempt=attempt, explanation=exercise.explanation)


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
