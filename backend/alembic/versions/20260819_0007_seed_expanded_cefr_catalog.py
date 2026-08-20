"""Seed expanded CEFR catalog across A1-C2.

Revision ID: 20260819_0007
Revises: 20260819_0006
Create Date: 2026-08-19 00:00:00
"""

from collections.abc import Sequence

from alembic import op
from sqlalchemy.orm import Session

from app.catalog.loader import DATA_DIR, load_catalog_from_dir, load_catalog_into_db

revision: str = "20260819_0007"
down_revision: str | Sequence[str] | None = "20260819_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    session = Session(bind=bind)
    dataset = load_catalog_from_dir(DATA_DIR)
    load_catalog_into_db(session, dataset, validate_first=True)


def downgrade() -> None:
    pass
