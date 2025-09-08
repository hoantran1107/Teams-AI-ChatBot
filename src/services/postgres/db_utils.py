"""
Database utilities for SQLAlchemy integration with FastAPI
"""

from contextlib import contextmanager
from typing import Generator, Any, Dict

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.config.database_config import get_db as config_get_db, db, Base


# Re-export the dependency to get DB session from config
get_db = config_get_db


@contextmanager
def get_db_context() -> Generator[Session, None, None]:
    """
    Context manager for database sessions - reimplemented for direct import

    Usage:
    ```python
    from src.services.postgres.db_utils import get_db_context

    with get_db_context() as session:
        # Use session here
        result = session.query(MyModel).all()
    ```
    """
    session = db.create_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def execute_raw_sql(
    query: str, params: Dict[str, Any] = None, db_session: Session = None
) -> list:
    """
    Execute a raw SQL query with parameters

    Args:
        query: Raw SQL query string
        params: Optional query parameters
        db_session: Optional SQLAlchemy session

    Returns:
        List of result rows as dictionaries
    """
    session = db_session or db.session
    result = session.execute(text(query), params or {})

    # Convert results to dictionaries
    keys = result.keys()
    return [dict(zip(keys, row)) for row in result.fetchall()]


def check_table_exists(table_name: str, db_session: Session = None) -> bool:
    """
    Check if a table exists in the database

    Args:
        table_name: Name of the table to check
        db_session: Optional SQLAlchemy session

    Returns:
        True if the table exists, False otherwise
    """
    session = db_session or db.session

    # This works for PostgreSQL
    query = text("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = :table_name
        );
    """)

    result = session.execute(query, {"table_name": table_name})
    return result.scalar()
