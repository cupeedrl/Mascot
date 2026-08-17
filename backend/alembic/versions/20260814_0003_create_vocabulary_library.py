"""Create shared vocabulary library and link personal vocabulary sources.

Revision ID: 20260814_0003
Revises: 20260814_0002
Create Date: 2026-08-14 00:00:00
"""

import unicodedata
import uuid
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260814_0003"
down_revision: str | Sequence[str] | None = "20260814_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SEED_NAMESPACE = uuid.UUID("7a313c6f-9a8e-4b51-bb7c-ec55b1496c70")

DEMO_SETS = [
    ("a1-daily-life", "A1", "Daily Life", "Daily Life", [
        ("routine", "noun", "The usual order in which you do things.", "thói quen hằng ngày", "Exercise is part of my morning routine."),
        ("breakfast", "noun", "The first meal of the day.", "bữa sáng", "I usually eat breakfast at seven."),
        ("commute", "verb", "To travel regularly between home and work or school.", "đi lại hằng ngày", "She commutes to work by bus."),
        ("neighbor", "noun", "A person who lives near you.", "hàng xóm", "Our neighbor is very friendly."),
        ("relax", "verb", "To rest and become less worried or tired.", "thư giãn", "I relax by listening to music."),
    ]),
    ("a1-family", "A1", "Family", "Family", [
        ("parent", "noun", "A mother or father.", "cha hoặc mẹ", "Her parents live nearby."),
        ("sibling", "noun", "A brother or sister.", "anh chị em ruột", "I have one younger sibling."),
        ("cousin", "noun", "A child of your aunt or uncle.", "anh chị em họ", "My cousin visits us every summer."),
        ("married", "adjective", "Having a husband or wife.", "đã kết hôn", "They have been married for five years."),
        ("support", "verb", "To help or encourage someone.", "hỗ trợ", "My family supports my studies."),
    ]),
    ("a2-travel", "A2", "Travel", "Travel", [
        ("journey", "noun", "The act of travelling from one place to another.", "hành trình", "The train journey took three hours."),
        ("reservation", "noun", "An arrangement to keep a seat or room for you.", "đặt chỗ", "I made a hotel reservation online."),
        ("luggage", "noun", "Bags and cases used while travelling.", "hành lý", "Your luggage is too heavy."),
        ("destination", "noun", "The place to which someone is travelling.", "điểm đến", "Da Nang is our final destination."),
        ("explore", "verb", "To travel around a place to learn about it.", "khám phá", "We explored the old town on foot."),
    ]),
    ("a2-work", "A2", "Work", "Work", [
        ("colleague", "noun", "A person you work with.", "đồng nghiệp", "I discussed the task with a colleague."),
        ("deadline", "noun", "The latest time by which something must be finished.", "hạn chót", "The project deadline is Friday."),
        ("schedule", "noun", "A plan showing when activities will happen.", "lịch trình", "My work schedule changes every week."),
        ("responsibility", "noun", "A duty that you are expected to deal with.", "trách nhiệm", "Managing the team is her responsibility."),
        ("apply", "verb", "To formally ask for a job or opportunity.", "ứng tuyển", "He applied for a new position."),
    ]),
    ("b1-education", "B1", "Education", "Education", [
        ("curriculum", "noun", "The subjects included in a course of study.", "chương trình học", "The school updated its curriculum."),
        ("assignment", "noun", "A piece of work given as part of study.", "bài tập được giao", "The assignment is due next Monday."),
        ("lecture", "noun", "A formal talk given to teach a group.", "bài giảng", "The lecture covered modern history."),
        ("revise", "verb", "To study something again before an examination.", "ôn tập", "I need to revise for the test."),
        ("qualification", "noun", "An official record showing a skill or education level.", "bằng cấp", "This job requires a professional qualification."),
    ]),
    ("b1-communication", "B1", "Communication", "Communication", [
        ("clarify", "verb", "To make something easier to understand.", "làm rõ", "Could you clarify your last point?"),
        ("persuade", "verb", "To make someone agree to do something through reasoning.", "thuyết phục", "She persuaded him to join the course."),
        ("interrupt", "verb", "To stop someone while they are speaking.", "ngắt lời", "Please do not interrupt the speaker."),
        ("gesture", "noun", "A movement that communicates an idea or feeling.", "cử chỉ", "He made a friendly gesture."),
        ("feedback", "noun", "Comments that help someone improve.", "phản hồi", "The teacher gave useful feedback."),
    ]),
    ("b2-work-business", "B2", "Work & Business", "Work & Business", [
        ("negotiate", "verb", "To discuss something in order to reach an agreement.", "đàm phán", "They negotiated a better contract."),
        ("revenue", "noun", "Money received by a business from its activities.", "doanh thu", "Online sales increased company revenue."),
        ("stakeholder", "noun", "A person or group affected by an organization or project.", "bên liên quan", "We invited every stakeholder to the meeting."),
        ("efficient", "adjective", "Working well without wasting time or resources.", "hiệu quả", "The new process is more efficient."),
        ("solely", "adverb", "Only and not involving anyone or anything else.", "chỉ, duy nhất", "The decision was solely hers."),
    ]),
    ("b2-technology", "B2", "Technology", "Technology", [
        ("innovation", "noun", "A new idea, method, or product.", "sự đổi mới", "Innovation drives the technology industry."),
        ("privacy", "noun", "The state of keeping personal information protected.", "quyền riêng tư", "Users are concerned about data privacy."),
        ("automate", "verb", "To use technology to perform a process automatically.", "tự động hóa", "The software automates repetitive tasks."),
        ("reliable", "adjective", "Working well and able to be trusted.", "đáng tin cậy", "We need a reliable internet connection."),
        ("cybersecurity", "noun", "Protection of computer systems and data from attack.", "an ninh mạng", "The company invested in cybersecurity training."),
    ]),
]


def _seed_id(kind: str, value: str) -> uuid.UUID:
    return uuid.uuid5(SEED_NAMESPACE, f"{kind}:{value}")


def _normalize(value: str) -> str:
    return unicodedata.normalize("NFKC", value.strip()).casefold()


def upgrade() -> None:
    vocabulary_sets = op.create_table(
        "vocabulary_sets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("learning_track_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("level_code", sa.String(length=32), nullable=False),
        sa.Column("topic", sa.String(length=120), nullable=False),
        sa.Column("order_index", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("length(trim(name)) > 0", name="ck_vocab_sets_name_not_blank"),
        sa.CheckConstraint("length(trim(level_code)) > 0", name="ck_vocab_sets_level_not_blank"),
        sa.CheckConstraint("length(trim(topic)) > 0", name="ck_vocab_sets_topic_not_blank"),
        sa.CheckConstraint("order_index >= 0", name="ck_vocab_sets_order_nonnegative"),
        sa.ForeignKeyConstraint(["learning_track_id"], ["learning_tracks.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "learning_track_id", "level_code", "topic", name="uq_vocab_sets_track_level_topic"
        ),
    )
    op.create_index(
        "ix_vocab_sets_track_level_active",
        "vocabulary_sets",
        ["learning_track_id", "level_code", "is_active"],
    )
    op.create_index("ix_vocab_sets_topic", "vocabulary_sets", ["topic"])

    vocabulary_entries = op.create_table(
        "vocabulary_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("vocabulary_set_id", sa.Uuid(), nullable=False),
        sa.Column("word", sa.String(length=255), nullable=False),
        sa.Column("normalized_word", sa.String(length=255), nullable=False),
        sa.Column("part_of_speech", sa.String(length=64), nullable=False),
        sa.Column("meaning", sa.Text(), nullable=False),
        sa.Column("translation", sa.Text(), nullable=False),
        sa.Column(
            "translation_language_code",
            sa.String(length=16),
            server_default=sa.text("'vi'"),
            nullable=False,
        ),
        sa.Column(
            "example_sentences",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("order_index", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("length(trim(word)) > 0", name="ck_vocab_entries_word_not_blank"),
        sa.CheckConstraint(
            "length(trim(normalized_word)) > 0", name="ck_vocab_entries_normalized_not_blank"
        ),
        sa.CheckConstraint("length(trim(part_of_speech)) > 0", name="ck_vocab_entries_pos_not_blank"),
        sa.CheckConstraint("length(trim(meaning)) > 0", name="ck_vocab_entries_meaning_not_blank"),
        sa.CheckConstraint("length(trim(translation)) > 0", name="ck_vocab_entries_translation_not_blank"),
        sa.CheckConstraint(
            "jsonb_typeof(example_sentences) = 'array'", name="ck_vocab_entries_examples_array"
        ),
        sa.CheckConstraint("order_index >= 0", name="ck_vocab_entries_order_nonnegative"),
        sa.ForeignKeyConstraint(["vocabulary_set_id"], ["vocabulary_sets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_vocab_entries_set_order", "vocabulary_entries", ["vocabulary_set_id", "order_index"]
    )
    op.create_index("ix_vocab_entries_normalized", "vocabulary_entries", ["normalized_word"])

    op.add_column("vocabularies", sa.Column("source_vocabulary_entry_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_vocab_source_entry",
        "vocabularies",
        "vocabulary_entries",
        ["source_vocabulary_entry_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "uq_vocab_user_source_entry",
        "vocabularies",
        ["user_id", "source_vocabulary_entry_id"],
        unique=True,
        postgresql_where=sa.text("source_vocabulary_entry_id IS NOT NULL"),
    )

    bind = op.get_bind()
    general_track_id = bind.execute(
        sa.text("SELECT id FROM learning_tracks WHERE code = 'general-english'")
    ).scalar_one()

    set_rows = []
    entry_rows = []
    for set_index, (code, level, name, topic, entries) in enumerate(DEMO_SETS):
        set_id = _seed_id("set", code)
        set_rows.append(
            {
                "id": set_id,
                "learning_track_id": general_track_id,
                "name": name,
                "description": f"Demo {level} vocabulary set for development and product evaluation.",
                "level_code": level,
                "topic": topic,
                "order_index": set_index,
                "is_active": True,
            }
        )
        for entry_index, (word, part_of_speech, meaning, translation, example) in enumerate(entries):
            entry_rows.append(
                {
                    "id": _seed_id("entry", f"{code}:{word}:{part_of_speech}"),
                    "vocabulary_set_id": set_id,
                    "word": word,
                    "normalized_word": _normalize(word),
                    "part_of_speech": part_of_speech,
                    "meaning": meaning,
                    "translation": translation,
                    "translation_language_code": "vi",
                    "example_sentences": [example],
                    "order_index": entry_index,
                }
            )

    op.bulk_insert(vocabulary_sets, set_rows)
    op.bulk_insert(vocabulary_entries, entry_rows)


def downgrade() -> None:
    op.drop_index("uq_vocab_user_source_entry", table_name="vocabularies")
    op.drop_constraint("fk_vocab_source_entry", "vocabularies", type_="foreignkey")
    op.drop_column("vocabularies", "source_vocabulary_entry_id")
    op.drop_table("vocabulary_entries")
    op.drop_table("vocabulary_sets")
