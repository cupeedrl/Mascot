"""Create a small, idempotent set of deterministic exercises for local users."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Direct execution (`python scripts/seed_demo_exercises.py`) puts /app/scripts,
# not /app, first on sys.path. Ensure the bind-mounted project source wins over
# any older editable package cached in the container image.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import Exercise, User, Vocabulary


def _add_if_missing(db, exercise: Exercise) -> bool:
    exists = db.scalar(
        select(Exercise.id).where(
            Exercise.user_id == exercise.user_id,
            Exercise.source == "manual",
            Exercise.prompt == exercise.prompt,
        )
    )
    if exists is not None:
        # Detach the transient candidate from persistent vocabulary backrefs so
        # a repeated seed remains a clean no-op without flush warnings.
        exercise.vocabularies.clear()
        return False
    db.add(exercise)
    return True


def seed_for_user(db, user: User) -> int:
    vocabularies = list(
        db.scalars(
            select(Vocabulary)
            .where(Vocabulary.user_id == user.id)
            .order_by(Vocabulary.created_at.asc(), Vocabulary.id.asc())
            .limit(10)
        )
    )
    if not vocabularies:
        return 0

    by_word = {item.normalized_word: item for item in vocabularies}
    required_words = ["solely", "revenue", "efficient", "negotiate"]
    if any(word not in by_word for word in required_words):
        return 0
    choices = [by_word[word] for word in required_words]
    target = choices[0]
    created = 0
    fill = Exercise(
        user_id=user.id,
        learning_track_id=target.learning_track_id,
        exercise_type="fill_in_blank",
        prompt=(
            "WORKPLACE LANGUAGE PRACTICE\n\n"
            "The finance team focused (1) ______ on essential costs.\n"
            "It also compared monthly (2) ______ with last year's income.\n"
            "Managers wanted a more (3) ______ process for routine work.\n"
            "Before signing, both sides agreed to (4) ______ again."
        ),
        options=[
            {
                "number": number,
                "options": [
                    {"id": option_id, "text": item.word}
                    for option_id, item in zip("ABCD", choices, strict=True)
                ],
            }
            for number in range(1, 5)
        ],
        correct_answer='{"1": "A", "2": "B", "3": "C", "4": "D"}',
        accepted_answers=[],
        explanation=(
            '{"1":"Solely means only or exclusively.",'
            '"2":"Revenue is income received by a business.",'
            '"3":"Efficient means working well without waste.",'
            '"4":"Negotiate means discuss terms to reach agreement."}'
        ),
        source="manual",
        vocabularies=choices,
    )
    created += int(_add_if_missing(db, fill))

    if len(choices) == 4:
        multiple_choice = Exercise(
            user_id=user.id,
            learning_track_id=target.learning_track_id,
            exercise_type="multiple_choice",
            prompt="The budget committee focused _______ on essential costs.",
            options=[
                {"id": option_id, "text": item.word}
                for option_id, item in zip("ABCD", choices, strict=True)
            ],
            correct_answer="A",
            accepted_answers=[],
            explanation=f'{target.word} means "{target.meaning}".',
            source="manual",
            vocabularies=choices,
        )
        created += int(_add_if_missing(db, multiple_choice))

    db.commit()
    return created


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--email",
        help="Seed only this existing user; omit to seed every existing user.",
    )
    args = parser.parse_args()

    with SessionLocal() as db:
        statement = select(User).where(User.is_active.is_(True)).order_by(User.email)
        if args.email:
            statement = statement.where(
                User.normalized_email == args.email.strip().casefold()
            )
        users = list(db.scalars(statement))
        if not users:
            raise SystemExit("No matching active user found.")

        total = 0
        for user in users:
            created = seed_for_user(db, user)
            total += created
            print(f"{user.email}: created {created} demo exercise(s)")
        print(f"Created {total} demo exercise(s) in total.")


if __name__ == "__main__":
    main()
