from __future__ import annotations

import uuid
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.models.exercise_attempt import ExerciseAttempt
from app.models.user import User
from app.models.vocabulary import Vocabulary
from app.models.vocabulary_entry import VocabularyEntry
from app.models.vocabulary_set import VocabularySet
from tests.test_vocabulary import authenticate, create_item, general_english_track_id


def test_user_default_role_is_user_and_registration_cannot_override(
    client: TestClient,
    session_factory: sessionmaker[Session],
) -> None:
    # 1. Registration endpoint rejects unauthorized extra fields
    reg_resp = client.post(
        "/api/v1/auth/register",
        json={"email": "new_student@example.com", "password": "StrongPassword123!", "role": "admin"},
    )
    assert reg_resp.status_code == 422

    # Normal registration
    reg_valid = client.post(
        "/api/v1/auth/register",
        json={"email": "new_student@example.com", "password": "StrongPassword123!"},
    )
    assert reg_valid.status_code == 201
    user_data = reg_valid.json()
    assert user_data["role"] == "user"

    with session_factory() as db:
        user_row = db.scalar(select(User).where(User.email == "new_student@example.com"))
        assert user_row is not None
        assert user_row.role == "user"


def test_admin_authorization_guards_across_all_endpoints(
    client: TestClient,
    session_factory: sessionmaker[Session],
) -> None:
    # 1. Unauthenticated -> 401
    assert client.get("/api/v1/admin/overview").status_code == 401
    assert client.get("/api/v1/admin/users").status_code == 401
    assert client.get("/api/v1/admin/catalog").status_code == 401

    # 2. Authenticated normal user -> 403 Forbidden
    normal_headers = authenticate(client, email="normal_learner_guard@example.com")
    assert client.get("/api/v1/admin/overview", headers=normal_headers).status_code == 403
    assert client.get("/api/v1/admin/users", headers=normal_headers).status_code == 403
    assert client.get("/api/v1/admin/catalog", headers=normal_headers).status_code == 403
    assert (
        client.post(
            "/api/v1/admin/catalog",
            headers=normal_headers,
            json={
                "word": "forbidden",
                "part_of_speech": "noun",
                "meaning": "not allowed",
                "translation": "bị cấm",
                "example_sentences": ["This is forbidden."],
                "level_code": "B1",
                "topic": "Rules",
            },
        ).status_code
        == 403
    )


def test_admin_users_management_flow(
    client: TestClient,
    session_factory: sessionmaker[Session],
    general_english_track_id: uuid.UUID,
) -> None:
    # 1. Create admin user and a learner user
    admin_headers = authenticate(client, email="head_admin@example.com")
    with session_factory() as db:
        admin_u = db.scalar(select(User).where(User.email == "head_admin@example.com"))
        admin_u.role = "admin"
        db.commit()

    learner_headers = authenticate(client, email="student_one@example.com")
    create_item(client, learner_headers, general_english_track_id, word="persevere")

    # 2. Admin lists users
    users_resp = client.get("/api/v1/admin/users?search=student_one", headers=admin_headers)
    assert users_resp.status_code == 200
    user_list = users_resp.json()
    assert user_list["total"] == 1
    learner_item = user_list["items"][0]
    assert learner_item["email"] == "student_one@example.com"
    assert learner_item["personal_vocabulary_count"] == 1
    learner_id = learner_item["id"]

    # 3. View user detail
    detail_resp = client.get(f"/api/v1/admin/users/{learner_id}", headers=admin_headers)
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["email"] == "student_one@example.com"
    assert "password_hash" not in detail

    # 4. Promote learner to admin
    promote_resp = client.patch(
        f"/api/v1/admin/users/{learner_id}/role",
        headers=admin_headers,
        json={"role": "admin"},
    )
    assert promote_resp.status_code == 200
    assert promote_resp.json()["role"] == "admin"

    # 5. Demote learner back to user
    demote_resp = client.patch(
        f"/api/v1/admin/users/{learner_id}/role",
        headers=admin_headers,
        json={"role": "user"},
    )
    assert demote_resp.status_code == 200
    assert demote_resp.json()["role"] == "user"

    # 6. Safety check: Cannot demote the last remaining admin
    with session_factory() as db:
        admin_u = db.scalar(select(User).where(User.email == "head_admin@example.com"))
        admin_id = str(admin_u.id)

    last_demote_resp = client.patch(
        f"/api/v1/admin/users/{admin_id}/role",
        headers=admin_headers,
        json={"role": "user"},
    )
    assert last_demote_resp.status_code == 400
    assert "cuối cùng" in last_demote_resp.json()["detail"].lower()

    # 7. Disable learner account
    disable_resp = client.patch(
        f"/api/v1/admin/users/{learner_id}/status",
        headers=admin_headers,
        json={"is_active": False},
    )
    assert disable_resp.status_code == 200
    assert disable_resp.json()["is_active"] is False

    # 8. Disabled learner cannot call authenticated APIs
    api_resp = client.get("/api/v1/dashboard", headers=learner_headers)
    assert api_resp.status_code == 401
    assert api_resp.json()["detail"]["code"] == "ACCOUNT_DISABLED"

    # 9. Disabled learner with wrong password -> generic 401
    wrong_pwd_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "student_one@example.com", "password": "WrongPassword123!"},
    )
    assert wrong_pwd_resp.status_code == 401
    assert wrong_pwd_resp.json()["detail"] == "Invalid email or password"

    # 10. Disabled learner with correct credentials gets 403 ACCOUNT_DISABLED
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "student_one@example.com", "password": "StrongPassword123!"},
    )
    assert login_resp.status_code == 403
    assert login_resp.json()["detail"]["code"] == "ACCOUNT_DISABLED"

    # 10. Re-enable learner account
    enable_resp = client.patch(
        f"/api/v1/admin/users/{learner_id}/status",
        headers=admin_headers,
        json={"is_active": True},
    )
    assert enable_resp.status_code == 200
    assert enable_resp.json()["is_active"] is True


def test_admin_catalog_crud_flow(
    client: TestClient,
    session_factory: sessionmaker[Session],
    general_english_track_id: uuid.UUID,
) -> None:
    admin_headers = authenticate(client, email="catalog_admin@example.com")
    with session_factory() as db:
        admin_u = db.scalar(select(User).where(User.email == "catalog_admin@example.com"))
        admin_u.role = "admin"
        db.commit()

    # 1. Create a shared catalog entry
    create_resp = client.post(
        "/api/v1/admin/catalog",
        headers=admin_headers,
        json={
            "word": "Resilient",
            "ipa": "/rɪˈzɪl.jənt/",
            "part_of_speech": "adjective",
            "meaning": "Able to quickly return to a previous good condition.",
            "translation": "Kiên cường, phục hồi nhanh",
            "example_sentences": ["She is a resilient person."],
            "level_code": "B2",
            "topic": "Personality",
        },
    )
    assert create_resp.status_code == 201
    created_entry = create_resp.json()
    assert created_entry["word"] == "Resilient"
    assert created_entry["level_code"] == "B2"
    entry_id = created_entry["id"]

    # 2. Duplicate rejection
    dup_resp = client.post(
        "/api/v1/admin/catalog",
        headers=admin_headers,
        json={
            "word": "resilient",
            "part_of_speech": "adjective",
            "meaning": "Another definition",
            "translation": "Kiên cường",
            "example_sentences": ["Another example."],
            "level_code": "B2",
            "topic": "Personality",
        },
    )
    assert dup_resp.status_code == 409

    # 3. List catalog entries with filter
    list_resp = client.get("/api/v1/admin/catalog?search=resilient", headers=admin_headers)
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] >= 1

    # 4. A learner imports this catalog entry to their personal notebook
    learner_headers = authenticate(client, email="catalog_learner@example.com")
    import_resp = client.post(
        "/api/v1/vocabulary-entries/import",
        headers=learner_headers,
        json={"entry_ids": [entry_id]},
    )
    assert import_resp.status_code == 200

    with session_factory() as db:
        user_vocab = db.scalar(
            select(Vocabulary).where(Vocabulary.word == "Resilient")
        )
        assert user_vocab is not None
        assert str(user_vocab.source_vocabulary_entry_id) == entry_id

    # 5. Admin edits catalog entry
    edit_resp = client.patch(
        f"/api/v1/admin/catalog/{entry_id}",
        headers=admin_headers,
        json={
            "meaning": "Able to withstand or recover quickly from difficult conditions.",
            "example_sentences": ["Babies are generally remarkably resilient."],
        },
    )
    assert edit_resp.status_code == 200
    assert "withstand" in edit_resp.json()["meaning"]

    # 6. Admin deletes catalog entry
    del_resp = client.delete(f"/api/v1/admin/catalog/{entry_id}", headers=admin_headers)
    assert del_resp.status_code == 200
    assert del_resp.json()["success"] is True

    # 7. User vocabulary remains intact with source_vocabulary_entry_id safely detached to NULL
    with session_factory() as db:
        user_vocab_after = db.scalar(
            select(Vocabulary).where(Vocabulary.word == "Resilient")
        )
        assert user_vocab_after is not None
        assert user_vocab_after.source_vocabulary_entry_id is None


def test_admin_ai_usage_flow(
    client: TestClient,
    session_factory: sessionmaker[Session],
) -> None:
    from app.services.ai_logger import record_ai_usage

    admin_headers = authenticate(client, email="ai_admin@example.com")
    with session_factory() as db:
        admin_u = db.scalar(select(User).where(User.email == "ai_admin@example.com"))
        admin_u.role = "admin"
        admin_id = admin_u.id

        # Insert real usage records
        record_ai_usage(
            db,
            user_id=admin_id,
            feature="exercise_generation",
            provider="groq",
            model="llama-3.3-70b-versatile",
            status="success",
            status_code=200,
            latency_ms=1250,
            input_tokens=150,
            output_tokens=300,
            total_tokens=450,
        )
        record_ai_usage(
            db,
            user_id=admin_id,
            feature="vocabulary_enrichment",
            provider="groq",
            model="llama-3.3-70b-versatile",
            status="rate_limited",
            status_code=429,
            latency_ms=45,
            error_type="AICooldownError",
        )
        record_ai_usage(
            db,
            user_id=None,
            feature="exercise_generation",
            provider="groq",
            model="llama-3.3-70b-versatile",
            status="failed",
            status_code=503,
            latency_ms=80,
            error_type="AIProviderNotConfiguredError",
        )

    # 1. Admin queries AI usage without filters
    resp = client.get("/api/v1/admin/ai-usage", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    assert data["summary"]["total_requests"] == 3
    assert data["summary"]["successful_requests"] == 1
    assert data["summary"]["failed_requests"] == 1
    assert data["summary"]["rate_limited_requests"] == 1
    assert data["summary"]["total_tokens"] == 450
    assert len(data["items"]) == 3

    # 2. Filter by status
    status_resp = client.get("/api/v1/admin/ai-usage?status=rate_limited", headers=admin_headers)
    assert status_resp.status_code == 200
    assert status_resp.json()["total"] == 1
    assert status_resp.json()["items"][0]["status"] == "rate_limited"

    # 3. Filter by period
    period_resp = client.get("/api/v1/admin/ai-usage?period=24h", headers=admin_headers)
    assert period_resp.status_code == 200
    assert period_resp.json()["total"] == 3

    # 4. Search by email
    search_resp = client.get("/api/v1/admin/ai-usage?search=ai_admin", headers=admin_headers)
    assert search_resp.status_code == 200
    assert search_resp.json()["total"] == 2

