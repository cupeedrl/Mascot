"""Seed Mandarin Chinese and its HSK learning track.

Revision ID: 20260908_0011
Revises: 20260820_0010
Create Date: 2026-09-08 00:00:00
"""

from collections.abc import Sequence
import uuid

import sqlalchemy as sa
from alembic import op

revision: str = "20260908_0011"
down_revision: str | Sequence[str] | None = "20260820_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CHINESE_LANGUAGE_ID = uuid.UUID("33333333-3333-4333-8333-333333333333")
GENERAL_CHINESE_TRACK_ID = uuid.UUID("44444444-4444-4444-8444-444444444444")


def upgrade() -> None:
    connection = op.get_bind()
    languages = sa.table(
        "languages",
        sa.column("id", sa.Uuid()),
        sa.column("code", sa.String()),
        sa.column("name", sa.String()),
        sa.column("native_name", sa.String()),
        sa.column("is_active", sa.Boolean()),
    )
    tracks = sa.table(
        "learning_tracks",
        sa.column("id", sa.Uuid()),
        sa.column("language_id", sa.Uuid()),
        sa.column("code", sa.String()),
        sa.column("name", sa.String()),
        sa.column("description", sa.String()),
        sa.column("level_framework", sa.String()),
        sa.column("is_active", sa.Boolean()),
    )

    language_id = connection.scalar(
        sa.select(languages.c.id).where(languages.c.code == "zh")
    )
    if language_id is None:
        language_id = CHINESE_LANGUAGE_ID
        connection.execute(
            languages.insert().values(
                id=language_id,
                code="zh",
                name="Chinese",
                native_name="中文",
                is_active=True,
            )
        )

    track_id = connection.scalar(
        sa.select(tracks.c.id).where(
            tracks.c.language_id == language_id,
            tracks.c.code == "general-chinese",
        )
    )
    if track_id is None:
        connection.execute(
            tracks.insert().values(
                id=GENERAL_CHINESE_TRACK_ID,
                language_id=language_id,
                code="general-chinese",
                name="General Chinese",
                description="Mandarin Chinese vocabulary learning with HSK levels 1–9",
                level_framework="HSK",
                is_active=True,
            )
        )


def downgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text("DELETE FROM learning_tracks WHERE id = :track_id"),
        {"track_id": GENERAL_CHINESE_TRACK_ID},
    )
    connection.execute(
        sa.text("DELETE FROM languages WHERE id = :language_id"),
        {"language_id": CHINESE_LANGUAGE_ID},
    )
