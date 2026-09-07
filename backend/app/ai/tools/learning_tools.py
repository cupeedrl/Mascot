from uuid import UUID
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from .schemas import (
    GetLearningStatsArgs,
    LearningStatsResult,
    RecentVocabularyItem,
    GetDueVocabArgs,
    DueVocabularyResult,
    VocabularyItem,
)

# Domain services
from app.services.dashboard import get_dashboard_snapshot
from app.services.review import list_due_vocabularies


def _to_recent_item(vocab) -> RecentVocabularyItem:
    """Map a Vocabulary ORM object to a RecentVocabularyItem schema."""
    return RecentVocabularyItem(
        id=vocab.id,
        word=vocab.word,
        meaning=vocab.meaning,
        translation=vocab.translation,
        created_at=vocab.created_at,
    )


def _to_due_item(vocab) -> VocabularyItem:
    """Map a Vocabulary ORM object to a VocabularyItem schema suitable for due list."""
    return VocabularyItem(
        id=vocab.id,
        word=vocab.word,
        meaning=vocab.meaning,
        translation=vocab.translation,
        learning_status=vocab.learning_status,
        next_review_at=vocab.next_review_at,
        last_reviewed_at=vocab.last_reviewed_at,
    )


def handle_get_learning_stats(
    args: GetLearningStatsArgs,
    db: Session,
    user_id: UUID,
) -> LearningStatsResult:
    """Retrieve the dashboard snapshot for *user_id* and shape it for the tool.

    Only a subset of fields needed by the assistant are exposed.  The
    ``recently_added_vocabulary`` list is trimmed to the first 5 entries to keep
    the payload compact.
    """
    snapshot = get_dashboard_snapshot(db, user_id)
    recent_items = [_to_recent_item(v) for v in snapshot.recently_added_vocabulary[:5]]
    return LearningStatsResult(
        total_vocabulary=snapshot.total_vocabulary,
        new_words=snapshot.new_words,
        learning_words=snapshot.learning_words,
        review_words=snapshot.review_words,
        mastered_words=snapshot.mastered_words,
        words_due_for_review=snapshot.words_due_for_review,
        exercises_completed=snapshot.exercises_completed,
        correct_exercise_attempts=snapshot.correct_exercise_attempts,
        incorrect_exercise_attempts=snapshot.incorrect_exercise_attempts,
        exercise_accuracy=snapshot.exercise_accuracy,
        current_streak=snapshot.current_streak,
        longest_streak=snapshot.longest_streak,
        recent_active_dates=snapshot.recent_active_dates,
        recent_vocabulary=recent_items,
    )


def handle_get_due_vocabulary(
    args: GetDueVocabArgs,
    db: Session,
    user_id: UUID,
) -> DueVocabularyResult:
    """Return a paginated list of vocabularies that are due for review.

    ``list_due_vocabularies`` already applies the ``user_id`` filter, so the
    result is safely scoped.
    """
    queue = list_due_vocabularies(
        db,
        user_id,
        limit=args.limit,
        learning_track_id=None,
        now=datetime.now(timezone.utc),
    )
    items = [_to_due_item(v) for v in queue.items]
    return DueVocabularyResult(items=items, total=queue.total, limit=queue.limit)
