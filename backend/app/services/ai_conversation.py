from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ai_conversation import AIConversation, AIMessage

DEFAULT_CONVERSATION_TITLE = "New conversation"
MAX_CONVERSATION_TITLE_LENGTH = 120


class AIConversationNotFoundError(Exception):
    pass


def derive_conversation_title(content: str) -> str:
    normalized = re.sub(r"\s+", " ", content).strip()
    if not normalized:
        return DEFAULT_CONVERSATION_TITLE
    if len(normalized) <= MAX_CONVERSATION_TITLE_LENGTH:
        return normalized
    return f"{normalized[: MAX_CONVERSATION_TITLE_LENGTH - 3].rstrip()}..."


def create_conversation(db: Session, user_id: uuid.UUID) -> AIConversation:
    conversation = AIConversation(user_id=user_id, title=DEFAULT_CONVERSATION_TITLE)
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


def get_owned_conversation(
    db: Session, user_id: uuid.UUID, conversation_id: uuid.UUID
) -> AIConversation:
    conversation = db.scalar(
        select(AIConversation).where(
            AIConversation.id == conversation_id,
            AIConversation.user_id == user_id,
        )
    )
    if conversation is None:
        raise AIConversationNotFoundError
    return conversation


def list_owned_conversations(db: Session, user_id: uuid.UUID) -> list[AIConversation]:
    return list(
        db.scalars(
            select(AIConversation)
            .where(AIConversation.user_id == user_id)
            .order_by(AIConversation.updated_at.desc(), AIConversation.id.desc())
        )
    )


def list_conversation_messages(
    db: Session, conversation_id: uuid.UUID
) -> list[AIMessage]:
    return list(
        db.scalars(
            select(AIMessage)
            .where(AIMessage.conversation_id == conversation_id)
            .order_by(AIMessage.created_at.asc(), AIMessage.id.asc())
        )
    )


def load_recent_conversation_messages(
    db: Session, conversation_id: uuid.UUID, limit: int
) -> list[AIMessage]:
    newest_first = list(
        db.scalars(
            select(AIMessage)
            .where(AIMessage.conversation_id == conversation_id)
            .order_by(AIMessage.created_at.desc(), AIMessage.id.desc())
            .limit(limit)
        )
    )
    newest_first.reverse()
    return newest_first


def append_visible_messages(
    db: Session,
    conversation: AIConversation,
    messages: list[tuple[str, str]],
) -> list[AIMessage]:
    created: list[AIMessage] = []
    timestamp = datetime.now(timezone.utc)
    for index, (role, content) in enumerate(messages):
        message = AIMessage(
            conversation_id=conversation.id,
            role=role,
            content=content,
            created_at=timestamp + timedelta(microseconds=index),
        )
        db.add(message)
        created.append(message)

    if conversation.title == DEFAULT_CONVERSATION_TITLE:
        first_user_content = next(
            (content for role, content in messages if role == "user"), None
        )
        if first_user_content is not None:
            conversation.title = derive_conversation_title(first_user_content)
    conversation.updated_at = datetime.now(timezone.utc)
    db.commit()
    for message in created:
        db.refresh(message)
    db.refresh(conversation)
    return created


def delete_owned_conversation(db: Session, conversation: AIConversation) -> None:
    db.delete(conversation)
    db.commit()
