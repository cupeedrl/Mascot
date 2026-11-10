"""Create the normalized, release-aware HSK catalog (milestone 1).

Additive only: new tables plus nullable provenance columns on
``vocabularies``. No catalog data is inserted here; releases are loaded by
``scripts/import_hsk_release.py`` from an approved dataset. Existing CEFR
catalog rows, the Chinese development set and personal vocabulary are not
modified.

Rollback limit: downgrade refuses to run once any personal vocabulary row
references the normalized catalog, because dropping the columns would
discard the learner's provenance snapshot.

Revision ID: 20261110_0015
Revises: 20260908_0014
Create Date: 2026-11-10 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261110_0015"
down_revision: str | Sequence[str] | None = "20260908_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PERMISSIONS = "('unknown', 'pending', 'approved', 'restricted', 'denied')"
POS_CODES = (
    "('noun', 'verb', 'adjective', 'adverb', 'pronoun', 'numeral', 'measure_word', "
    "'numeral_measure', 'preposition', 'conjunction', 'particle', 'interjection', "
    "'onomatopoeia', 'prefix', 'suffix', 'phrase', 'idiom')"
)

UPGRADE_SQL = f"""
CREATE TABLE catalog_releases (
    id uuid PRIMARY KEY,
    learning_track_id uuid NOT NULL
        REFERENCES learning_tracks (id) ON DELETE RESTRICT,
    code varchar(64) NOT NULL,
    title varchar(200) NOT NULL,
    source_name varchar(200) NOT NULL,
    source_version varchar(100),
    source_sha256 varchar(64) NOT NULL,
    source_manifest jsonb NOT NULL,
    data_origin varchar(24) NOT NULL,
    status varchar(20) NOT NULL DEFAULT 'draft',
    storage_permission_status varchar(20) NOT NULL DEFAULT 'unknown',
    transformation_permission_status varchar(20) NOT NULL DEFAULT 'unknown',
    redistribution_permission_status varchar(20) NOT NULL DEFAULT 'unknown',
    publication_permission_status varchar(20) NOT NULL DEFAULT 'unknown',
    permission_evidence jsonb NOT NULL DEFAULT '{{}}'::jsonb,
    import_report jsonb,
    import_completed_at timestamptz,
    published_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_catalog_releases_track_code UNIQUE (learning_track_id, code),
    CONSTRAINT uq_catalog_releases_id_track UNIQUE (id, learning_track_id),
    CONSTRAINT ck_catalog_releases_code_not_blank CHECK (length(trim(code)) > 0),
    CONSTRAINT ck_catalog_releases_title_not_blank CHECK (length(trim(title)) > 0),
    CONSTRAINT ck_catalog_releases_source_name_not_blank CHECK (length(trim(source_name)) > 0),
    CONSTRAINT ck_catalog_releases_status
        CHECK (status IN ('draft', 'in_review', 'published', 'retired')),
    CONSTRAINT ck_catalog_releases_data_origin
        CHECK (data_origin IN ('third_party', 'mascot_owned', 'synthetic_fixture')),
    CONSTRAINT ck_catalog_releases_storage_permission
        CHECK (storage_permission_status IN {PERMISSIONS}),
    CONSTRAINT ck_catalog_releases_transformation_permission
        CHECK (transformation_permission_status IN {PERMISSIONS}),
    CONSTRAINT ck_catalog_releases_redistribution_permission
        CHECK (redistribution_permission_status IN {PERMISSIONS}),
    CONSTRAINT ck_catalog_releases_publication_permission
        CHECK (publication_permission_status IN {PERMISSIONS}),
    CONSTRAINT ck_catalog_releases_source_sha256_length CHECK (length(source_sha256) = 64),
    CONSTRAINT ck_catalog_releases_publication_permissions CHECK (
        status <> 'published' OR data_origin <> 'third_party' OR (
            storage_permission_status = 'approved'
            AND transformation_permission_status = 'approved'
            AND redistribution_permission_status = 'approved'
            AND publication_permission_status = 'approved')),
    CONSTRAINT ck_catalog_releases_published_requires_import
        CHECK (status NOT IN ('published', 'retired') OR import_completed_at IS NOT NULL),
    CONSTRAINT ck_catalog_releases_published_at
        CHECK (status <> 'published' OR published_at IS NOT NULL),
    CONSTRAINT ck_catalog_releases_manifest_object
        CHECK (jsonb_typeof(source_manifest) = 'object'),
    CONSTRAINT ck_catalog_releases_evidence_object
        CHECK (jsonb_typeof(permission_evidence) = 'object')
);
CREATE UNIQUE INDEX uq_catalog_releases_one_published_per_track
    ON catalog_releases (learning_track_id) WHERE status = 'published';

CREATE TABLE catalog_source_entries (
    id uuid PRIMARY KEY,
    catalog_release_id uuid NOT NULL
        REFERENCES catalog_releases (id) ON DELETE RESTRICT,
    source_record_id_type varchar(64) NOT NULL,
    source_record_id_value varchar(255) NOT NULL,
    official_serial integer,
    raw_word varchar(255) NOT NULL,
    raw_pinyin varchar(255) NOT NULL,
    raw_pos varchar(64),
    raw_level_name varchar(64) NOT NULL,
    raw_payload jsonb NOT NULL,
    payload_sha256 varchar(64) NOT NULL,
    search_pinyin varchar(255) NOT NULL,
    review_status varchar(20) NOT NULL DEFAULT 'pending',
    review_flags jsonb NOT NULL DEFAULT '[]'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_catalog_source_entries_identity
        UNIQUE (catalog_release_id, source_record_id_type, source_record_id_value),
    CONSTRAINT uq_catalog_source_entries_id_release UNIQUE (id, catalog_release_id),
    CONSTRAINT ck_catalog_source_entries_id_type CHECK (length(trim(source_record_id_type)) > 0),
    CONSTRAINT ck_catalog_source_entries_id_value CHECK (length(trim(source_record_id_value)) > 0),
    CONSTRAINT ck_catalog_source_entries_raw_word CHECK (length(trim(raw_word)) > 0),
    CONSTRAINT ck_catalog_source_entries_raw_pinyin CHECK (length(trim(raw_pinyin)) > 0),
    CONSTRAINT ck_catalog_source_entries_serial_positive
        CHECK (official_serial IS NULL OR official_serial > 0),
    CONSTRAINT ck_catalog_source_entries_payload_sha256 CHECK (length(payload_sha256) = 64),
    CONSTRAINT ck_catalog_source_entries_review_status
        CHECK (review_status IN ('pending', 'accepted', 'ambiguous', 'retired')),
    CONSTRAINT ck_catalog_source_entries_payload_object
        CHECK (jsonb_typeof(raw_payload) = 'object'),
    CONSTRAINT ck_catalog_source_entries_flags_array
        CHECK (jsonb_typeof(review_flags) = 'array')
);
CREATE UNIQUE INDEX uq_catalog_source_entries_release_serial
    ON catalog_source_entries (catalog_release_id, official_serial)
    WHERE official_serial IS NOT NULL;
CREATE INDEX ix_catalog_source_entries_release_word
    ON catalog_source_entries (catalog_release_id, raw_word);

CREATE TABLE catalog_source_entry_levels (
    source_entry_id uuid NOT NULL,
    level_code varchar(16) NOT NULL,
    catalog_release_id uuid NOT NULL,
    role varchar(16) NOT NULL,
    order_index integer NOT NULL,
    PRIMARY KEY (source_entry_id, level_code),
    CONSTRAINT fk_source_levels_source_release
        FOREIGN KEY (source_entry_id, catalog_release_id)
        REFERENCES catalog_source_entries (id, catalog_release_id) ON DELETE CASCADE,
    CONSTRAINT ck_source_levels_level_code
        CHECK (level_code IN ('HSK1', 'HSK2', 'HSK3', 'HSK4', 'HSK5', 'HSK6', 'HSK7-9')),
    CONSTRAINT ck_source_levels_role CHECK (role IN ('primary', 'annotation')),
    CONSTRAINT ck_source_levels_order CHECK (order_index >= 0),
    CONSTRAINT ck_source_levels_primary_first CHECK ((role = 'primary') = (order_index = 0)),
    CONSTRAINT uq_source_levels_order UNIQUE (source_entry_id, order_index)
);
CREATE UNIQUE INDEX uq_source_levels_one_primary
    ON catalog_source_entry_levels (source_entry_id) WHERE role = 'primary';
CREATE INDEX ix_source_levels_release_level_role
    ON catalog_source_entry_levels (catalog_release_id, level_code, role);

CREATE TABLE lexical_entries (
    id uuid PRIMARY KEY,
    language_id uuid NOT NULL REFERENCES languages (id) ON DELETE RESTRICT,
    lexical_key varchar(128) NOT NULL,
    headword varchar(255) NOT NULL,
    status varchar(16) NOT NULL DEFAULT 'active',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_lexical_entries_language_key UNIQUE (language_id, lexical_key),
    CONSTRAINT ck_lexical_entries_key CHECK (length(trim(lexical_key)) > 0),
    CONSTRAINT ck_lexical_entries_headword CHECK (length(trim(headword)) > 0),
    CONSTRAINT ck_lexical_entries_status CHECK (status IN ('active', 'retired'))
);
CREATE INDEX ix_lexical_entries_headword ON lexical_entries (language_id, headword);

CREATE TABLE lexical_pronunciations (
    id uuid PRIMARY KEY,
    lexical_entry_id uuid NOT NULL REFERENCES lexical_entries (id) ON DELETE CASCADE,
    pinyin varchar(255) NOT NULL,
    order_index integer NOT NULL,
    CONSTRAINT uq_lexical_pronunciations_pinyin UNIQUE (lexical_entry_id, pinyin),
    CONSTRAINT uq_lexical_pronunciations_id_lexical UNIQUE (id, lexical_entry_id),
    CONSTRAINT ck_lexical_pronunciations_pinyin CHECK (length(trim(pinyin)) > 0),
    CONSTRAINT ck_lexical_pronunciations_order CHECK (order_index >= 0)
);

CREATE TABLE lexical_senses (
    id uuid PRIMARY KEY,
    lexical_entry_id uuid NOT NULL REFERENCES lexical_entries (id) ON DELETE CASCADE,
    sense_key varchar(64) NOT NULL,
    gloss_en text,
    gloss_vi text,
    gloss_source varchar(120) NOT NULL,
    review_status varchar(16) NOT NULL DEFAULT 'draft',
    status varchar(16) NOT NULL DEFAULT 'active',
    order_index integer NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_lexical_senses_key UNIQUE (lexical_entry_id, sense_key),
    CONSTRAINT uq_lexical_senses_id_lexical UNIQUE (id, lexical_entry_id),
    CONSTRAINT ck_lexical_senses_key CHECK (length(trim(sense_key)) > 0),
    CONSTRAINT ck_lexical_senses_has_gloss CHECK (gloss_en IS NOT NULL OR gloss_vi IS NOT NULL),
    CONSTRAINT ck_lexical_senses_gloss_en CHECK (gloss_en IS NULL OR length(trim(gloss_en)) > 0),
    CONSTRAINT ck_lexical_senses_gloss_vi CHECK (gloss_vi IS NULL OR length(trim(gloss_vi)) > 0),
    CONSTRAINT ck_lexical_senses_gloss_source CHECK (length(trim(gloss_source)) > 0),
    CONSTRAINT ck_lexical_senses_review_status
        CHECK (review_status IN ('draft', 'approved', 'rejected')),
    CONSTRAINT ck_lexical_senses_status CHECK (status IN ('active', 'retired')),
    CONSTRAINT ck_lexical_senses_order CHECK (order_index >= 0)
);

CREATE TABLE lexical_sense_pos (
    sense_id uuid NOT NULL REFERENCES lexical_senses (id) ON DELETE CASCADE,
    pos_code varchar(32) NOT NULL,
    pos_origin varchar(20) NOT NULL,
    source_label varchar(32),
    PRIMARY KEY (sense_id, pos_code),
    CONSTRAINT ck_lexical_sense_pos_code CHECK (pos_code IN {POS_CODES}),
    CONSTRAINT ck_lexical_sense_pos_origin CHECK (pos_origin IN ('official_source', 'editorial')),
    CONSTRAINT ck_lexical_sense_pos_source_label
        CHECK (source_label IS NULL OR length(trim(source_label)) > 0)
);

CREATE TABLE lexical_sense_pronunciations (
    sense_id uuid NOT NULL,
    pronunciation_id uuid NOT NULL,
    lexical_entry_id uuid NOT NULL,
    PRIMARY KEY (sense_id, pronunciation_id),
    CONSTRAINT fk_sense_pron_sense_lexical FOREIGN KEY (sense_id, lexical_entry_id)
        REFERENCES lexical_senses (id, lexical_entry_id) ON DELETE CASCADE,
    CONSTRAINT fk_sense_pron_pronunciation_lexical FOREIGN KEY (pronunciation_id, lexical_entry_id)
        REFERENCES lexical_pronunciations (id, lexical_entry_id) ON DELETE CASCADE
);

CREATE TABLE lexical_variants (
    id uuid PRIMARY KEY,
    lexical_entry_id uuid NOT NULL REFERENCES lexical_entries (id) ON DELETE CASCADE,
    pronunciation_id uuid,
    variant_form varchar(255) NOT NULL,
    variant_type varchar(20) NOT NULL,
    variant_source varchar(120) NOT NULL,
    order_index integer NOT NULL,
    CONSTRAINT fk_variants_pronunciation_lexical FOREIGN KEY (pronunciation_id, lexical_entry_id)
        REFERENCES lexical_pronunciations (id, lexical_entry_id) ON DELETE CASCADE,
    CONSTRAINT uq_lexical_variants_form UNIQUE (lexical_entry_id, variant_form, variant_type),
    CONSTRAINT ck_lexical_variants_form CHECK (length(trim(variant_form)) > 0),
    CONSTRAINT ck_lexical_variants_type
        CHECK (variant_type IN ('traditional', 'alternate', 'erhua')),
    CONSTRAINT ck_lexical_variants_source CHECK (length(trim(variant_source)) > 0)
);

CREATE TABLE lexical_sense_examples (
    id uuid PRIMARY KEY,
    sense_id uuid NOT NULL REFERENCES lexical_senses (id) ON DELETE CASCADE,
    text_zh text NOT NULL,
    pinyin text,
    translation_vi text,
    example_source varchar(120) NOT NULL,
    order_index integer NOT NULL,
    CONSTRAINT uq_lexical_sense_examples_order UNIQUE (sense_id, order_index),
    CONSTRAINT ck_lexical_sense_examples_text CHECK (length(trim(text_zh)) > 0),
    CONSTRAINT ck_lexical_sense_examples_source CHECK (length(trim(example_source)) > 0),
    CONSTRAINT ck_lexical_sense_examples_order CHECK (order_index >= 0)
);

CREATE TABLE catalog_source_mappings (
    id uuid PRIMARY KEY,
    catalog_release_id uuid NOT NULL,
    source_entry_id uuid NOT NULL,
    lexical_entry_id uuid NOT NULL REFERENCES lexical_entries (id) ON DELETE RESTRICT,
    pronunciation_id uuid,
    sense_id uuid,
    review_status varchar(16) NOT NULL DEFAULT 'proposed',
    order_index integer NOT NULL,
    notes text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fk_mappings_source_release FOREIGN KEY (source_entry_id, catalog_release_id)
        REFERENCES catalog_source_entries (id, catalog_release_id) ON DELETE RESTRICT,
    CONSTRAINT fk_mappings_pronunciation_lexical FOREIGN KEY (pronunciation_id, lexical_entry_id)
        REFERENCES lexical_pronunciations (id, lexical_entry_id) ON DELETE RESTRICT,
    CONSTRAINT fk_mappings_sense_lexical FOREIGN KEY (sense_id, lexical_entry_id)
        REFERENCES lexical_senses (id, lexical_entry_id) ON DELETE RESTRICT,
    CONSTRAINT fk_mappings_sense_pronunciation FOREIGN KEY (sense_id, pronunciation_id)
        REFERENCES lexical_sense_pronunciations (sense_id, pronunciation_id) ON DELETE RESTRICT,
    CONSTRAINT uq_mappings_interpretation UNIQUE NULLS NOT DISTINCT
        (source_entry_id, lexical_entry_id, pronunciation_id, sense_id),
    CONSTRAINT uq_mappings_id_source UNIQUE (id, source_entry_id),
    CONSTRAINT uq_mappings_id_sense UNIQUE (id, sense_id),
    CONSTRAINT ck_mappings_review_status
        CHECK (review_status IN ('proposed', 'approved', 'rejected')),
    CONSTRAINT ck_mappings_order CHECK (order_index >= 0)
);
CREATE INDEX ix_mappings_release_source
    ON catalog_source_mappings (catalog_release_id, source_entry_id);

ALTER TABLE vocabularies
    ADD COLUMN catalog_source_entry_id uuid
        CONSTRAINT fk_vocab_catalog_source_entry
        REFERENCES catalog_source_entries (id) ON DELETE RESTRICT,
    ADD COLUMN catalog_mapping_id uuid,
    ADD COLUMN catalog_sense_id uuid
        CONSTRAINT fk_vocab_catalog_sense
        REFERENCES lexical_senses (id) ON DELETE RESTRICT,
    ADD COLUMN catalog_pronunciation_id uuid
        CONSTRAINT fk_vocab_catalog_pronunciation
        REFERENCES lexical_pronunciations (id) ON DELETE RESTRICT,
    ADD COLUMN catalog_snapshot jsonb,
    ADD CONSTRAINT fk_vocab_catalog_mapping_source
        FOREIGN KEY (catalog_mapping_id, catalog_source_entry_id)
        REFERENCES catalog_source_mappings (id, source_entry_id) ON DELETE RESTRICT,
    ADD CONSTRAINT fk_vocab_catalog_mapping_sense
        FOREIGN KEY (catalog_mapping_id, catalog_sense_id)
        REFERENCES catalog_source_mappings (id, sense_id) ON DELETE RESTRICT,
    ADD CONSTRAINT fk_vocab_catalog_sense_pronunciation
        FOREIGN KEY (catalog_sense_id, catalog_pronunciation_id)
        REFERENCES lexical_sense_pronunciations (sense_id, pronunciation_id) ON DELETE RESTRICT,
    ADD CONSTRAINT ck_vocab_catalog_save_complete CHECK (
        catalog_source_entry_id IS NULL OR (
            catalog_mapping_id IS NOT NULL AND catalog_sense_id IS NOT NULL
            AND catalog_snapshot IS NOT NULL)),
    ADD CONSTRAINT ck_vocab_catalog_refs_need_source CHECK (
        catalog_source_entry_id IS NOT NULL OR (
            catalog_mapping_id IS NULL AND catalog_sense_id IS NULL
            AND catalog_pronunciation_id IS NULL)),
    ADD CONSTRAINT ck_vocab_single_catalog_origin
        CHECK (catalog_source_entry_id IS NULL OR source_vocabulary_entry_id IS NULL),
    ADD CONSTRAINT ck_vocab_catalog_snapshot_object
        CHECK (catalog_snapshot IS NULL OR jsonb_typeof(catalog_snapshot) = 'object');
CREATE UNIQUE INDEX uq_vocab_user_catalog_source_sense
    ON vocabularies (user_id, catalog_source_entry_id, catalog_sense_id) NULLS NOT DISTINCT
    WHERE catalog_source_entry_id IS NOT NULL;
"""

DOWNGRADE_SQL = """
DROP INDEX uq_vocab_user_catalog_source_sense;
ALTER TABLE vocabularies
    DROP CONSTRAINT ck_vocab_catalog_snapshot_object,
    DROP CONSTRAINT ck_vocab_single_catalog_origin,
    DROP CONSTRAINT ck_vocab_catalog_refs_need_source,
    DROP CONSTRAINT ck_vocab_catalog_save_complete,
    DROP CONSTRAINT fk_vocab_catalog_sense_pronunciation,
    DROP CONSTRAINT fk_vocab_catalog_mapping_sense,
    DROP CONSTRAINT fk_vocab_catalog_mapping_source,
    DROP COLUMN catalog_snapshot,
    DROP COLUMN catalog_pronunciation_id,
    DROP COLUMN catalog_sense_id,
    DROP COLUMN catalog_mapping_id,
    DROP COLUMN catalog_source_entry_id;
DROP TABLE catalog_source_mappings;
DROP TABLE lexical_sense_examples;
DROP TABLE lexical_variants;
DROP TABLE lexical_sense_pronunciations;
DROP TABLE lexical_sense_pos;
DROP TABLE lexical_senses;
DROP TABLE lexical_pronunciations;
DROP TABLE lexical_entries;
DROP TABLE catalog_source_entry_levels;
DROP TABLE catalog_source_entries;
DROP TABLE catalog_releases;
"""


def _statements(script: str) -> list[str]:
    # One statement per execute: psycopg rejects multi-command prepared queries.
    return [part.strip() for part in script.split(";") if part.strip()]


def upgrade() -> None:
    for statement in _statements(UPGRADE_SQL):
        op.execute(sa.text(statement))


def downgrade() -> None:
    connection = op.get_bind()
    saved = connection.scalar(
        sa.text("SELECT count(*) FROM vocabularies WHERE catalog_source_entry_id IS NOT NULL")
    )
    if saved:
        raise RuntimeError(
            f"Refusing to downgrade 20261110_0015: {saved} personal vocabulary rows reference "
            "the normalized HSK catalog. Dropping these columns would discard learner "
            "provenance snapshots. Export or detach them deliberately first."
        )
    for statement in _statements(DOWNGRADE_SQL):
        op.execute(sa.text(statement))
