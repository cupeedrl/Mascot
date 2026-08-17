"""Create deterministic exercise and attempt tables.

Revision ID: 20260815_0004
Revises: 20260814_0003
Create Date: 2026-08-15 00:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260815_0004"
down_revision: str | Sequence[str] | None = "20260814_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "exercises",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("learning_track_id", sa.Uuid(), nullable=False),
        sa.Column("exercise_type", sa.String(length=32), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column(
            "options",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("correct_answer", sa.Text(), nullable=False),
        sa.Column(
            "accepted_answers",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column(
            "source",
            sa.String(length=20),
            server_default="manual",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "exercise_type IN ('multiple_choice', 'fill_in_blank')",
            name="ck_exercises_type",
        ),
        sa.CheckConstraint(
            "source IN ('manual', 'ai')",
            name="ck_exercises_source",
        ),
        sa.CheckConstraint(
            "length(trim(prompt)) > 0",
            name="ck_exercises_prompt_not_blank",
        ),
        sa.CheckConstraint(
            "length(trim(correct_answer)) > 0",
            name="ck_exercises_answer_not_blank",
        ),
        sa.CheckConstraint(
            "options IS NULL OR jsonb_typeof(options) = 'array'",
            name="ck_exercises_options_array",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(accepted_answers) = 'array'",
            name="ck_exercises_accepted_answers_array",
        ),
        sa.CheckConstraint(
            "(exercise_type = 'multiple_choice' AND options IS NOT NULL) OR "
            "(exercise_type = 'fill_in_blank' AND options IS NULL)",
            name="ck_exercises_options_by_type",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["learning_track_id"], ["learning_tracks.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_exercises_user_track_created",
        "exercises",
        ["user_id", "learning_track_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_exercises_user_type", "exercises", ["user_id", "exercise_type"]
    )

    op.create_table(
        "exercise_vocabularies",
        sa.Column("exercise_id", sa.Uuid(), nullable=False),
        sa.Column("vocabulary_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["exercise_id"], ["exercises.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["vocabulary_id"], ["vocabularies.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("exercise_id", "vocabulary_id"),
    )
    op.create_index(
        "ix_exercise_vocabularies_vocabulary_id",
        "exercise_vocabularies",
        ["vocabulary_id"],
    )

    op.create_table(
        "exercise_attempts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("exercise_id", sa.Uuid(), nullable=False),
        sa.Column("user_answer", sa.Text(), nullable=False),
        # This is an immutable answer snapshot, named `correct_answer` per PLAN.md.
        sa.Column("correct_answer", sa.Text(), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(trim(user_answer)) > 0",
            name="ck_exercise_attempts_user_answer_not_blank",
        ),
        sa.CheckConstraint(
            "length(trim(correct_answer)) > 0",
            name="ck_exercise_attempts_correct_answer_not_blank",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["exercise_id"], ["exercises.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_exercise_attempts_user_completed",
        "exercise_attempts",
        ["user_id", sa.text("completed_at DESC")],
    )
    op.create_index(
        "ix_exercise_attempts_user_correct",
        "exercise_attempts",
        ["user_id", "is_correct"],
    )
    op.create_index(
        "ix_exercise_attempts_exercise_id",
        "exercise_attempts",
        ["exercise_id"],
    )


def downgrade() -> None:
    op.drop_table("exercise_attempts")
    op.drop_table("exercise_vocabularies")
    op.drop_table("exercises")
