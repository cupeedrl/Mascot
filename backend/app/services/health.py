from sqlalchemy import text
from sqlalchemy.orm import Session


def verify_database_connection(db: Session) -> None:
    """Raise a SQLAlchemy error when a trivial database query cannot run."""
    db.execute(text("SELECT 1"))

