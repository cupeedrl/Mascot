from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.learning_levels import get_level_codes, is_valid_level
from app.models.language import Language
from app.models.learning_track import LearningTrack
from app.models.user_learning_preference import UserLearningPreference


class LearningPreferenceTrackUnavailableError(Exception):
    pass


class InvalidLearningPreferenceLevelError(Exception):
    pass


@dataclass(frozen=True)
class LearningPreferenceSnapshot:
    learning_track_id: uuid.UUID
    framework: str
    current_level_code: str | None
    level_codes: list[str]


def _load_active_track(db: Session, learning_track_id: uuid.UUID) -> LearningTrack:
    track = db.scalar(
        select(LearningTrack)
        .join(LearningTrack.language)
        .options(joinedload(LearningTrack.language))
        .where(
            LearningTrack.id == learning_track_id,
            LearningTrack.is_active.is_(True),
            Language.is_active.is_(True),
        )
    )
    if track is None:
        raise LearningPreferenceTrackUnavailableError
    return track


def get_stored_current_level(
    db: Session, user_id: uuid.UUID, learning_track_id: uuid.UUID
) -> str | None:
    return db.scalar(
        select(UserLearningPreference.current_level_code).where(
            UserLearningPreference.user_id == user_id,
            UserLearningPreference.learning_track_id == learning_track_id,
        )
    )


def _snapshot(
    track: LearningTrack, current_level_code: str | None
) -> LearningPreferenceSnapshot:
    return LearningPreferenceSnapshot(
        learning_track_id=track.id,
        framework=track.level_framework,
        current_level_code=current_level_code,
        level_codes=list(get_level_codes(track.level_framework)),
    )


def get_learning_preference(
    db: Session, user_id: uuid.UUID, learning_track_id: uuid.UUID
) -> LearningPreferenceSnapshot:
    track = _load_active_track(db, learning_track_id)
    return _snapshot(track, get_stored_current_level(db, user_id, track.id))


def set_learning_preference(
    db: Session,
    user_id: uuid.UUID,
    learning_track_id: uuid.UUID,
    current_level_code: str | None,
) -> LearningPreferenceSnapshot:
    track = _load_active_track(db, learning_track_id)
    normalized_level = (
        current_level_code.strip().upper() if current_level_code is not None else None
    )
    if normalized_level is not None and not is_valid_level(
        track.level_framework, normalized_level
    ):
        raise InvalidLearningPreferenceLevelError

    preference = db.scalar(
        select(UserLearningPreference).where(
            UserLearningPreference.user_id == user_id,
            UserLearningPreference.learning_track_id == track.id,
        )
    )
    if preference is None:
        preference = UserLearningPreference(
            user_id=user_id,
            learning_track_id=track.id,
            current_level_code=normalized_level,
        )
        db.add(preference)
    else:
        preference.current_level_code = normalized_level
    db.commit()
    return _snapshot(track, normalized_level)
