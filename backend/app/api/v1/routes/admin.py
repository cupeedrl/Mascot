from __future__ import annotations

import math
import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin
from app.catalog.constants import CATALOG_PARTS_OF_SPEECH, GENERAL_ENGLISH_TRACK_ID
from app.db.session import get_db
from app.models.exercise_attempt import ExerciseAttempt
from app.models.learning_track import LearningTrack
from app.models.user import User
from app.models.vocabulary import Vocabulary
from app.models.vocabulary_entry import VocabularyEntry
from app.models.vocabulary_set import VocabularySet
from app.schemas.admin import (
    AdminCatalogEntryItem,
    AdminCatalogListResponse,
    AdminCreateCatalogEntryRequest,
    AdminOverviewResponse,
    AdminUpdateCatalogEntryRequest,
    AdminUpdateUserRoleRequest,
    AdminUpdateUserStatusRequest,
    AdminUserDetailResponse,
    AdminUserListItem,
    AdminUserListResponse,
    AdminUserRecentActivityItem,
)
from app.schemas.vocabulary import CEFRLevel
from app.services.dashboard import get_dashboard_snapshot
from app.services.normalization import normalize_word

router = APIRouter(prefix="/admin", tags=["admin"])


# ==========================================
# 1. OVERVIEW
# ==========================================


@router.get("/overview", response_model=AdminOverviewResponse)
def get_admin_overview(
    _admin_user: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> AdminOverviewResponse:
    """Fetch high-level system metrics for administrator dashboard."""
    total_users = db.scalar(select(func.count()).select_from(User)) or 0
    total_catalog_entries = (
        db.scalar(select(func.count()).select_from(VocabularyEntry)) or 0
    )
    total_personal_vocabulary = (
        db.scalar(select(func.count()).select_from(Vocabulary)) or 0
    )
    total_practice_sessions = (
        db.scalar(select(func.count()).select_from(ExerciseAttempt)) or 0
    )

    return AdminOverviewResponse(
        total_users=total_users,
        total_catalog_entries=total_catalog_entries,
        total_personal_vocabulary=total_personal_vocabulary,
        total_practice_sessions=total_practice_sessions,
    )


# ==========================================
# 2. USERS MANAGEMENT
# ==========================================


@router.get("/users", response_model=AdminUserListResponse)
def list_admin_users(
    _admin_user: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    search: Annotated[str | None, Query(max_length=320)] = None,
    role: Annotated[Literal["user", "admin"] | None, Query()] = None,
    status_filter: Annotated[Literal["active", "disabled"] | None, Query(alias="status")] = None,
) -> AdminUserListResponse:
    """List users with server-side pagination, search, filter, and aggregate metrics."""
    # Subqueries to avoid N+1 queries
    vocab_sub = (
        select(Vocabulary.user_id, func.count(Vocabulary.id).label("vocab_count"))
        .group_by(Vocabulary.user_id)
        .subquery()
    )
    attempt_sub = (
        select(
            ExerciseAttempt.user_id,
            func.count(ExerciseAttempt.id).label("practice_count"),
            func.max(ExerciseAttempt.completed_at).label("last_active_at"),
        )
        .group_by(ExerciseAttempt.user_id)
        .subquery()
    )

    query = (
        select(
            User,
            func.coalesce(vocab_sub.c.vocab_count, 0).label("vocab_count"),
            func.coalesce(attempt_sub.c.practice_count, 0).label("practice_count"),
            attempt_sub.c.last_active_at,
        )
        .outerjoin(vocab_sub, User.id == vocab_sub.c.user_id)
        .outerjoin(attempt_sub, User.id == attempt_sub.c.user_id)
    )

    # Base filters
    count_query = select(func.count()).select_from(User)

    if search and search.strip():
        term = f"%{search.strip().lower()}%"
        query = query.where(User.normalized_email.ilike(term))
        count_query = count_query.where(User.normalized_email.ilike(term))

    if role:
        query = query.where(User.role == role)
        count_query = count_query.where(User.role == role)

    if status_filter:
        is_active_val = status_filter == "active"
        query = query.where(User.is_active.is_(is_active_val))
        count_query = count_query.where(User.is_active.is_(is_active_val))

    total = db.scalar(count_query) or 0
    total_pages = max(1, math.ceil(total / page_size))
    offset = (page - 1) * page_size

    results = db.execute(
        query.order_by(User.created_at.desc()).offset(offset).limit(page_size)
    ).all()

    items = [
        AdminUserListItem(
            id=row[0].id,
            email=row[0].email,
            role=row[0].role,
            is_active=row[0].is_active,
            created_at=row[0].created_at,
            last_active_at=row[3],
            personal_vocabulary_count=int(row[1]),
            practice_session_count=int(row[2]),
        )
        for row in results
    ]

    return AdminUserListResponse(
        items=items,
        page=page,
        page_size=page_size,
        total=total,
        total_pages=total_pages,
    )


@router.get("/users/{user_id}", response_model=AdminUserDetailResponse)
def get_admin_user_detail(
    user_id: uuid.UUID,
    _admin_user: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> AdminUserDetailResponse:
    """Fetch user detail, learning activity, and streak statistics."""
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Người dùng không tồn tại."
        )

    snapshot = get_dashboard_snapshot(db, user.id)

    # Fetch last active timestamp
    last_active = db.scalar(
        select(func.max(ExerciseAttempt.completed_at)).where(
            ExerciseAttempt.user_id == user.id
        )
    )

    # Fetch recent 10 exercise attempts for inspection
    recent_attempts = db.scalars(
        select(ExerciseAttempt)
        .where(ExerciseAttempt.user_id == user.id)
        .order_by(ExerciseAttempt.completed_at.desc())
        .limit(10)
    ).all()

    return AdminUserDetailResponse(
        id=user.id,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
        last_active_at=last_active,
        total_vocabulary=snapshot.total_vocabulary,
        learning_words=snapshot.learning_words,
        mastered_words=snapshot.mastered_words,
        exercises_completed=snapshot.exercises_completed,
        exercise_accuracy=snapshot.exercise_accuracy,
        current_streak=snapshot.current_streak,
        longest_streak=snapshot.longest_streak,
        recent_activity=[
            AdminUserRecentActivityItem(
                id=attempt.id,
                exercise_id=attempt.exercise_id,
                is_correct=attempt.is_correct,
                user_answer=attempt.user_answer,
                correct_answer=attempt.correct_answer,
                completed_at=attempt.completed_at,
            )
            for attempt in recent_attempts
        ],
    )


@router.patch("/users/{user_id}/role", response_model=AdminUserListItem)
def update_admin_user_role(
    user_id: uuid.UUID,
    payload: AdminUpdateUserRoleRequest,
    _admin_user: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> AdminUserListItem:
    """Promote or demote user role with last-admin guard."""
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Người dùng không tồn tại."
        )

    if user.role == "admin" and payload.role == "user":
        # Check if this is the last active admin
        other_admins = db.scalar(
            select(func.count())
            .select_from(User)
            .where(
                User.role == "admin",
                User.is_active.is_(True),
                User.id != user.id,
            )
        )
        if not other_admins or other_admins < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Không thể hủy quyền của quản trị viên cuối cùng trong hệ thống.",
            )

    user.role = payload.role
    db.commit()
    db.refresh(user)

    # Return updated item with counts
    vocab_count = (
        db.scalar(
            select(func.count()).select_from(Vocabulary).where(Vocabulary.user_id == user.id)
        )
        or 0
    )
    practice_count = (
        db.scalar(
            select(func.count())
            .select_from(ExerciseAttempt)
            .where(ExerciseAttempt.user_id == user.id)
        )
        or 0
    )
    last_active = db.scalar(
        select(func.max(ExerciseAttempt.completed_at)).where(
            ExerciseAttempt.user_id == user.id
        )
    )

    return AdminUserListItem(
        id=user.id,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
        last_active_at=last_active,
        personal_vocabulary_count=vocab_count,
        practice_session_count=practice_count,
    )


@router.patch("/users/{user_id}/status", response_model=AdminUserListItem)
def update_admin_user_status(
    user_id: uuid.UUID,
    payload: AdminUpdateUserStatusRequest,
    _admin_user: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> AdminUserListItem:
    """Enable or disable user account with last-admin guard."""
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Người dùng không tồn tại."
        )

    if user.role == "admin" and not payload.is_active:
        other_admins = db.scalar(
            select(func.count())
            .select_from(User)
            .where(
                User.role == "admin",
                User.is_active.is_(True),
                User.id != user.id,
            )
        )
        if not other_admins or other_admins < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Không thể vô hiệu hóa tài khoản quản trị viên cuối cùng.",
            )

    user.is_active = payload.is_active
    db.commit()
    db.refresh(user)

    vocab_count = (
        db.scalar(
            select(func.count()).select_from(Vocabulary).where(Vocabulary.user_id == user.id)
        )
        or 0
    )
    practice_count = (
        db.scalar(
            select(func.count())
            .select_from(ExerciseAttempt)
            .where(ExerciseAttempt.user_id == user.id)
        )
        or 0
    )
    last_active = db.scalar(
        select(func.max(ExerciseAttempt.completed_at)).where(
            ExerciseAttempt.user_id == user.id
        )
    )

    return AdminUserListItem(
        id=user.id,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
        last_active_at=last_active,
        personal_vocabulary_count=vocab_count,
        practice_session_count=practice_count,
    )


# ==========================================
# 3. CATALOG MANAGEMENT
# ==========================================


def _get_learning_track(db: Session) -> LearningTrack:
    track = db.scalar(
        select(LearningTrack).where(
            LearningTrack.code == "general-english",
            LearningTrack.is_active.is_(True),
        )
    )
    if track is None:
        track = db.scalar(select(LearningTrack).where(LearningTrack.is_active.is_(True)))
    if track is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Learning track not found.",
        )
    return track


def _get_or_create_set(db: Session, level_code: str, topic: str) -> VocabularySet:
    clean_topic = topic.strip()
    clean_level = level_code.strip().upper()
    track = _get_learning_track(db)

    existing_set = db.scalar(
        select(VocabularySet).where(
            VocabularySet.learning_track_id == track.id,
            VocabularySet.level_code == clean_level,
            VocabularySet.topic == clean_topic,
        )
    )
    if existing_set is not None:
        return existing_set

    # Create new set for this topic and level
    max_order = (
        db.scalar(
            select(func.max(VocabularySet.order_index)).where(
                VocabularySet.learning_track_id == track.id,
                VocabularySet.level_code == clean_level,
            )
        )
        or 0
    )

    new_set = VocabularySet(
        learning_track_id=track.id,
        name=f"{clean_topic} ({clean_level})",
        level_code=clean_level,
        topic=clean_topic,
        order_index=max_order + 1,
        is_active=True,
    )
    db.add(new_set)
    db.flush()
    return new_set


@router.get("/catalog", response_model=AdminCatalogListResponse)
def list_admin_catalog(
    _admin_user: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    search: Annotated[str | None, Query(max_length=255)] = None,
    level: Annotated[CEFRLevel | None, Query()] = None,
    topic: Annotated[str | None, Query(max_length=120)] = None,
    sort_by: Annotated[Literal["word", "level", "created_at"], Query()] = "word",
    sort_order: Annotated[Literal["asc", "desc"], Query()] = "asc",
) -> AdminCatalogListResponse:
    """List shared catalog entries with filtering and server-side pagination."""
    query = select(VocabularyEntry, VocabularySet).join(
        VocabularySet, VocabularyEntry.vocabulary_set_id == VocabularySet.id
    )
    count_query = select(func.count()).select_from(VocabularyEntry).join(
        VocabularySet, VocabularyEntry.vocabulary_set_id == VocabularySet.id
    )

    if search and search.strip():
        term = f"%{normalize_word(search.strip())}%"
        query = query.where(VocabularyEntry.normalized_word.ilike(term))
        count_query = count_query.where(VocabularyEntry.normalized_word.ilike(term))

    if level:
        query = query.where(VocabularySet.level_code == level)
        count_query = count_query.where(VocabularySet.level_code == level)

    if topic and topic.strip():
        topic_term = f"%{topic.strip().lower()}%"
        query = query.where(VocabularySet.topic.ilike(topic_term))
        count_query = count_query.where(VocabularySet.topic.ilike(topic_term))

    total = db.scalar(count_query) or 0
    total_pages = max(1, math.ceil(total / page_size))
    offset = (page - 1) * page_size

    # Sorting
    if sort_by == "level":
        sort_col = VocabularySet.level_code
    elif sort_by == "created_at":
        sort_col = VocabularyEntry.created_at
    else:
        sort_col = VocabularyEntry.word

    order_clause = sort_col.asc() if sort_order == "asc" else sort_col.desc()
    results = db.execute(
        query.order_by(order_clause, VocabularyEntry.id.asc()).offset(offset).limit(page_size)
    ).all()

    items = [
        AdminCatalogEntryItem(
            id=entry.id,
            vocabulary_set_id=entry.vocabulary_set_id,
            word=entry.word,
            ipa=entry.ipa,
            part_of_speech=entry.part_of_speech,
            meaning=entry.meaning,
            translation=entry.translation,
            example_sentences=entry.example_sentences,
            level_code=vset.level_code,
            topic=vset.topic,
            set_name=vset.name,
            order_index=entry.order_index,
            created_at=entry.created_at,
            updated_at=entry.updated_at,
        )
        for entry, vset in results
    ]

    return AdminCatalogListResponse(
        items=items,
        page=page,
        page_size=page_size,
        total=total,
        total_pages=total_pages,
    )


@router.get("/catalog/{entry_id}", response_model=AdminCatalogEntryItem)
def get_admin_catalog_entry(
    entry_id: uuid.UUID,
    _admin_user: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> AdminCatalogEntryItem:
    """Fetch individual catalog entry detail."""
    entry = db.get(VocabularyEntry, entry_id)
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Từ vựng không tồn tại trong thư viện."
        )
    vset = db.get(VocabularySet, entry.vocabulary_set_id)
    if vset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Bộ từ vựng tương ứng không tồn tại."
        )

    return AdminCatalogEntryItem(
        id=entry.id,
        vocabulary_set_id=entry.vocabulary_set_id,
        word=entry.word,
        ipa=entry.ipa,
        part_of_speech=entry.part_of_speech,
        meaning=entry.meaning,
        translation=entry.translation,
        example_sentences=entry.example_sentences,
        level_code=vset.level_code,
        topic=vset.topic,
        set_name=vset.name,
        order_index=entry.order_index,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
    )


@router.post("/catalog", response_model=AdminCatalogEntryItem, status_code=status.HTTP_201_CREATED)
def create_admin_catalog_entry(
    payload: AdminCreateCatalogEntryRequest,
    _admin_user: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> AdminCatalogEntryItem:
    """Create a new catalog entry in the shared vocabulary catalog."""
    clean_word = payload.word.strip()
    norm_word = normalize_word(clean_word)
    clean_pos = payload.part_of_speech.strip().lower()

    if clean_pos not in CATALOG_PARTS_OF_SPEECH:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Từ loại '{payload.part_of_speech}' không hợp lệ.",
        )

    target_set = _get_or_create_set(db, payload.level_code, payload.topic)

    # Check duplicate in set
    duplicate = db.scalar(
        select(VocabularyEntry).where(
            VocabularyEntry.vocabulary_set_id == target_set.id,
            VocabularyEntry.normalized_word == norm_word,
            VocabularyEntry.part_of_speech == clean_pos,
        )
    )
    if duplicate is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Từ vựng '{clean_word}' ({clean_pos}) đã tồn tại trong chủ đề '{payload.topic}'.",
        )

    max_order = (
        db.scalar(
            select(func.max(VocabularyEntry.order_index)).where(
                VocabularyEntry.vocabulary_set_id == target_set.id
            )
        )
        or 0
    )

    entry = VocabularyEntry(
        vocabulary_set_id=target_set.id,
        word=clean_word,
        normalized_word=norm_word,
        ipa=payload.ipa.strip() if payload.ipa and payload.ipa.strip() else None,
        part_of_speech=clean_pos,
        meaning=payload.meaning.strip(),
        translation=payload.translation.strip(),
        translation_language_code="vi",
        example_sentences=[s.strip() for s in payload.example_sentences if s.strip()],
        order_index=max_order + 1,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)

    return AdminCatalogEntryItem(
        id=entry.id,
        vocabulary_set_id=target_set.id,
        word=entry.word,
        ipa=entry.ipa,
        part_of_speech=entry.part_of_speech,
        meaning=entry.meaning,
        translation=entry.translation,
        example_sentences=entry.example_sentences,
        level_code=target_set.level_code,
        topic=target_set.topic,
        set_name=target_set.name,
        order_index=entry.order_index,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
    )


@router.patch("/catalog/{entry_id}", response_model=AdminCatalogEntryItem)
def update_admin_catalog_entry(
    entry_id: uuid.UUID,
    payload: AdminUpdateCatalogEntryRequest,
    _admin_user: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> AdminCatalogEntryItem:
    """Update an existing catalog entry."""
    entry = db.get(VocabularyEntry, entry_id)
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Từ vựng không tồn tại trong thư viện."
        )
    current_set = db.get(VocabularySet, entry.vocabulary_set_id)
    if current_set is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Bộ từ vựng tương ứng không tồn tại."
        )

    # Determine target set
    target_level = payload.level_code or current_set.level_code
    target_topic = payload.topic.strip() if payload.topic else current_set.topic
    target_set = current_set
    if target_level != current_set.level_code or target_topic != current_set.topic:
        target_set = _get_or_create_set(db, target_level, target_topic)
        entry.vocabulary_set_id = target_set.id

    # Update basic fields if provided
    if payload.word is not None:
        entry.word = payload.word.strip()
        entry.normalized_word = normalize_word(entry.word)

    if payload.ipa is not None:
        entry.ipa = payload.ipa.strip() if payload.ipa.strip() else None

    if payload.part_of_speech is not None:
        clean_pos = payload.part_of_speech.strip().lower()
        if clean_pos not in CATALOG_PARTS_OF_SPEECH:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Từ loại '{payload.part_of_speech}' không hợp lệ.",
            )
        entry.part_of_speech = clean_pos

    if payload.meaning is not None:
        entry.meaning = payload.meaning.strip()

    if payload.translation is not None:
        entry.translation = payload.translation.strip()

    if payload.example_sentences is not None:
        entry.example_sentences = [
            s.strip() for s in payload.example_sentences if s.strip()
        ]

    # Verify duplicate after changes
    duplicate = db.scalar(
        select(VocabularyEntry).where(
            VocabularyEntry.id != entry.id,
            VocabularyEntry.vocabulary_set_id == target_set.id,
            VocabularyEntry.normalized_word == entry.normalized_word,
            VocabularyEntry.part_of_speech == entry.part_of_speech,
        )
    )
    if duplicate is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Từ vựng '{entry.word}' ({entry.part_of_speech}) đã tồn tại trong chủ đề '{target_set.topic}'.",
        )

    db.commit()
    db.refresh(entry)

    return AdminCatalogEntryItem(
        id=entry.id,
        vocabulary_set_id=target_set.id,
        word=entry.word,
        ipa=entry.ipa,
        part_of_speech=entry.part_of_speech,
        meaning=entry.meaning,
        translation=entry.translation,
        example_sentences=entry.example_sentences,
        level_code=target_set.level_code,
        topic=target_set.topic,
        set_name=target_set.name,
        order_index=entry.order_index,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
    )


@router.delete("/catalog/{entry_id}", status_code=status.HTTP_200_OK)
def delete_admin_catalog_entry(
    entry_id: uuid.UUID,
    _admin_user: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, object]:
    """Delete a shared catalog entry safely. User vocabulary references will be set to NULL."""
    entry = db.get(VocabularyEntry, entry_id)
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Từ vựng không tồn tại trong thư viện."
        )

    # Explicitly detach any personal vocabulary references before deleting
    db.execute(
        select(Vocabulary).where(Vocabulary.source_vocabulary_entry_id == entry.id)
    )
    vocab_items = db.scalars(
        select(Vocabulary).where(Vocabulary.source_vocabulary_entry_id == entry.id)
    ).all()
    for v in vocab_items:
        v.source_vocabulary_entry_id = None

    db.delete(entry)
    db.commit()

    return {"success": True, "message": "Đã xóa từ vựng khỏi thư viện dùng chung."}
