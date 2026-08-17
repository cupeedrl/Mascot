"""Create language, learning track, and vocabulary tables.

Revision ID: 20260814_0002
Revises: 20260813_0001
Create Date: 2026-08-14 00:00:00
"""

import uuid
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260814_0002"
down_revision: str | Sequence[str] | None = "20260813_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ENGLISH_LANGUAGE_ID = uuid.UUID("11111111-1111-4111-8111-111111111111")
GENERAL_ENGLISH_TRACK_ID = uuid.UUID("22222222-2222-4222-8222-222222222222")


def upgrade() -> None:
    languages = op.create_table(
        "languages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=16), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("native_name", sa.String(length=100), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("length(trim(code)) > 0", name="ck_languages_code_not_blank"),
        sa.CheckConstraint("code = lower(code)", name="ck_languages_code_lowercase"),
        sa.CheckConstraint("length(trim(name)) > 0", name="ck_languages_name_not_blank"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_languages_code", "languages", ["code"], unique=True)

    learning_tracks = op.create_table(
        "learning_tracks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("language_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("level_framework", sa.String(length=32), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "length(trim(code)) > 0", name="ck_learning_tracks_code_not_blank"
        ),
        sa.CheckConstraint(
            "code = lower(code)", name="ck_learning_tracks_code_lowercase"
        ),
        sa.CheckConstraint(
            "length(trim(name)) > 0", name="ck_learning_tracks_name_not_blank"
        ),
        sa.CheckConstraint(
            "length(trim(level_framework)) > 0",
            name="ck_learning_tracks_framework_not_blank",
        ),
        sa.ForeignKeyConstraint(
            ["language_id"], ["languages.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "language_id", "code", name="uq_learning_tracks_language_code"
        ),
    )
    op.create_index(
        "ix_learning_tracks_language_id", "learning_tracks", ["language_id"]
    )

    op.create_table(
        "vocabularies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("learning_track_id", sa.Uuid(), nullable=False),
        sa.Column("word", sa.String(length=255), nullable=False),
        sa.Column("normalized_word", sa.String(length=255), nullable=False),
        sa.Column("part_of_speech", sa.String(length=64), nullable=False),
        sa.Column("meaning", sa.Text(), nullable=False),
        sa.Column("translation", sa.Text(), nullable=False),
        sa.Column(
            "translation_language_code",
            sa.String(length=16),
            server_default=sa.text("'vi'"),
            nullable=False,
        ),
        sa.Column(
            "example_sentences",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("level_code", sa.String(length=32), nullable=False),
        sa.Column("topic", sa.String(length=120), nullable=True),
        sa.Column(
            "learning_status",
            sa.String(length=20),
            server_default=sa.text("'new'"),
            nullable=False,
        ),
        sa.Column("review_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("correct_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("incorrect_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("last_reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_review_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("length(trim(word)) > 0", name="ck_vocabularies_word_not_blank"),
        sa.CheckConstraint(
            "length(trim(normalized_word)) > 0",
            name="ck_vocabularies_normalized_word_not_blank",
        ),
        sa.CheckConstraint(
            "length(trim(part_of_speech)) > 0",
            name="ck_vocabularies_part_of_speech_not_blank",
        ),
        sa.CheckConstraint(
            "length(trim(meaning)) > 0", name="ck_vocabularies_meaning_not_blank"
        ),
        sa.CheckConstraint(
            "length(trim(translation)) > 0", name="ck_vocabularies_translation_not_blank"
        ),
        sa.CheckConstraint(
            "jsonb_typeof(example_sentences) = 'array'",
            name="ck_vocabularies_examples_array",
        ),
        sa.CheckConstraint(
            "learning_status IN ('new', 'learning', 'review', 'mastered')",
            name="ck_vocabularies_learning_status",
        ),
        sa.CheckConstraint("review_count >= 0", name="ck_vocabularies_review_count"),
        sa.CheckConstraint("correct_count >= 0", name="ck_vocabularies_correct_count"),
        sa.CheckConstraint("incorrect_count >= 0", name="ck_vocabularies_incorrect_count"),
        sa.CheckConstraint(
            "correct_count + incorrect_count <= review_count",
            name="ck_vocabularies_review_totals",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["learning_track_id"], ["learning_tracks.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_vocab_user_created",
        "vocabularies",
        ["user_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_vocab_user_track_status",
        "vocabularies",
        ["user_id", "learning_track_id", "learning_status"],
    )
    op.create_index(
        "ix_vocab_user_track_level",
        "vocabularies",
        ["user_id", "learning_track_id", "level_code"],
    )
    op.create_index(
        "ix_vocab_user_track_topic",
        "vocabularies",
        ["user_id", "learning_track_id", "topic"],
    )
    op.create_index(
        "ix_vocab_user_normalized",
        "vocabularies",
        ["user_id", "learning_track_id", "normalized_word"],
    )
    op.create_index(
        "ix_vocab_user_next_review",
        "vocabularies",
        ["user_id", "next_review_at"],
        postgresql_where=sa.text("next_review_at IS NOT NULL"),
    )

    op.bulk_insert(
        languages,
        [
            {
                "id": ENGLISH_LANGUAGE_ID,
                "code": "en",
                "name": "English",
                "native_name": "English",
                "is_active": True,
            }
        ],
    )
    op.bulk_insert(
        learning_tracks,
        [
            {
                "id": GENERAL_ENGLISH_TRACK_ID,
                "language_id": ENGLISH_LANGUAGE_ID,
                "code": "general-english",
                "name": "General English",
                "description": "General English learning for V1",
                "level_framework": "CEFR",
                "is_active": True,
            }
        ],
    )


def downgrade() -> None:
    op.drop_table("vocabularies")
    op.drop_index("ix_learning_tracks_language_id", table_name="learning_tracks")
    op.drop_table("learning_tracks")
    op.drop_index("ix_languages_code", table_name="languages")
    op.drop_table("languages")
