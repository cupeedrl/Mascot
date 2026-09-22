from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


class AICooldownError(Exception):
    def __init__(self, retry_after: int, message: str | None = None) -> None:
        self.retry_after = max(1, retry_after)
        super().__init__(
            message
            or f"Bạn đang tạo bài quá nhanh. Hãy chờ {self.retry_after} giây rồi thử lại."
        )


class AIDuplicateRequestError(Exception):
    def __init__(self, message: str | None = None) -> None:
        super().__init__(
            message
            or "Yêu cầu tạo bài tập tương tự đang được xử lý. Vui lòng chờ trong giây lát."
        )


@dataclass
class UserActivity:
    last_generation_by_feature: dict[str, float] = field(default_factory=dict)
    in_flight_fingerprints: set[str] = field(default_factory=set)


class AIGuard:
    """Thread-safe in-memory guard for AI generation rate limiting and deduplication."""

    def __init__(self, default_cooldown_seconds: int = 30) -> None:
        self._default_cooldown = default_cooldown_seconds
        self._users: dict[uuid.UUID, UserActivity] = {}
        self._lock = threading.Lock()

    def _get_user_activity(self, user_id: uuid.UUID) -> UserActivity:
        if user_id not in self._users:
            self._users[user_id] = UserActivity()
        return self._users[user_id]

    @staticmethod
    def compute_fingerprint(
        user_id: uuid.UUID,
        feature: str,
        payload_data: dict[str, Any],
    ) -> str:
        serialized = json.dumps(payload_data, sort_keys=True, default=str)
        raw = f"{user_id}:{feature}:{serialized}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def check_and_acquire(
        self,
        user_id: uuid.UUID,
        feature: str,
        fingerprint: str,
        cooldown_seconds: int | None = None,
        bypass_cooldown: bool = False,
    ) -> None:
        cooldown = cooldown_seconds if cooldown_seconds is not None else self._default_cooldown
        now = time.time()

        with self._lock:
            activity = self._get_user_activity(user_id)

            # 1. Check in-flight duplicate
            if fingerprint in activity.in_flight_fingerprints:
                logger.info(
                    "AI generation duplicate in-flight rejected (user_id=%s, feature=%s)",
                    user_id,
                    feature,
                )
                raise AIDuplicateRequestError()

            # 2. Check cooldown per feature
            last_time = activity.last_generation_by_feature.get(feature, 0.0)
            if not bypass_cooldown and last_time > 0:
                elapsed = now - last_time
                if elapsed < cooldown:
                    remaining = int(cooldown - elapsed) + 1
                    logger.info(
                        "AI generation cooldown active (user_id=%s, feature=%s, remaining=%ss)",
                        user_id,
                        feature,
                        remaining,
                    )
                    raise AICooldownError(retry_after=remaining)

            # Acquire in-flight lock
            activity.in_flight_fingerprints.add(fingerprint)

    def release(
        self,
        user_id: uuid.UUID,
        feature: str,
        fingerprint: str,
        mark_success: bool = True,
    ) -> None:
        now = time.time()
        with self._lock:
            activity = self._get_user_activity(user_id)
            activity.in_flight_fingerprints.discard(fingerprint)
            if mark_success:
                activity.last_generation_by_feature[feature] = now

    def reset_user(self, user_id: uuid.UUID) -> None:
        """Helper for test cleanup."""
        with self._lock:
            self._users.pop(user_id, None)


# Global singleton instance
ai_guard = AIGuard(default_cooldown_seconds=30)
