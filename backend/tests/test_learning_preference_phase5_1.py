from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.models.language import Language
from app.models.learning_track import LearningTrack
from app.services.learning_profile import get_learning_profile

PASSWORD = "StrongPassword123!"


@dataclass(frozen=True)
class Tracks:
    english: LearningTrack
    chinese: LearningTrack


@pytest.fixture
def tracks(session_factory: Any) -> Tracks:
    with session_factory() as db:
        english = LearningTrack(
            language=Language(code="en", name="English", native_name="English"),
            code="general-english",
            name="General English",
            level_framework="CEFR",
        )
        chinese = LearningTrack(
            language=Language(code="zh", name="Chinese", native_name="中文"),
            code="general-chinese",
            name="General Chinese",
            level_framework="HSK",
        )
        db.add_all([english, chinese])
        db.commit()
        db.refresh(english)
        db.refresh(chinese)
        return Tracks(english=english, chinese=chinese)


def authenticate(client: TestClient, email: str) -> tuple[dict[str, str], UUID]:
    registration = client.post(
        "/api/v1/auth/register", json={"email": email, "password": PASSWORD}
    )
    assert registration.status_code == 201
    login = client.post(
        "/api/v1/auth/login", json={"email": email, "password": PASSWORD}
    )
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}, UUID(
        registration.json()["id"]
    )


def preference_url(track: LearningTrack) -> str:
    return f"/api/v1/learning-preferences/{track.id}"


def test_user_can_set_normalized_english_b1(
    client: TestClient, tracks: Tracks
) -> None:
    headers, _ = authenticate(client, "preference-english@example.com")

    response = client.put(
        preference_url(tracks.english),
        headers=headers,
        json={"current_level_code": " b1 "},
    )

    assert response.status_code == 200
    assert response.json() == {
        "learning_track_id": str(tracks.english.id),
        "framework": "CEFR",
        "current_level_code": "B1",
        "level_codes": ["A1", "A2", "B1", "B2", "C1", "C2"],
    }


def test_user_can_set_normalized_chinese_hsk2(
    client: TestClient, tracks: Tracks
) -> None:
    headers, _ = authenticate(client, "preference-chinese@example.com")

    response = client.put(
        preference_url(tracks.chinese),
        headers=headers,
        json={"current_level_code": "hsk2"},
    )

    assert response.status_code == 200
    assert response.json()["framework"] == "HSK"
    assert response.json()["current_level_code"] == "HSK2"
    assert response.json()["level_codes"] == [f"HSK{number}" for number in range(1, 10)]


@pytest.mark.parametrize(
    ("track_name", "invalid_level"),
    (("english", "HSK2"), ("chinese", "B1")),
)
def test_cross_framework_level_is_rejected(
    track_name: str,
    invalid_level: str,
    client: TestClient,
    tracks: Tracks,
) -> None:
    headers, _ = authenticate(client, f"preference-invalid-{track_name}@example.com")

    response = client.put(
        preference_url(getattr(tracks, track_name)),
        headers=headers,
        json={"current_level_code": invalid_level},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Level is not valid for the selected learning track"


def test_preferences_are_isolated_by_user(
    client: TestClient, tracks: Tracks
) -> None:
    owner_headers, _ = authenticate(client, "preference-owner@example.com")
    other_headers, _ = authenticate(client, "preference-other@example.com")
    assert client.put(
        preference_url(tracks.english),
        headers=owner_headers,
        json={"current_level_code": "B2"},
    ).status_code == 200

    other = client.get(preference_url(tracks.english), headers=other_headers)

    assert other.status_code == 200
    assert other.json()["current_level_code"] is None


def test_same_user_can_store_independent_levels_for_both_tracks(
    client: TestClient, tracks: Tracks
) -> None:
    headers, _ = authenticate(client, "preference-both@example.com")
    client.put(
        preference_url(tracks.english),
        headers=headers,
        json={"current_level_code": "B1"},
    )
    client.put(
        preference_url(tracks.chinese),
        headers=headers,
        json={"current_level_code": "HSK2"},
    )

    english = client.get(preference_url(tracks.english), headers=headers)
    chinese = client.get(preference_url(tracks.chinese), headers=headers)

    assert english.json()["current_level_code"] == "B1"
    assert chinese.json()["current_level_code"] == "HSK2"


def test_unset_preference_returns_null(client: TestClient, tracks: Tracks) -> None:
    headers, _ = authenticate(client, "preference-unset@example.com")

    response = client.get(preference_url(tracks.chinese), headers=headers)

    assert response.status_code == 200
    assert response.json()["current_level_code"] is None


@pytest.mark.parametrize(
    ("track_name", "level"), (("english", "B1"), ("chinese", "HSK2"))
)
def test_learning_profile_uses_authoritative_stored_level(
    track_name: str,
    level: str,
    client: TestClient,
    session_factory: Any,
    tracks: Tracks,
) -> None:
    headers, user_id = authenticate(
        client, f"preference-profile-{track_name}@example.com"
    )
    track = getattr(tracks, track_name)
    client.put(
        preference_url(track),
        headers=headers,
        json={"current_level_code": level},
    )

    with session_factory() as db:
        profile = get_learning_profile(
            db, user_id, learning_track_id=track.id
        )

    assert profile.current_level == level


def test_changing_level_updates_learning_profile(
    client: TestClient, session_factory: Any, tracks: Tracks
) -> None:
    headers, user_id = authenticate(client, "preference-update@example.com")
    client.put(
        preference_url(tracks.english),
        headers=headers,
        json={"current_level_code": "A2"},
    )
    client.put(
        preference_url(tracks.english),
        headers=headers,
        json={"current_level_code": "C1"},
    )

    with session_factory() as db:
        profile = get_learning_profile(
            db, user_id, learning_track_id=tracks.english.id
        )

    assert profile.current_level == "C1"


def test_frontend_cannot_inject_user_id(
    client: TestClient, tracks: Tracks
) -> None:
    headers, _ = authenticate(client, "preference-injection@example.com")

    response = client.put(
        preference_url(tracks.english),
        headers=headers,
        json={"current_level_code": "B1", "user_id": "00000000-0000-0000-0000-000000000001"},
    )

    assert response.status_code == 422
    unchanged = client.get(preference_url(tracks.english), headers=headers)
    assert unchanged.json()["current_level_code"] is None


def test_preference_routes_require_authentication(
    client: TestClient, tracks: Tracks
) -> None:
    assert client.get(preference_url(tracks.english)).status_code == 401
    assert client.put(
        preference_url(tracks.english), json={"current_level_code": "B1"}
    ).status_code == 401


def test_browser_cors_preflight_allows_preference_update(
    client: TestClient, tracks: Tracks
) -> None:
    response = client.options(
        preference_url(tracks.english),
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "PUT",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )

    assert response.status_code == 200
    assert "PUT" in response.headers["access-control-allow-methods"]
