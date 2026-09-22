import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.health import DatabaseHealthResponse, HealthResponse
from app.services.health import verify_database_connection

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/health")


@router.get("", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Return application liveness without requiring a database connection."""
    return HealthResponse(status="ok")


@router.get("/database", response_model=DatabaseHealthResponse)
def database_health_check(db: Session = Depends(get_db)) -> DatabaseHealthResponse:
    """Verify that the backend can execute a simple PostgreSQL query."""
    try:
        verify_database_connection(db)
    except SQLAlchemyError as exc:
        # Log only the exception class; connection errors can contain deployment
        # metadata and must not leak credentials through diagnostic logs.
        logger.warning("Database health check failed (%s)", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable",
        ) from exc

    return DatabaseHealthResponse(status="ok", database="reachable")
