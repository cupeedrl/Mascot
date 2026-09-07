from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from app.core.config import get_settings


class ActionTokenError(Exception):
    pass


class ActionTokenExpiredError(ActionTokenError):
    pass


class ActionOwnerMismatchError(ActionTokenError):
    pass


class ActionReplayError(ActionTokenError):
    pass


@dataclass(frozen=True)
class ActionClaims:
    action_id: uuid.UUID
    user_id: uuid.UUID
    tool_name: str
    arguments: dict[str, Any]
    expires_at: datetime


def issue_action_token(
    *,
    tool_name: str,
    arguments: dict[str, Any],
    user_id: uuid.UUID,
) -> tuple[str, ActionClaims]:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    claims = ActionClaims(
        action_id=uuid.uuid4(),
        user_id=user_id,
        tool_name=tool_name,
        arguments=arguments,
        expires_at=now + timedelta(seconds=settings.ai_action_token_expire_seconds),
    )
    payload = {
        "sub": str(user_id),
        "type": "ai_action",
        "tool": tool_name,
        "args": arguments,
        "iat": now,
        "exp": claims.expires_at,
        "jti": str(claims.action_id),
        "iss": settings.jwt_issuer,
        "aud": settings.ai_action_token_audience,
    }
    token = jwt.encode(
        payload,
        settings.jwt_secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )
    return token, claims


def verify_action_token(token: str, current_user_id: uuid.UUID) -> ActionClaims:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
            audience=settings.ai_action_token_audience,
            issuer=settings.jwt_issuer,
            options={
                "require": ["sub", "type", "tool", "args", "iat", "exp", "jti", "iss", "aud"]
            },
        )
    except jwt.ExpiredSignatureError as exc:
        raise ActionTokenExpiredError("Action token expired") from exc
    except jwt.PyJWTError as exc:
        raise ActionTokenError("Action token is invalid") from exc

    try:
        user_id = uuid.UUID(payload["sub"])
        action_id = uuid.UUID(payload["jti"])
        tool_name = payload["tool"]
        arguments = payload["args"]
        expires_at = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise ActionTokenError("Action token claims are invalid") from exc

    if payload.get("type") != "ai_action":
        raise ActionTokenError("Unexpected action token type")
    if user_id != current_user_id:
        raise ActionOwnerMismatchError("Action belongs to another user")
    if not isinstance(tool_name, str) or not tool_name:
        raise ActionTokenError("Action tool is invalid")
    if not isinstance(arguments, dict):
        raise ActionTokenError("Action arguments are invalid")
    return ActionClaims(action_id, user_id, tool_name, arguments, expires_at)


class ActionReplayGuard:
    """Process-local replay guard; domain duplicate rules remain the final backstop."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._reserved: dict[uuid.UUID, datetime] = {}

    def reserve(self, action_id: uuid.UUID, expires_at: datetime) -> None:
        now = datetime.now(timezone.utc)
        with self._lock:
            self._reserved = {
                key: expiry for key, expiry in self._reserved.items() if expiry > now
            }
            if action_id in self._reserved:
                raise ActionReplayError("Action was already handled")
            self._reserved[action_id] = expires_at

    def release(self, action_id: uuid.UUID) -> None:
        with self._lock:
            self._reserved.pop(action_id, None)

    def clear(self) -> None:
        with self._lock:
            self._reserved.clear()


action_replay_guard = ActionReplayGuard()
