"""Create per-user learning-track preferences.

Revision ID: 20260908_0014
Revises: 20260908_0013
Create Date: 2026-09-08 16:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260908_0014"
down_revision: str | Sequence[str] | None = "20260908_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_learning_preferences",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("learning_track_id", sa.Uuid(), nullable=False),
        sa.Column("current_level_code", sa.String(length=32), nullable=True),
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
            "current_level_code IS NULL OR length(trim(current_level_code)) > 0",
            name="ck_user_learning_preferences_level_not_blank",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["learning_track_id"], ["learning_tracks.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "learning_track_id",
            name="uq_user_learning_preferences_user_track",
        ),
    )
    op.create_index(
        "ix_user_learning_preferences_user_id",
        "user_learning_preferences",
        ["user_id"],
    )
    op.create_index(
        "ix_user_learning_preferences_learning_track_id",
        "user_learning_preferences",
        ["learning_track_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_user_learning_preferences_learning_track_id",
        table_name="user_learning_preferences",
    )
    op.drop_index(
        "ix_user_learning_preferences_user_id",
        table_name="user_learning_preferences",
    )
    op.drop_table("user_learning_preferences")
