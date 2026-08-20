"""Add IPA column to vocabularies and vocabulary_entries.

Revision ID: 20260819_0006
Revises: 20260818_0005
Create Date: 2026-08-19 00:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260819_0006"
down_revision: str | Sequence[str] | None = "20260818_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "vocabularies",
        sa.Column("ipa", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "vocabulary_entries",
        sa.Column("ipa", sa.String(length=100), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("vocabulary_entries", "ipa")
    op.drop_column("vocabularies", "ipa")
