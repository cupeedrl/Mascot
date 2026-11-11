"""PostgreSQL 16 integration tests for the normalized HSK catalog.

These run only against a DISPOSABLE PostgreSQL server:

    MASCOT_PG_TEST_ADMIN_URL=postgresql+psycopg://postgres:pw@host:5432/postgres
    MASCOT_PG_TEST_DISPOSABLE=1

Each test creates and drops its own ``mascot_hsk_test_*`` database. Never point
this at a development, Neon, Render or production server.
"""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.catalog import hsk_import
from app.db.session import get_db
from app.main import app
from app.models import (
    CatalogEntryTopic,
    CatalogRelease,
    CatalogSourceEntry,
    CatalogSourceEntryLevel,
    CatalogSourceMapping,
    CatalogTopic,
    LearningTrack,
    LexicalEntry,
    LexicalPronunciation,
    LexicalSense,
    LexicalSensePos,
    LexicalSensePronunciation,
    LexicalVariant,
    Vocabulary,
)
from tests.hsk_fixtures import build_dataset, revised_review
from tests.hsk_scenario import authenticate, import_and_publish, import_dataset, run_learner_flow

ADMIN_URL = os.environ.get("MASCOT_PG_TEST_ADMIN_URL")
pytestmark = pytest.mark.skipif(
    not ADMIN_URL or os.environ.get("MASCOT_PG_TEST_DISPOSABLE") != "1",
    reason="needs a disposable PostgreSQL 16 server (MASCOT_PG_TEST_ADMIN_URL)",
)
BACKEND_DIR = Path(__file__).resolve().parents[2]
HEAD = "20261111_0017"
HSK_BASE = "20261110_0015"
BEFORE = "20260908_0014"
CATALOG_MODELS = (
    CatalogRelease,
    CatalogSourceEntry,
    CatalogSourceEntryLevel,
    CatalogSourceMapping,
    LexicalEntry,
    LexicalPronunciation,
    LexicalSense,
    LexicalSensePos,
    LexicalSensePronunciation,
    LexicalVariant,
    CatalogTopic,
    CatalogEntryTopic,
)


def _alembic(url: str, *args: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "DATABASE_URL": url}
    return subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", *args],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _upgrade(url: str, target: str) -> None:
    result = _alembic(url, "upgrade", target)
    assert result.returncode == 0, result.stderr


@pytest.fixture
def database_url() -> Generator[str, None, None]:
    name = f"mascot_hsk_test_{uuid.uuid4().hex[:12]}"
    admin = create_engine(ADMIN_URL, isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        version = connection.scalar(text("SHOW server_version_num"))
        assert 160000 <= int(version) < 170000, f"expected PostgreSQL 16, got {version}"
        connection.execute(text(f'CREATE DATABASE "{name}"'))
    url = make_url(ADMIN_URL).set(database=name).render_as_string(hide_password=False)
    try:
        yield url
    finally:
        with admin.connect() as connection:
            connection.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        admin.dispose()


@pytest.fixture
def engine(database_url: str) -> Generator[Engine, None, None]:
    _upgrade(database_url, "head")
    engine = create_engine(database_url)
    yield engine
    engine.dispose()


@pytest.fixture
def pg_sessions(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture
def pg_client(pg_sessions: sessionmaker[Session]) -> Generator[TestClient, None, None]:
    def override() -> Generator[Session, None, None]:
        with pg_sessions() as session:
            yield session

    app.dependency_overrides[get_db] = override
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


def _track_id(db: Session) -> uuid.UUID:
    return db.scalar(select(LearningTrack.id).where(LearningTrack.code == "general-chinese"))


# --------------------------------------------------------------------------- migration


def test_single_linear_head() -> None:
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    script = ScriptDirectory.from_config(Config(str(BACKEND_DIR / "alembic.ini")))
    assert script.get_heads() == [HEAD]
    assert script.get_revision(HEAD).down_revision == "20261111_0016"  # usernames + email codes
    assert script.get_revision("20261111_0016").down_revision == HSK_BASE
    assert script.get_revision(HSK_BASE).down_revision == BEFORE


def _legacy_state(connection) -> dict[str, object]:
    return {
        "tables": {
            table: connection.scalar(text(f"SELECT count(*) FROM {table}"))
            for table in (
                "users",
                "vocabulary_sets",
                "vocabulary_entries",
                "vocabularies",
                "exercises",
                "exercise_vocabularies",
                "exercise_attempts",
                "learning_tracks",
                "languages",
            )
        },
        "vocabularies": connection.execute(
            text(
                "SELECT id, word, ipa, part_of_speech, meaning, translation, level_code, topic, "
                "learning_status, review_count, correct_count, incorrect_count, last_reviewed_at, "
                "next_review_at, source_vocabulary_entry_id, example_sentences::text "
                "FROM vocabularies ORDER BY id"
            )
        ).all(),
        "catalog_digest": connection.scalar(
            text(
                "SELECT md5(string_agg(e.id::text || e.word || e.meaning || e.translation, ',' "
                "ORDER BY e.id)) FROM vocabulary_entries e"
            )
        ),
    }


def test_migration_preserves_cefr_chinese_dev_data_and_progress(database_url: str, tmp_path: Path) -> None:
    _upgrade(database_url, BEFORE)
    engine = create_engine(database_url)
    user_id, vocab_id, exercise_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    with engine.begin() as connection:
        cefr_entries = connection.scalar(
            text(
                "SELECT count(*) FROM vocabulary_entries e JOIN vocabulary_sets s "
                "ON s.id = e.vocabulary_set_id WHERE s.level_code IN ('A1','A2','B1','B2','C1','C2')"
            )
        )
        assert cefr_entries > 0
        hsk_dev = connection.scalar(
            text(
                "SELECT count(*) FROM vocabulary_entries e JOIN vocabulary_sets s "
                "ON s.id = e.vocabulary_set_id WHERE s.level_code = 'HSK1'"
            )
        )
        assert hsk_dev == 8
        entry = connection.execute(
            text(
                "SELECT e.id, e.word, e.part_of_speech, e.meaning, e.translation, s.learning_track_id, s.level_code "
                "FROM vocabulary_entries e JOIN vocabulary_sets s ON s.id = e.vocabulary_set_id "
                "WHERE s.level_code = 'A1' ORDER BY e.id LIMIT 1"
            )
        ).one()
        connection.execute(
            text(
                "INSERT INTO users (id, email, normalized_email, password_hash) "
                "VALUES (:id, 'legacy@example.com', 'legacy@example.com', 'x')"
            ),
            {"id": user_id},
        )
        connection.execute(
            text(
                "INSERT INTO vocabularies (id, user_id, learning_track_id, source_vocabulary_entry_id, word, "
                "normalized_word, part_of_speech, meaning, translation, level_code, learning_status, "
                "review_count, correct_count, incorrect_count, last_reviewed_at, next_review_at) VALUES "
                "(:id, :user, :track, :entry, :word, :normalized, :pos, :meaning, :translation, :level, "
                "'learning', 5, 3, 2, now() - interval '1 day', now() + interval '2 days')"
            ),
            {
                "id": vocab_id,
                "user": user_id,
                "track": entry.learning_track_id,
                "entry": entry.id,
                "word": entry.word,
                "normalized": entry.word.lower(),
                "pos": entry.part_of_speech,
                "meaning": entry.meaning,
                "translation": entry.translation,
                "level": entry.level_code,
            },
        )
        connection.execute(
            text(
                "INSERT INTO exercises (id, user_id, learning_track_id, exercise_type, prompt, options, "
                "correct_answer) VALUES (:id, :user, :track, 'multiple_choice', 'Pick', "
                "'[{\"id\":\"A\",\"text\":\"x\"}]', 'A')"
            ),
            {"id": exercise_id, "user": user_id, "track": entry.learning_track_id},
        )
        connection.execute(
            text("INSERT INTO exercise_vocabularies VALUES (:e, :v)"),
            {"e": exercise_id, "v": vocab_id},
        )
        connection.execute(
            text(
                "INSERT INTO exercise_attempts (id, user_id, exercise_id, user_answer, correct_answer, "
                "is_correct) VALUES (:id, :user, :e, 'A', 'A', true)"
            ),
            {"id": uuid.uuid4(), "user": user_id, "e": exercise_id},
        )
    with engine.connect() as connection:
        before = _legacy_state(connection)

    _upgrade(database_url, "head")
    with engine.connect() as connection:
        assert _legacy_state(connection) == before
        assert connection.scalar(text("SELECT count(*) FROM catalog_releases")) == 0
        assert connection.scalar(text("SELECT count(*) FROM catalog_source_entries")) == 0

    # Rollback limit 1: with no catalog saves, downgrade is clean and lossless.
    result = _alembic(database_url, "downgrade", BEFORE)
    assert result.returncode == 0, result.stderr
    with engine.connect() as connection:
        assert _legacy_state(connection) == before
        assert connection.scalar(text("SELECT to_regclass('catalog_releases')")) is None
    _upgrade(database_url, "head")

    # Rollback limit 2: once a learner saved a catalog sense, downgrade refuses.
    sessions = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    import_and_publish(sessions, tmp_path)
    with sessions() as db:
        mapping = db.scalar(
            select(CatalogSourceMapping)
            .join(LexicalSense, LexicalSense.id == CatalogSourceMapping.sense_id)
            .where(LexicalSense.gloss_en == "tea")
        )
        db.add(
            Vocabulary(
                user_id=user_id,
                learning_track_id=_track_id(db),
                catalog_source_entry_id=mapping.source_entry_id,
                catalog_mapping_id=mapping.id,
                catalog_sense_id=mapping.sense_id,
                catalog_pronunciation_id=mapping.pronunciation_id,
                catalog_snapshot={"schema_version": 1},
                word="茶",
                normalized_word="茶",
                part_of_speech="noun",
                meaning="tea",
                translation="trà",
                level_code="HSK5",
            )
        )
        db.commit()
    refused = _alembic(database_url, "downgrade", BEFORE)
    assert refused.returncode != 0
    assert "Refusing to downgrade 20261110_0015" in refused.stderr
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM vocabularies")) == 2
    engine.dispose()


# --------------------------------------------------------------------------- constraints


def _expect_violation(db: Session, constraint: str | tuple[str, ...], statement, params=None) -> None:
    names = (constraint,) if isinstance(constraint, str) else constraint
    savepoint = db.begin_nested()
    with pytest.raises(IntegrityError) as caught:
        db.execute(text(statement) if isinstance(statement, str) else statement, params or {})
        db.flush()
    savepoint.rollback()
    assert caught.value.orig.diag.constraint_name in names, caught.value.orig.diag.constraint_name


def test_postgres_constraints_reject_bad_associations(pg_sessions, tmp_path: Path) -> None:
    import_and_publish(pg_sessions, tmp_path)
    with pg_sessions() as db:
        release = db.scalar(select(CatalogRelease))
        other_release_id = uuid.uuid4()
        db.execute(
            text(
                "INSERT INTO catalog_releases (id, learning_track_id, code, title, source_name, "
                "source_sha256, source_manifest, data_origin) VALUES (:id, :track, 'other', 'Other', "
                "'synthetic', repeat('a', 64), '{}', 'synthetic_fixture')"
            ),
            {"id": other_release_id, "track": release.learning_track_id},
        )
        entries = {e.raw_word: e for e in db.scalars(select(CatalogSourceEntry))}
        lexical = {item.lexical_key: item for item in db.scalars(select(LexicalEntry))}
        pron = {(p.lexical_entry_id, p.pinyin): p.id for p in db.scalars(select(LexicalPronunciation))}
        senses = {(s.lexical_entry_id, s.sense_key): s.id for s in db.scalars(select(LexicalSense))}
        ai, chang, cha = lexical["zh:爱"], lexical["zh:长"], lexical["zh:茶"]
        ai_sense = senses[(ai.id, "s1")]
        long_sense, grow_sense = senses[(chang.id, "long")], senses[(chang.id, "grow")]
        cha_pron = pron[(cha.id, "chá")]

        insert_mapping = (
            "INSERT INTO catalog_source_mappings (id, catalog_release_id, source_entry_id, lexical_entry_id, "
            "pronunciation_id, sense_id, review_status, order_index) VALUES (gen_random_uuid(), :release, "
            ":source, :lexical, :pron, :sense, 'approved', 9)"
        )
        # Cross-release: source entry belongs to another release.
        _expect_violation(db, "fk_mappings_source_release", insert_mapping, {
            "release": other_release_id, "source": entries["爱"].id, "lexical": ai.id, "pron": None, "sense": None})
        # Cross-lexical sense and reading.
        _expect_violation(db, "fk_mappings_sense_lexical", insert_mapping, {
            "release": release.id, "source": entries["爱"].id, "lexical": ai.id, "pron": None, "sense": long_sense})
        _expect_violation(db, "fk_mappings_pronunciation_lexical", insert_mapping, {
            "release": release.id, "source": entries["爱"].id, "lexical": ai.id, "pron": cha_pron, "sense": None})
        # Sense and reading of the same lexical entry that are not linked.
        _expect_violation(db, "fk_mappings_sense_pronunciation", insert_mapping, {
            "release": release.id, "source": entries["长"].id, "lexical": chang.id,
            "pron": pron[(chang.id, "cháng")], "sense": grow_sense})
        # NULLS NOT DISTINCT: a second lexical-only mapping for 朋友 is a duplicate.
        friend = lexical["zh:朋友"]
        _expect_violation(db, "uq_mappings_interpretation", insert_mapping, {
            "release": release.id, "source": entries["朋友"].id, "lexical": friend.id,
            "pron": pron[(friend.id, "péngyou")], "sense": None})
        # Sense–reading link across lexical entries.
        _expect_violation(
            db,
            ("fk_sense_pron_pronunciation_lexical", "fk_sense_pron_sense_lexical"),
            "INSERT INTO lexical_sense_pronunciations VALUES (:sense, :pron, :lexical)",
            {"sense": ai_sense, "pron": cha_pron, "lexical": ai.id},
        )
        # Level membership: cross-release, second primary, invalid level.
        insert_level = (
            "INSERT INTO catalog_source_entry_levels VALUES (:source, :level, :release, :role, :order)"
        )
        _expect_violation(db, "fk_source_levels_source_release", insert_level, {
            "source": entries["爱"].id, "level": "HSK5", "release": other_release_id, "role": "annotation", "order": 5})
        _expect_violation(db, ("uq_source_levels_one_primary", "uq_source_levels_order"), insert_level, {
            "source": entries["长"].id, "level": "HSK5", "release": release.id, "role": "primary", "order": 0})
        _expect_violation(db, "ck_source_levels_level_code", insert_level, {
            "source": entries["爱"].id, "level": "HSK10", "release": release.id, "role": "annotation", "order": 3})
        # Source identity: duplicate official serial within a release.
        _expect_violation(db, "uq_catalog_source_entries_release_serial", text(
            "UPDATE catalog_source_entries SET official_serial = 1 WHERE id = :id"), {"id": entries["水"].id})
        # POS outside the controlled list.
        _expect_violation(db, "ck_lexical_sense_pos_code",
            "INSERT INTO lexical_sense_pos VALUES (:sense, 'verbish', 'editorial', NULL)", {"sense": ai_sense})
        # Release rules: one published release per track; third-party publication gate.
        _expect_violation(db, "uq_catalog_releases_one_published_per_track", text(
            "UPDATE catalog_releases SET status = 'published', published_at = now(), "
            "import_completed_at = now() WHERE id = :id"), {"id": other_release_id})
        _expect_violation(db, "ck_catalog_releases_publication_permissions", text(
            "UPDATE catalog_releases SET data_origin = 'third_party', storage_permission_status = 'unknown' "
            "WHERE id = :id"), {"id": release.id})
        _expect_violation(db, "ck_catalog_releases_published_requires_import", text(
            "UPDATE catalog_releases SET status = 'retired' WHERE id = :id"), {"id": other_release_id})

        # Topics: a word only joins topics of its own level, and a subtopic stays
        # in its parent's level.
        topics = {(t.level_code, t.topic_key): t.id for t in db.scalars(select(CatalogTopic))}
        hsk2_topic = topics[("HSK2", "日常生活/交往")]
        insert_entry_topic = (
            "INSERT INTO catalog_entry_topics VALUES (:source, :topic, :release, :level, 'editorial', 'approved')"
        )
        _expect_violation(db, "fk_entry_topics_topic_release_level", insert_entry_topic, {
            "source": entries["爱"].id, "topic": hsk2_topic, "release": release.id, "level": "HSK1"})
        _expect_violation(db, "fk_entry_topics_level_membership", insert_entry_topic, {
            "source": entries["爱"].id, "topic": hsk2_topic, "release": release.id, "level": "HSK2"})
        _expect_violation(db, "fk_catalog_topics_parent_same_level", text(
            "INSERT INTO catalog_topics VALUES (gen_random_uuid(), :release, 'HSK2', :parent, 2, 'x/y', 'y', NULL, "
            "'mascot', 0)"), {"release": release.id, "parent": topics[("HSK1", "日常生活")]})

        # Personal snapshot guarantees.
        user_id = uuid.uuid4()
        db.execute(text("INSERT INTO users (id, email, normalized_email, password_hash) "
                        "VALUES (:id, 'c@example.com', 'c@example.com', 'x')"), {"id": user_id})
        tea_map = db.scalar(select(CatalogSourceMapping).where(CatalogSourceMapping.source_entry_id == entries["茶"].id))
        long_map = db.scalar(select(CatalogSourceMapping).where(CatalogSourceMapping.sense_id == long_sense))
        insert_vocab = (
            "INSERT INTO vocabularies (id, user_id, learning_track_id, catalog_source_entry_id, catalog_mapping_id, "
            "catalog_sense_id, catalog_pronunciation_id, catalog_snapshot, word, normalized_word, part_of_speech, "
            "meaning, translation, level_code) VALUES (gen_random_uuid(), :user, :track, :source, :mapping, :sense, "
            ":pron, CAST(:snapshot AS jsonb), 'w', 'w', 'noun', 'm', 't', 'HSK5')"
        )
        base = {"user": user_id, "track": release.learning_track_id, "source": entries["茶"].id,
                "mapping": tea_map.id, "sense": tea_map.sense_id, "pron": tea_map.pronunciation_id,
                "snapshot": '{"schema_version": 1}'}
        db.execute(text(insert_vocab), base)
        _expect_violation(db, "uq_vocab_user_catalog_source_sense", insert_vocab, base)
        _expect_violation(db, "ck_vocab_catalog_save_complete", insert_vocab, {**base, "snapshot": None, "user": uuid.uuid4()})
        _expect_violation(db, ("fk_vocab_catalog_mapping_sense", "fk_vocab_catalog_sense_pronunciation"),
                          insert_vocab, {**base, "sense": ai_sense})
        _expect_violation(db, "fk_vocab_catalog_mapping_source", insert_vocab,
                          {**base, "mapping": long_map.id, "sense": long_sense, "pron": None})
        _expect_violation(db, "ck_vocab_single_catalog_origin", text(
            "UPDATE vocabularies SET source_vocabulary_entry_id = (SELECT id FROM vocabulary_entries LIMIT 1) "
            "WHERE user_id = :user"), {"user": user_id})
        # Catalog rows referenced by a snapshot cannot be hard-deleted (retire instead).
        _expect_violation(
            db,
            ("fk_vocab_catalog_sense", "fk_mappings_sense_lexical", "fk_vocab_catalog_mapping_sense",
             "fk_mappings_sense_pronunciation", "fk_vocab_catalog_sense_pronunciation"),
            "DELETE FROM lexical_senses WHERE id = :id",
            {"id": tea_map.sense_id},
        )
        _expect_violation(db, ("fk_vocab_catalog_source_entry", "fk_mappings_source_release"),
                          "DELETE FROM catalog_source_entries WHERE id = :id", {"id": entries["茶"].id})
        db.rollback()


# --------------------------------------------------------------------------- importer


def _identities(db: Session) -> dict[str, set]:
    result = {}
    for model in CATALOG_MODELS:
        keys = [column for column in model.__table__.primary_key.columns]
        result[model.__tablename__] = {tuple(row) for row in db.execute(select(*keys)).all()}
    return result


def test_importer_is_repeatable_and_does_not_publish(pg_sessions, tmp_path: Path) -> None:
    directory = build_dataset(tmp_path / "v1")
    first = import_dataset(pg_sessions, directory)
    with pg_sessions() as db:
        before = _identities(db)
        release = db.get(CatalogRelease, first.release_id)
        assert release.status == "draft"
        assert release.import_report["per_level"]["HSK1"]["source_rows"] == 3
    second = import_dataset(pg_sessions, directory)
    assert second.release_id == first.release_id
    assert second.counts.get("source_entries_inserted", 0) == 0
    assert second.counts.get("mappings_inserted", 0) == 0
    assert second.counts.get("lexical_entries_inserted", 0) == 0
    with pg_sessions() as db:
        after = _identities(db)
        assert after == before
        assert {k: len(v) for k, v in after.items()} == {
            "catalog_releases": 1,
            "catalog_source_entries": 12,
            "catalog_source_entry_levels": 13,
            "catalog_source_mappings": 11,
            "lexical_entries": 10,
            "lexical_pronunciations": 11,
            "lexical_senses": 10,
            "lexical_sense_pos": 8,
            "lexical_sense_pronunciations": 10,
            "lexical_variants": 1,
            "catalog_topics": 7,
            "catalog_entry_topics": 3,
        }
        entry = db.scalar(select(CatalogSourceEntry).where(CatalogSourceEntry.source_record_id_value == "101"))
        assert (entry.source_record_id_value, entry.official_serial, entry.raw_word) == ("101", 1, "爱")
        assert db.scalar(select(func.count()).select_from(Vocabulary)) == 0


def test_third_party_release_without_permissions_cannot_be_published(pg_sessions, tmp_path: Path) -> None:
    permissions = {k: {"status": "unknown"} for k in ("storage", "transformation", "redistribution", "publication")}
    directory = build_dataset(
        tmp_path / "tp", release_code="third-party-draft", data_origin="third_party", permissions=permissions
    )
    import_dataset(pg_sessions, directory)
    with pg_sessions() as db:
        with pytest.raises(hsk_import.ReleaseStateError, match="publication blocked"):
            hsk_import.publish_release(
                db, track_id=_track_id(db), release_code="third-party-draft", allow_awaiting_review=True
            )
        assert db.scalar(select(CatalogRelease.status)) == "draft"


def test_changed_source_requires_new_release(pg_sessions, tmp_path: Path) -> None:
    import_dataset(pg_sessions, build_dataset(tmp_path / "a"))
    from tests.hsk_fixtures import SOURCE_RECORDS

    changed = [dict(r) for r in SOURCE_RECORDS]
    changed[0]["pinyin"] = "ài!"
    with pytest.raises(hsk_import.ReleaseStateError, match="different source file"):
        import_dataset(pg_sessions, build_dataset(tmp_path / "b", records=changed))


# --------------------------------------------------------------------------- learner flow


def test_hsk1_to_6_learner_flow_and_catalog_update_preserve_progress(
    pg_client: TestClient, pg_sessions, tmp_path: Path
) -> None:
    import_and_publish(pg_sessions, tmp_path)
    with pg_sessions() as db:
        track_id = _track_id(db)
    headers = authenticate(pg_client, "pg-learner@example.com")
    ids = run_learner_flow(pg_client, headers, track_id)

    def personal_state():
        with pg_sessions() as db:
            return {
                str(v.id): (
                    v.word, v.ipa, v.part_of_speech, v.meaning, v.translation, v.level_code,
                    v.learning_status, v.review_count, v.correct_count, v.incorrect_count,
                    v.last_reviewed_at, v.next_review_at, v.catalog_snapshot,
                )
                for v in db.scalars(select(Vocabulary))
            }

    before = personal_state()
    with pg_sessions() as db:
        attempts_before = db.scalar(text("SELECT count(*) FROM exercise_attempts"))

    # A later catalog release edits glosses/POS and retires a sense; v1 is retired.
    v2 = build_dataset(tmp_path / "v2", release_code="synthetic-hsk-v2", review=revised_review())
    import_dataset(pg_sessions, v2)
    with pg_sessions() as db:
        hsk_import.publish_release(
            db, track_id=track_id, release_code="synthetic-hsk-v2", allow_awaiting_review=True
        )
        statuses = dict(db.execute(select(CatalogRelease.code, CatalogRelease.status)).all())
        assert statuses == {"synthetic-hsk-v1": "retired", "synthetic-hsk-v2": "published"}
        assert db.scalar(
            select(LexicalSense.gloss_en).join(LexicalEntry).where(LexicalEntry.lexical_key == "zh:爱")
        ) == "to love; to be fond of (revised)"

    assert personal_state() == before
    with pg_sessions() as db:
        assert db.scalar(text("SELECT count(*) FROM exercise_attempts")) == attempts_before

    # Old release entries are no longer browsable, but saved words are intact and reviewable.
    gone = pg_client.get(f"/api/v1/catalog/hsk/{track_id}/entries/{ids['chang_entry_id']}", headers=headers)
    assert gone.status_code == 404
    saved = pg_client.get(f"/api/v1/vocabularies/{ids['grow_vocabulary_id']}", headers=headers).json()
    assert saved["meaning"] == "to grow"
    assert saved["catalog_snapshot"]["release"]["code"] == "synthetic-hsk-v1"
    reviewed = pg_client.post(
        f"/api/v1/vocabularies/{ids['grow_vocabulary_id']}/reviews", headers=headers, json={"is_correct": False}
    )
    assert reviewed.status_code == 200 and reviewed.json()["review_count"] == 1

    # The new release shows the revised gloss, hides the retired sense, and allows a fresh save.
    levels = pg_client.get(f"/api/v1/catalog/hsk/{track_id}/levels", headers=headers).json()
    assert levels["release"]["code"] == "synthetic-hsk-v2"
    listing = pg_client.get(
        f"/api/v1/catalog/hsk/{track_id}/entries", params={"level": "HSK2"}, headers=headers
    ).json()
    chang_v2 = next(item for item in listing["items"] if item["raw_word"] == "长")
    detail = pg_client.get(f"/api/v1/catalog/hsk/{track_id}/entries/{chang_v2['id']}", headers=headers).json()
    assert [s["sense_key"] for s in detail["interpretations"][0]["senses"]] == ["long"]
    long_v2 = detail["interpretations"][0]["senses"][0]
    assert long_v2["saved_vocabulary_id"] == ids["long_vocabulary_id"]
    resave = pg_client.post(
        f"/api/v1/catalog/hsk/{track_id}/entries/{chang_v2['id']}/save",
        headers=headers,
        json={"mapping_id": long_v2["mapping_id"]},
    )
    assert resave.json() == {
        "created": False, "vocabulary_id": ids["long_vocabulary_id"], "reason": "already_saved"
    }
    with pg_sessions() as db:
        assert db.scalar(select(func.count()).select_from(Vocabulary)) == len(before)
