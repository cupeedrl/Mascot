from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.ai_conversation import (
    AIConversationDetailResponse,
    AIConversationSummaryResponse,
)
from app.services.ai_conversation import (
    AIConversationNotFoundError,
    create_conversation,
    delete_owned_conversation,
    get_owned_conversation,
    list_conversation_messages,
    list_owned_conversations,
)

router = APIRouter(prefix="/ai/conversations", tags=["ai"])


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="AI conversation not found.")


@router.get("", response_model=list[AIConversationSummaryResponse])
def list_conversations(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[AIConversationSummaryResponse]:
    return list_owned_conversations(db, current_user.id)


@router.post(
    "", response_model=AIConversationSummaryResponse, status_code=status.HTTP_201_CREATED
)
def create_new_conversation(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> AIConversationSummaryResponse:
    return create_conversation(db, current_user.id)


@router.get("/{conversation_id}", response_model=AIConversationDetailResponse)
def get_conversation(
    conversation_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> AIConversationDetailResponse:
    try:
        conversation = get_owned_conversation(db, current_user.id, conversation_id)
    except AIConversationNotFoundError as exc:
        raise _not_found() from exc
    return AIConversationDetailResponse.model_validate(
        {
            "id": conversation.id,
            "title": conversation.title,
            "created_at": conversation.created_at,
            "updated_at": conversation.updated_at,
            "messages": list_conversation_messages(db, conversation.id),
        }
    )


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(
    conversation_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    try:
        conversation = get_owned_conversation(db, current_user.id, conversation_id)
    except AIConversationNotFoundError as exc:
        raise _not_found() from exc
    delete_owned_conversation(db, conversation)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
