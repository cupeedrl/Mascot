from __future__ import annotations

import pathlib
import uuid
import pytest
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.catalog.constants import (
    CATALOG_CEFR_LEVELS,
    CATALOG_PARTS_OF_SPEECH,
    RECOMMENDED_TOPIC_POOL,
)
from app.catalog.loader import (
    load_catalog_from_dir,
    load_catalog_into_db,
    seed_entry_id,
    seed_set_id,
)
from app.catalog.schema import CatalogEntrySeed, CatalogSetSeed
from app.catalog.validator import validate_catalog_dataset
from app.models.vocabulary import Vocabulary
from app.models.vocabulary_entry import VocabularyEntry
from app.models.vocabulary_set import VocabularySet
from tests.test_vocabulary import authenticate, create_item, general_english_track_id


def test_valid_catalog_entry_creation() -> None:
    entry = CatalogEntrySeed(
        word="diligent",
        part_of_speech="adjective",
        ipa="/ˈdɪl.ɪ.dʒənt/",
        meaning="Having or showing care and conscientiousness in one's work.",
        translation="chăm chỉ, cần cù",
        example_sentences=["She is a diligent student."],
    )
    assert entry.word == "diligent"
    assert entry.part_of_speech == "adjective"
    assert entry.ipa == "/ˈdɪl.ɪ.dʒənt/"
    assert len(entry.example_sentences) == 1


def test_invalid_cefr_level_rejected() -> None:
    with pytest.raises(ValidationError) as exc:
        CatalogSetSeed(
            code="x1-invalid",
            level_code="Z9",
            topic="Daily Life",
            entries=[],
        )
    assert "Invalid CEFR level" in str(exc.value)


def test_invalid_part_of_speech_rejected() -> None:
    with pytest.raises(ValidationError) as exc:
        CatalogEntrySeed(
            word="test",
            part_of_speech="not_a_valid_pos",
            ipa="/test/",
            meaning="A procedure for critical evaluation.",
            translation="bài kiểm tra",
            example_sentences=["This is a test."],
        )
    assert "Invalid part of speech" in str(exc.value)


def test_missing_or_blank_ipa_rejected() -> None:
    with pytest.raises(ValidationError) as exc:
        CatalogEntrySeed(
            word="test",
            part_of_speech="noun",
            ipa="   ",
            meaning="A test.",
            translation="bài kiểm tra",
            example_sentences=["This is a test."],
        )
    assert "IPA" in str(exc.value)


def test_more_than_one_example_sentence_rejected() -> None:
    with pytest.raises(ValidationError) as exc:
        CatalogEntrySeed(
            word="test",
            part_of_speech="noun",
            ipa="/test/",
            meaning="A test.",
            translation="bài kiểm tra",
            example_sentences=["First example sentence.", "Second sentence."],
        )
    assert "exactly one" in str(exc.value)


def test_validator_detects_duplicate_senses() -> None:
    sets = [
        CatalogSetSeed(
            code="set-a",
            level_code="A1",
            topic="Daily Life",
            entries=[
                CatalogEntrySeed(
                    word="tidy",
                    part_of_speech="verb",
                    ipa="/ˈtaɪ.di/",
                    meaning="To make a place clean.",
                    translation="dọn dẹp",
                    example_sentences=["I tidy my room."],
                ),
            ],
        ),
        CatalogSetSeed(
            code="set-b",
            level_code="A2",
            topic="Home",
            entries=[
                CatalogEntrySeed(
                    word="tidy",
                    part_of_speech="verb",
                    ipa="/ˈtaɪ.di/",
                    meaning="To clean up.",
                    translation="dọn dẹp",
                    example_sentences=["He tidies his desk."],
                ),
            ],
        ),
    ]
    result = validate_catalog_dataset(sets)
    assert not result.is_valid
    assert any("Duplicate entry sense" in err for err in result.errors)


def test_validator_allows_different_senses_of_same_word() -> None:
    sets = [
        CatalogSetSeed(
            code="a1-bank-nature",
            level_code="A1",
            topic="Daily Life",
            entries=[
                CatalogEntrySeed(
                    word="bank",
                    part_of_speech="noun",
                    ipa="/bæŋk/",
                    meaning="The land alongside or sloping down to a river or lake.",
                    translation="bờ sông",
                    example_sentences=["They sat on the river bank."],
                ),
            ],
        ),
        CatalogSetSeed(
            code="a2-bank-finance",
            level_code="A2",
            topic="Shopping",
            entries=[
                CatalogEntrySeed(
                    word="bank",
                    part_of_speech="noun",
                    ipa="/bæŋk/",
                    meaning="A financial establishment that invests money and pays interest.",
                    translation="ngân hàng",
                    example_sentences=["I went to the bank to deposit money."],
                ),
            ],
        ),
    ]
    result = validate_catalog_dataset(sets)
    assert result.is_valid
    assert len(result.errors) == 0


def test_initial_catalog_data_files_pass_validation() -> None:
    data_dir = pathlib.Path(__file__).parent.parent / "app" / "catalog" / "data"
    sets = load_catalog_from_dir(data_dir)
    assert len(sets) >= 6
    result = validate_catalog_dataset(sets)
    assert result.is_valid, "\n".join(result.errors)
    assert result.total_entries > 0


def test_idempotent_catalog_db_loading(
    session_factory: sessionmaker[Session],
    general_english_track_id: uuid.UUID,
) -> None:
    data_dir = pathlib.Path(__file__).parent.parent / "app" / "catalog" / "data"
    sets = load_catalog_from_dir(data_dir)

    with session_factory() as db:
        first_result = load_catalog_into_db(db, sets, track_id=general_english_track_id)
        assert first_result.sets_created > 0
        assert first_result.entries_created > 0

        # Rerun to test idempotency
        second_result = load_catalog_into_db(db, sets, track_id=general_english_track_id)
        assert second_result.sets_created == 0
        assert second_result.entries_created == 0
        assert second_result.sets_updated == first_result.sets_created
        assert second_result.entries_updated == first_result.entries_created


def test_catalog_seed_never_mutates_or_deletes_user_vocabulary(
    session_factory: sessionmaker[Session],
    general_english_track_id: uuid.UUID,
) -> None:
    user_id = uuid.uuid4()
    with session_factory() as db:
        # Create a user custom vocabulary
        user_vocab = Vocabulary(
            user_id=user_id,
            learning_track_id=general_english_track_id,
            word="custom_user_word",
            normalized_word="custom_user_word",
            ipa="/ˈkʌs.təm/",
            part_of_speech="noun",
            meaning="A user created word.",
            translation="từ cá nhân",
            translation_language_code="vi",
            example_sentences=["A custom user sentence."],
            level_code="B1",
            topic="Work",
            learning_status="learning",
        )
        db.add(user_vocab)
        db.commit()

        # Load catalog sets
        data_dir = pathlib.Path(__file__).parent.parent / "app" / "catalog" / "data"
        sets = load_catalog_from_dir(data_dir)
        load_catalog_into_db(db, sets, track_id=general_english_track_id)

        # Confirm user vocabulary still exists intact
        refreshed = db.get(Vocabulary, user_vocab.id)
        assert refreshed is not None
        assert refreshed.word == "custom_user_word"
        assert refreshed.learning_status == "learning"


def test_catalog_loader_query_count_is_batched(
    session_factory: sessionmaker[Session],
    general_english_track_id: uuid.UUID,
) -> None:
    data_dir = pathlib.Path(__file__).parent.parent / "app" / "catalog" / "data"
    sets = load_catalog_from_dir(data_dir)
    total_entries = sum(len(s.entries) for s in sets)
    assert total_entries >= 2000

    from sqlalchemy import event

    with session_factory() as db:
        engine = db.get_bind()
        query_count = 0

        def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            nonlocal query_count
            query_count += 1

        event.listen(engine, "before_cursor_execute", before_cursor_execute)
        try:
            # 1. Initial bulk load
            res1 = load_catalog_into_db(db, sets, track_id=general_english_track_id)
            assert res1.entries_created == total_entries
            # Query count must be bounded and small (batch size 500), NOT ~2400+ per-entry SELECTs
            assert query_count < 30, f"Expected < 30 queries, got {query_count}"

            # 2. Idempotent re-run
            query_count = 0
            res2 = load_catalog_into_db(db, sets, track_id=general_english_track_id)
            assert res2.entries_created == 0
            assert res2.entries_updated == total_entries
            assert query_count < 30, f"Expected < 30 queries on rerun, got {query_count}"
        finally:
            event.remove(engine, "before_cursor_execute", before_cursor_execute)

