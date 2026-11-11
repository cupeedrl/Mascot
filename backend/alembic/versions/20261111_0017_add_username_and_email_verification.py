"""Add usernames, display names and email verification codes.

Existing accounts are treated as verified (email_verified_at = created_at) so
nobody is locked out; they have no username until they choose one. New
accounts confirm their email with a 6-digit code when
REQUIRE_EMAIL_VERIFICATION is on (the default).

Revision ID: 20261111_0017
Revises: 20261111_0016
Create Date: 2026-11-11 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261111_0017"
down_revision: str | Sequence[str] | None = "20261111_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UPGRADE_SQL = """
ALTER TABLE users
    ADD COLUMN username varchar(30),
    ADD COLUMN normalized_username varchar(30),
    ADD COLUMN display_name varchar(80),
    ADD COLUMN email_verified_at timestamptz,
    ADD CONSTRAINT ck_users_username_pair
        CHECK ((username IS NULL) = (normalized_username IS NULL)),
    ADD CONSTRAINT ck_users_display_name_not_blank
        CHECK (display_name IS NULL OR length(trim(display_name)) > 0);
UPDATE users SET email_verified_at = created_at WHERE email_verified_at IS NULL;
CREATE UNIQUE INDEX uq_users_normalized_username
    ON users (normalized_username) WHERE normalized_username IS NOT NULL;
CREATE TABLE email_verification_codes (
    id uuid PRIMARY KEY,
    user_id uuid NOT NULL UNIQUE REFERENCES users (id) ON DELETE CASCADE,
    code_hash varchar(64) NOT NULL,
    expires_at timestamptz NOT NULL,
    attempts integer NOT NULL DEFAULT 0,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_email_verification_codes_attempts CHECK (attempts >= 0),
    CONSTRAINT ck_email_verification_codes_hash CHECK (length(code_hash) = 64)
);
"""

DOWNGRADE_SQL = """
DROP TABLE email_verification_codes;
DROP INDEX uq_users_normalized_username;
ALTER TABLE users
    DROP CONSTRAINT ck_users_display_name_not_blank,
    DROP CONSTRAINT ck_users_username_pair,
    DROP COLUMN email_verified_at,
    DROP COLUMN display_name,
    DROP COLUMN normalized_username,
    DROP COLUMN username;
"""


def _statements(script: str) -> list[str]:
    # One statement per execute: psycopg rejects multi-command prepared queries.
    return [part.strip() for part in script.split(";") if part.strip()]


def upgrade() -> None:
    for statement in _statements(UPGRADE_SQL):
        op.execute(sa.text(statement))


def downgrade() -> None:
    # Note: usernames and display names are lost on downgrade.
    for statement in _statements(DOWNGRADE_SQL):
        op.execute(sa.text(statement))
