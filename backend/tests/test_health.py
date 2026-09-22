import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.api.v1.routes.health import database_health_check


class HealthySession:
    def execute(self, _statement: object) -> None:
        return None


class UnavailableSession:
    def execute(self, _statement: object) -> None:
        raise OperationalError("SELECT 1", {}, Exception("connection refused"))


def test_health_endpoint_is_registered_and_returns_ok(client: TestClient) -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_database_health_returns_reachable() -> None:
    response = database_health_check(HealthySession())

    assert response.model_dump() == {"status": "ok", "database": "reachable"}


def test_database_health_returns_safe_error() -> None:
    with pytest.raises(HTTPException) as exc_info:
        database_health_check(UnavailableSession())

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "Database unavailable"
