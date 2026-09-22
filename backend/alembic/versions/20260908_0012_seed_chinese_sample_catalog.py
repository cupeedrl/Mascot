"""Seed a small Mandarin HSK development catalog.

Revision ID: 20260908_0012
Revises: 20260908_0011
Create Date: 2026-09-08 01:00:00
"""

from collections.abc import Sequence
import uuid

import sqlalchemy as sa
from alembic import op

revision: str = "20260908_0012"
down_revision: str | Sequence[str] | None = "20260908_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SEED_NAMESPACE = uuid.UUID("7a313c6f-9a8e-4b51-bb7c-ec55b1496c70")
TRACK_ID = uuid.UUID("44444444-4444-4444-8444-444444444444")
SET_CODE = "hsk1-daily-foundations"
SET_ID = uuid.uuid5(SEED_NAMESPACE, f"set:{TRACK_ID}:{SET_CODE}")

ENTRIES = (
    ("学习", "verb", "xuéxí", "to study or learn", "học tập", "我每天学习中文。"),
    ("你好", "phrase", "nǐ hǎo", "a common greeting", "xin chào", "你好，很高兴认识你。"),
    ("谢谢", "phrase", "xièxie", "to express gratitude", "cảm ơn", "谢谢你的帮助。"),
    ("水", "noun", "shuǐ", "water", "nước", "我想喝水。"),
    ("吃", "verb", "chī", "to eat", "ăn", "我们一起吃饭吧。"),
    ("家", "noun", "jiā", "home or family", "nhà, gia đình", "我的家在河内。"),
    ("朋友", "noun", "péngyou", "a friend", "bạn bè", "他是我的朋友。"),
    ("喜欢", "verb", "xǐhuan", "to like", "thích", "我喜欢喝茶。"),
)


def _entry_id(word: str, part_of_speech: str) -> uuid.UUID:
    return uuid.uuid5(
        SEED_NAMESPACE,
        f"entry:{TRACK_ID}:{SET_CODE}:{word}:{part_of_speech}",
    )


def upgrade() -> None:
    connection = op.get_bind()
    vocabulary_sets = sa.table(
        "vocabulary_sets",
        sa.column("id", sa.Uuid()),
        sa.column("learning_track_id", sa.Uuid()),
        sa.column("name", sa.String()),
        sa.column("description", sa.String()),
        sa.column("level_code", sa.String()),
        sa.column("topic", sa.String()),
        sa.column("order_index", sa.Integer()),
        sa.column("is_active", sa.Boolean()),
    )
    vocabulary_entries = sa.table(
        "vocabulary_entries",
        sa.column("id", sa.Uuid()),
        sa.column("vocabulary_set_id", sa.Uuid()),
        sa.column("word", sa.String()),
        sa.column("normalized_word", sa.String()),
        sa.column("ipa", sa.String()),
        sa.column("part_of_speech", sa.String()),
        sa.column("meaning", sa.String()),
        sa.column("translation", sa.String()),
        sa.column("translation_language_code", sa.String()),
        sa.column("example_sentences", sa.JSON()),
        sa.column("order_index", sa.Integer()),
    )
    if connection.scalar(
        sa.select(vocabulary_sets.c.id).where(vocabulary_sets.c.id == SET_ID)
    ) is None:
        connection.execute(
            vocabulary_sets.insert().values(
                id=SET_ID,
                learning_track_id=TRACK_ID,
                name="HSK 1 · Daily Foundations",
                description="A small reviewed starter set for basic Mandarin learning flows.",
                level_code="HSK1",
                topic="Daily Life",
                order_index=0,
                is_active=True,
            )
        )
    for index, (word, part_of_speech, pinyin, meaning, translation, example) in enumerate(ENTRIES):
        entry_id = _entry_id(word, part_of_speech)
        if connection.scalar(
            sa.select(vocabulary_entries.c.id).where(vocabulary_entries.c.id == entry_id)
        ) is None:
            connection.execute(
                vocabulary_entries.insert().values(
                    id=entry_id,
                    vocabulary_set_id=SET_ID,
                    word=word,
                    normalized_word=word.casefold(),
                    ipa=pinyin,
                    part_of_speech=part_of_speech,
                    meaning=meaning,
                    translation=translation,
                    translation_language_code="vi",
                    example_sentences=[example],
                    order_index=index,
                )
            )


def downgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text("DELETE FROM vocabulary_entries WHERE vocabulary_set_id = :set_id"),
        {"set_id": SET_ID},
    )
    connection.execute(
        sa.text("DELETE FROM vocabulary_sets WHERE id = :set_id"),
        {"set_id": SET_ID},
    )
