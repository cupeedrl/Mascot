"""Add per-level topics and word-topic assignments to the HSK catalog.

Additive only: two new tables. Topics belong to one release and one level
(the official 2025 topic syllabus tree); a word can be assigned only to a
topic of a level it is a member of, in the same release.

Revision ID: 20261111_0016
Revises: 20261110_0015
Create Date: 2026-11-11 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261111_0016"
down_revision: str | Sequence[str] | None = "20261110_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UPGRADE_SQL = """
CREATE TABLE catalog_topics (
    id uuid PRIMARY KEY,
    catalog_release_id uuid NOT NULL,
    level_code varchar(16) NOT NULL,
    parent_id uuid,
    depth integer NOT NULL,
    topic_key varchar(255) NOT NULL,
    name_zh varchar(255) NOT NULL,
    name_vi varchar(255),
    source varchar(32) NOT NULL,
    order_index integer NOT NULL,
    CONSTRAINT fk_catalog_topics_release FOREIGN KEY (catalog_release_id)
        REFERENCES catalog_releases (id) ON DELETE CASCADE,
    CONSTRAINT uq_catalog_topics_id_release_level UNIQUE (id, catalog_release_id, level_code),
    CONSTRAINT fk_catalog_topics_parent_same_level
        FOREIGN KEY (parent_id, catalog_release_id, level_code)
        REFERENCES catalog_topics (id, catalog_release_id, level_code) ON DELETE CASCADE,
    CONSTRAINT uq_catalog_topics_key UNIQUE (catalog_release_id, level_code, topic_key),
    CONSTRAINT ck_catalog_topics_level
        CHECK (level_code IN ('HSK1', 'HSK2', 'HSK3', 'HSK4', 'HSK5', 'HSK6', 'HSK7-9')),
    CONSTRAINT ck_catalog_topics_depth CHECK (depth IN (1, 2, 3)),
    CONSTRAINT ck_catalog_topics_root CHECK ((depth = 1) = (parent_id IS NULL)),
    CONSTRAINT ck_catalog_topics_key CHECK (length(trim(topic_key)) > 0),
    CONSTRAINT ck_catalog_topics_name_zh CHECK (length(trim(name_zh)) > 0),
    CONSTRAINT ck_catalog_topics_name_vi CHECK (name_vi IS NULL OR length(trim(name_vi)) > 0),
    CONSTRAINT ck_catalog_topics_source CHECK (source IN ('official_syllabus', 'mascot')),
    CONSTRAINT ck_catalog_topics_order CHECK (order_index >= 0)
);
CREATE INDEX ix_catalog_topics_release_level
    ON catalog_topics (catalog_release_id, level_code, depth);

CREATE TABLE catalog_entry_topics (
    source_entry_id uuid NOT NULL,
    topic_id uuid NOT NULL,
    catalog_release_id uuid NOT NULL,
    level_code varchar(16) NOT NULL,
    origin varchar(20) NOT NULL,
    review_status varchar(16) NOT NULL DEFAULT 'proposed',
    PRIMARY KEY (source_entry_id, topic_id),
    CONSTRAINT fk_entry_topics_source_release FOREIGN KEY (source_entry_id, catalog_release_id)
        REFERENCES catalog_source_entries (id, catalog_release_id) ON DELETE CASCADE,
    CONSTRAINT fk_entry_topics_level_membership FOREIGN KEY (source_entry_id, level_code)
        REFERENCES catalog_source_entry_levels (source_entry_id, level_code) ON DELETE CASCADE,
    CONSTRAINT fk_entry_topics_topic_release_level
        FOREIGN KEY (topic_id, catalog_release_id, level_code)
        REFERENCES catalog_topics (id, catalog_release_id, level_code) ON DELETE CASCADE,
    CONSTRAINT ck_entry_topics_origin CHECK (origin IN ('ai_suggested', 'editorial')),
    CONSTRAINT ck_entry_topics_review_status
        CHECK (review_status IN ('proposed', 'approved', 'rejected'))
);
CREATE INDEX ix_entry_topics_topic ON catalog_entry_topics (topic_id, review_status);
"""

DOWNGRADE_SQL = """
DROP TABLE catalog_entry_topics;
DROP TABLE catalog_topics;
"""


def _statements(script: str) -> list[str]:
    # One statement per execute: psycopg rejects multi-command prepared queries.
    return [part.strip() for part in script.split(";") if part.strip()]


def upgrade() -> None:
    for statement in _statements(UPGRADE_SQL):
        op.execute(sa.text(statement))


def downgrade() -> None:
    # Topics are catalog data reloadable from the release dataset; no learner
    # data references these tables, so dropping them is lossless for users.
    for statement in _statements(DOWNGRADE_SQL):
        op.execute(sa.text(statement))
