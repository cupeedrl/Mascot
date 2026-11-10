"""Normalized, release-aware catalog for HSK vocabulary (milestone 1).

See docs/hsk/HSK_CATALOG_IMPLEMENTATION_PLAN.md. Official source fields are
stored verbatim on ``CatalogSourceEntry``; reviewed lexical structure lives in
the ``lexical_*`` tables and is linked through ``CatalogSourceMapping``.

PostgreSQL is the authoritative engine. Partial indexes declare both
``postgresql_where`` and ``sqlite_where`` so the in-memory SQLite test schema
keeps the same semantics; JSON-shape CHECKs exist only in the migration.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

JSONType = JSON().with_variant(JSONB, "postgresql")

RELEASE_STATUSES = ("draft", "in_review", "published", "retired")
DATA_ORIGINS = ("third_party", "mascot_owned", "synthetic_fixture")
PERMISSION_STATUSES = ("unknown", "pending", "approved", "restricted", "denied")
SOURCE_REVIEW_STATUSES = ("pending", "accepted", "ambiguous", "retired")
CATALOG_LEVEL_CODES = ("HSK1", "HSK2", "HSK3", "HSK4", "HSK5", "HSK6", "HSK7-9")
LEVEL_ROLES = ("primary", "annotation")
LEXICAL_STATUSES = ("active", "retired")
SENSE_REVIEW_STATUSES = ("draft", "approved", "rejected")
SENSE_STATUSES = ("active", "retired")
MAPPING_REVIEW_STATUSES = ("proposed", "approved", "rejected")
POS_ORIGINS = ("official_source", "editorial")
VARIANT_TYPES = ("traditional", "alternate", "erhua")
# Controlled milestone-1 list (OD-02 open). Missing POS = no row, never a guess.
POS_CODES = (
    "noun",
    "verb",
    "adjective",
    "adverb",
    "pronoun",
    "numeral",
    "measure_word",
    "numeral_measure",
    "preposition",
    "conjunction",
    "particle",
    "interjection",
    "onomatopoeia",
    "prefix",
    "suffix",
    "phrase",
    "idiom",
)


def _in(column: str, values: tuple[str, ...]) -> str:
    quoted = ", ".join(f"'{value}'" for value in values)
    return f"{column} IN ({quoted})"


def _partial(where: str) -> dict[str, object]:
    return {"postgresql_where": text(where), "sqlite_where": text(where)}


class CatalogRelease(Base):
    __tablename__ = "catalog_releases"
    __table_args__ = (
        UniqueConstraint("learning_track_id", "code", name="uq_catalog_releases_track_code"),
        UniqueConstraint("id", "learning_track_id", name="uq_catalog_releases_id_track"),
        CheckConstraint("length(trim(code)) > 0", name="ck_catalog_releases_code_not_blank"),
        CheckConstraint("length(trim(title)) > 0", name="ck_catalog_releases_title_not_blank"),
        CheckConstraint(
            "length(trim(source_name)) > 0", name="ck_catalog_releases_source_name_not_blank"
        ),
        CheckConstraint(_in("status", RELEASE_STATUSES), name="ck_catalog_releases_status"),
        CheckConstraint(_in("data_origin", DATA_ORIGINS), name="ck_catalog_releases_data_origin"),
        CheckConstraint(
            _in("storage_permission_status", PERMISSION_STATUSES),
            name="ck_catalog_releases_storage_permission",
        ),
        CheckConstraint(
            _in("transformation_permission_status", PERMISSION_STATUSES),
            name="ck_catalog_releases_transformation_permission",
        ),
        CheckConstraint(
            _in("redistribution_permission_status", PERMISSION_STATUSES),
            name="ck_catalog_releases_redistribution_permission",
        ),
        CheckConstraint(
            _in("publication_permission_status", PERMISSION_STATUSES),
            name="ck_catalog_releases_publication_permission",
        ),
        CheckConstraint(
            "length(source_sha256) = 64", name="ck_catalog_releases_source_sha256_length"
        ),
        # Publication gate: a third-party release may become published only when
        # all four independently recorded permissions are approved.
        CheckConstraint(
            "status <> 'published' OR data_origin <> 'third_party' OR ("
            "storage_permission_status = 'approved' AND "
            "transformation_permission_status = 'approved' AND "
            "redistribution_permission_status = 'approved' AND "
            "publication_permission_status = 'approved')",
            name="ck_catalog_releases_publication_permissions",
        ),
        CheckConstraint(
            "status NOT IN ('published', 'retired') OR import_completed_at IS NOT NULL",
            name="ck_catalog_releases_published_requires_import",
        ),
        CheckConstraint(
            "status <> 'published' OR published_at IS NOT NULL",
            name="ck_catalog_releases_published_at",
        ),
        Index(
            "uq_catalog_releases_one_published_per_track",
            "learning_track_id",
            unique=True,
            **_partial("status = 'published'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    learning_track_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("learning_tracks.id", ondelete="RESTRICT"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    source_name: Mapped[str] = mapped_column(String(200), nullable=False)
    source_version: Mapped[str | None] = mapped_column(String(100))
    source_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    source_manifest: Mapped[dict] = mapped_column(JSONType, nullable=False)
    data_origin: Mapped[str] = mapped_column(String(24), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="draft", server_default="draft"
    )
    storage_permission_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="unknown", server_default="unknown"
    )
    transformation_permission_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="unknown", server_default="unknown"
    )
    redistribution_permission_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="unknown", server_default="unknown"
    )
    publication_permission_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="unknown", server_default="unknown"
    )
    permission_evidence: Mapped[dict] = mapped_column(
        JSONType, nullable=False, default=dict, server_default=text("'{}'")
    )
    import_report: Mapped[dict | None] = mapped_column(JSONType)
    import_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class CatalogSourceEntry(Base):
    __tablename__ = "catalog_source_entries"
    __table_args__ = (
        UniqueConstraint(
            "catalog_release_id",
            "source_record_id_type",
            "source_record_id_value",
            name="uq_catalog_source_entries_identity",
        ),
        UniqueConstraint("id", "catalog_release_id", name="uq_catalog_source_entries_id_release"),
        Index(
            "uq_catalog_source_entries_release_serial",
            "catalog_release_id",
            "official_serial",
            unique=True,
            **_partial("official_serial IS NOT NULL"),
        ),
        Index("ix_catalog_source_entries_release_word", "catalog_release_id", "raw_word"),
        CheckConstraint(
            "length(trim(source_record_id_type)) > 0", name="ck_catalog_source_entries_id_type"
        ),
        CheckConstraint(
            "length(trim(source_record_id_value)) > 0", name="ck_catalog_source_entries_id_value"
        ),
        CheckConstraint("length(trim(raw_word)) > 0", name="ck_catalog_source_entries_raw_word"),
        CheckConstraint(
            "length(trim(raw_pinyin)) > 0", name="ck_catalog_source_entries_raw_pinyin"
        ),
        CheckConstraint(
            "official_serial IS NULL OR official_serial > 0",
            name="ck_catalog_source_entries_serial_positive",
        ),
        CheckConstraint(
            "length(payload_sha256) = 64", name="ck_catalog_source_entries_payload_sha256"
        ),
        CheckConstraint(
            _in("review_status", SOURCE_REVIEW_STATUSES),
            name="ck_catalog_source_entries_review_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    catalog_release_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("catalog_releases.id", ondelete="RESTRICT"), nullable=False
    )
    source_record_id_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_record_id_value: Mapped[str] = mapped_column(String(255), nullable=False)
    official_serial: Mapped[int | None] = mapped_column(Integer)
    raw_word: Mapped[str] = mapped_column(String(255), nullable=False)
    raw_pinyin: Mapped[str] = mapped_column(String(255), nullable=False)
    raw_pos: Mapped[str | None] = mapped_column(String(64))
    raw_level_name: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_payload: Mapped[dict] = mapped_column(JSONType, nullable=False)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    search_pinyin: Mapped[str] = mapped_column(String(255), nullable=False)
    review_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", server_default="pending"
    )
    review_flags: Mapped[list[str]] = mapped_column(
        JSONType, nullable=False, default=list, server_default=text("'[]'")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    release: Mapped[CatalogRelease] = relationship()
    levels: Mapped[list["CatalogSourceEntryLevel"]] = relationship(
        order_by="CatalogSourceEntryLevel.order_index", viewonly=True
    )
    mappings: Mapped[list["CatalogSourceMapping"]] = relationship(
        order_by="CatalogSourceMapping.order_index", viewonly=True
    )


class CatalogSourceEntryLevel(Base):
    __tablename__ = "catalog_source_entry_levels"
    __table_args__ = (
        ForeignKeyConstraint(
            ["source_entry_id", "catalog_release_id"],
            ["catalog_source_entries.id", "catalog_source_entries.catalog_release_id"],
            ondelete="CASCADE",
            name="fk_source_levels_source_release",
        ),
        CheckConstraint(_in("level_code", CATALOG_LEVEL_CODES), name="ck_source_levels_level_code"),
        CheckConstraint(_in("role", LEVEL_ROLES), name="ck_source_levels_role"),
        CheckConstraint("order_index >= 0", name="ck_source_levels_order"),
        CheckConstraint(
            "(role = 'primary') = (order_index = 0)", name="ck_source_levels_primary_first"
        ),
        UniqueConstraint("source_entry_id", "order_index", name="uq_source_levels_order"),
        Index(
            "uq_source_levels_one_primary",
            "source_entry_id",
            unique=True,
            **_partial("role = 'primary'"),
        ),
        Index("ix_source_levels_release_level_role", "catalog_release_id", "level_code", "role"),
    )

    source_entry_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    level_code: Mapped[str] = mapped_column(String(16), primary_key=True)
    catalog_release_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)


class LexicalEntry(Base):
    __tablename__ = "lexical_entries"
    __table_args__ = (
        UniqueConstraint("language_id", "lexical_key", name="uq_lexical_entries_language_key"),
        CheckConstraint("length(trim(lexical_key)) > 0", name="ck_lexical_entries_key"),
        CheckConstraint("length(trim(headword)) > 0", name="ck_lexical_entries_headword"),
        CheckConstraint(_in("status", LEXICAL_STATUSES), name="ck_lexical_entries_status"),
        Index("ix_lexical_entries_headword", "language_id", "headword"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    language_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("languages.id", ondelete="RESTRICT"), nullable=False
    )
    lexical_key: Mapped[str] = mapped_column(String(128), nullable=False)
    headword: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="active", server_default="active"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    pronunciations: Mapped[list["LexicalPronunciation"]] = relationship(
        order_by="LexicalPronunciation.order_index", viewonly=True
    )
    senses: Mapped[list["LexicalSense"]] = relationship(
        order_by="LexicalSense.order_index", viewonly=True
    )
    variants: Mapped[list["LexicalVariant"]] = relationship(
        order_by="LexicalVariant.order_index", viewonly=True
    )


class LexicalPronunciation(Base):
    __tablename__ = "lexical_pronunciations"
    __table_args__ = (
        UniqueConstraint("lexical_entry_id", "pinyin", name="uq_lexical_pronunciations_pinyin"),
        UniqueConstraint("id", "lexical_entry_id", name="uq_lexical_pronunciations_id_lexical"),
        CheckConstraint("length(trim(pinyin)) > 0", name="ck_lexical_pronunciations_pinyin"),
        CheckConstraint("order_index >= 0", name="ck_lexical_pronunciations_order"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    lexical_entry_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("lexical_entries.id", ondelete="CASCADE"), nullable=False
    )
    pinyin: Mapped[str] = mapped_column(String(255), nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class LexicalSense(Base):
    __tablename__ = "lexical_senses"
    __table_args__ = (
        UniqueConstraint("lexical_entry_id", "sense_key", name="uq_lexical_senses_key"),
        UniqueConstraint("id", "lexical_entry_id", name="uq_lexical_senses_id_lexical"),
        CheckConstraint("length(trim(sense_key)) > 0", name="ck_lexical_senses_key"),
        CheckConstraint(
            "gloss_en IS NOT NULL OR gloss_vi IS NOT NULL", name="ck_lexical_senses_has_gloss"
        ),
        CheckConstraint(
            "gloss_en IS NULL OR length(trim(gloss_en)) > 0", name="ck_lexical_senses_gloss_en"
        ),
        CheckConstraint(
            "gloss_vi IS NULL OR length(trim(gloss_vi)) > 0", name="ck_lexical_senses_gloss_vi"
        ),
        CheckConstraint(
            "length(trim(gloss_source)) > 0", name="ck_lexical_senses_gloss_source"
        ),
        CheckConstraint(
            _in("review_status", SENSE_REVIEW_STATUSES), name="ck_lexical_senses_review_status"
        ),
        CheckConstraint(_in("status", SENSE_STATUSES), name="ck_lexical_senses_status"),
        CheckConstraint("order_index >= 0", name="ck_lexical_senses_order"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    lexical_entry_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("lexical_entries.id", ondelete="CASCADE"), nullable=False
    )
    sense_key: Mapped[str] = mapped_column(String(64), nullable=False)
    gloss_en: Mapped[str | None] = mapped_column(Text)
    gloss_vi: Mapped[str | None] = mapped_column(Text)
    gloss_source: Mapped[str] = mapped_column(String(120), nullable=False)
    review_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="draft", server_default="draft"
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="active", server_default="active"
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    pos: Mapped[list["LexicalSensePos"]] = relationship(viewonly=True)
    pronunciation_links: Mapped[list["LexicalSensePronunciation"]] = relationship(viewonly=True)
    examples: Mapped[list["LexicalSenseExample"]] = relationship(
        order_by="LexicalSenseExample.order_index", viewonly=True
    )


class LexicalSensePos(Base):
    __tablename__ = "lexical_sense_pos"
    __table_args__ = (
        CheckConstraint(_in("pos_code", POS_CODES), name="ck_lexical_sense_pos_code"),
        CheckConstraint(_in("pos_origin", POS_ORIGINS), name="ck_lexical_sense_pos_origin"),
        CheckConstraint(
            "source_label IS NULL OR length(trim(source_label)) > 0",
            name="ck_lexical_sense_pos_source_label",
        ),
    )

    sense_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("lexical_senses.id", ondelete="CASCADE"), primary_key=True
    )
    pos_code: Mapped[str] = mapped_column(String(32), primary_key=True)
    pos_origin: Mapped[str] = mapped_column(String(20), nullable=False)
    source_label: Mapped[str | None] = mapped_column(String(32))


class LexicalSensePronunciation(Base):
    __tablename__ = "lexical_sense_pronunciations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["sense_id", "lexical_entry_id"],
            ["lexical_senses.id", "lexical_senses.lexical_entry_id"],
            ondelete="CASCADE",
            name="fk_sense_pron_sense_lexical",
        ),
        ForeignKeyConstraint(
            ["pronunciation_id", "lexical_entry_id"],
            ["lexical_pronunciations.id", "lexical_pronunciations.lexical_entry_id"],
            ondelete="CASCADE",
            name="fk_sense_pron_pronunciation_lexical",
        ),
    )

    sense_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    pronunciation_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    lexical_entry_id: Mapped[uuid.UUID] = mapped_column(nullable=False)


class LexicalVariant(Base):
    __tablename__ = "lexical_variants"
    __table_args__ = (
        ForeignKeyConstraint(
            ["pronunciation_id", "lexical_entry_id"],
            ["lexical_pronunciations.id", "lexical_pronunciations.lexical_entry_id"],
            ondelete="CASCADE",
            name="fk_variants_pronunciation_lexical",
        ),
        UniqueConstraint(
            "lexical_entry_id", "variant_form", "variant_type", name="uq_lexical_variants_form"
        ),
        CheckConstraint("length(trim(variant_form)) > 0", name="ck_lexical_variants_form"),
        CheckConstraint(_in("variant_type", VARIANT_TYPES), name="ck_lexical_variants_type"),
        CheckConstraint("length(trim(variant_source)) > 0", name="ck_lexical_variants_source"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    lexical_entry_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("lexical_entries.id", ondelete="CASCADE"), nullable=False
    )
    pronunciation_id: Mapped[uuid.UUID | None] = mapped_column()
    variant_form: Mapped[str] = mapped_column(String(255), nullable=False)
    variant_type: Mapped[str] = mapped_column(String(20), nullable=False)
    variant_source: Mapped[str] = mapped_column(String(120), nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class LexicalSenseExample(Base):
    __tablename__ = "lexical_sense_examples"
    __table_args__ = (
        UniqueConstraint("sense_id", "order_index", name="uq_lexical_sense_examples_order"),
        CheckConstraint("length(trim(text_zh)) > 0", name="ck_lexical_sense_examples_text"),
        CheckConstraint(
            "length(trim(example_source)) > 0", name="ck_lexical_sense_examples_source"
        ),
        CheckConstraint("order_index >= 0", name="ck_lexical_sense_examples_order"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    sense_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("lexical_senses.id", ondelete="CASCADE"), nullable=False
    )
    text_zh: Mapped[str] = mapped_column(Text, nullable=False)
    pinyin: Mapped[str | None] = mapped_column(Text)
    translation_vi: Mapped[str | None] = mapped_column(Text)
    example_source: Mapped[str] = mapped_column(String(120), nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class CatalogSourceMapping(Base):
    __tablename__ = "catalog_source_mappings"
    __table_args__ = (
        ForeignKeyConstraint(
            ["source_entry_id", "catalog_release_id"],
            ["catalog_source_entries.id", "catalog_source_entries.catalog_release_id"],
            ondelete="RESTRICT",
            name="fk_mappings_source_release",
        ),
        ForeignKeyConstraint(
            ["pronunciation_id", "lexical_entry_id"],
            ["lexical_pronunciations.id", "lexical_pronunciations.lexical_entry_id"],
            ondelete="RESTRICT",
            name="fk_mappings_pronunciation_lexical",
        ),
        ForeignKeyConstraint(
            ["sense_id", "lexical_entry_id"],
            ["lexical_senses.id", "lexical_senses.lexical_entry_id"],
            ondelete="RESTRICT",
            name="fk_mappings_sense_lexical",
        ),
        # When both a sense and a reading are named, that pairing must exist.
        ForeignKeyConstraint(
            ["sense_id", "pronunciation_id"],
            ["lexical_sense_pronunciations.sense_id", "lexical_sense_pronunciations.pronunciation_id"],
            ondelete="RESTRICT",
            name="fk_mappings_sense_pronunciation",
        ),
        UniqueConstraint(
            "source_entry_id",
            "lexical_entry_id",
            "pronunciation_id",
            "sense_id",
            name="uq_mappings_interpretation",
            postgresql_nulls_not_distinct=True,
        ),
        UniqueConstraint("id", "source_entry_id", name="uq_mappings_id_source"),
        UniqueConstraint("id", "sense_id", name="uq_mappings_id_sense"),
        CheckConstraint(
            _in("review_status", MAPPING_REVIEW_STATUSES), name="ck_mappings_review_status"
        ),
        CheckConstraint("order_index >= 0", name="ck_mappings_order"),
        Index("ix_mappings_release_source", "catalog_release_id", "source_entry_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    catalog_release_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    source_entry_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    lexical_entry_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("lexical_entries.id", ondelete="RESTRICT"), nullable=False
    )
    pronunciation_id: Mapped[uuid.UUID | None] = mapped_column()
    sense_id: Mapped[uuid.UUID | None] = mapped_column()
    review_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="proposed", server_default="proposed"
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    lexical_entry: Mapped[LexicalEntry] = relationship(viewonly=True)
