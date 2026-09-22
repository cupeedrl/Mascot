from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.language import Language
from app.models.learning_track import LearningTrack


def list_active_languages(db: Session) -> list[Language]:
    return list(
        db.scalars(
            select(Language)
            .where(Language.is_active.is_(True))
            .order_by(Language.name)
        )
    )


def list_active_learning_tracks(
    db: Session, language_code: str | None = None
) -> list[LearningTrack]:
    statement = (
        select(LearningTrack)
        .join(LearningTrack.language)
        .options(joinedload(LearningTrack.language))
        .where(
            LearningTrack.is_active.is_(True),
            Language.is_active.is_(True),
        )
        .order_by(Language.name, LearningTrack.name)
    )
    if language_code:
        statement = statement.where(Language.code == language_code.strip().lower())
    return list(db.scalars(statement))
