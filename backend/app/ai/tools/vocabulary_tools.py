from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.ai.tools.schemas import AddVocabularyArgs, AddVocabularyResult
from app.schemas.vocabulary import VocabularyCreate
from app.services.catalog import list_active_learning_tracks
from app.services.vocabulary import DuplicateVocabularySenseError, create_vocabulary


class AddVocabularyDuplicateError(Exception):
    def __init__(self, existing_vocabulary_id: UUID) -> None:
        self.existing_vocabulary_id = existing_vocabulary_id
        super().__init__("Vocabulary sense already exists")


class DefaultLearningTrackUnavailableError(Exception):
    pass


def handle_add_vocabulary(
    args: AddVocabularyArgs,
    db: Session,
    user_id: UUID,
) -> AddVocabularyResult:
    """Create one vocabulary through the existing domain service."""
    track = next(
        (
            item
            for item in list_active_learning_tracks(db, language_code="en")
            if item.code == "general-english"
        ),
        None,
    )
    if track is None:
        raise DefaultLearningTrackUnavailableError

    payload = VocabularyCreate(
        learning_track_id=track.id,
        **args.model_dump(),
        learning_status="new",
    )
    try:
        item = create_vocabulary(db, user_id, payload)
    except DuplicateVocabularySenseError as exc:
        raise AddVocabularyDuplicateError(exc.existing.id) from exc
    return AddVocabularyResult.model_validate(item)
