"""Optional SQLAlchemy engine factory. No schema creation or automatic connection."""

from contextlib import contextmanager

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import Connection, make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from stylometry.config import database_url


def create_optional_engine(url: str | None = None) -> Engine | None:
    configured_url = url if url is not None else database_url()
    if not configured_url:
        return None
    try:
        parsed = make_url(configured_url)
    except Exception:
        raise ValueError("Invalid database configuration; check the local environment.") from None
    if parsed.drivername != "postgresql+psycopg":
        raise ValueError("Use the postgresql+psycopg driver for PostgreSQL.")
    try:
        return create_engine(parsed, pool_pre_ping=True, hide_parameters=True,
                             connect_args={"connect_timeout": 5}, echo=False)
    except Exception:
        raise ValueError("Invalid database configuration; check the local environment.") from None


class DatabaseUnavailable(RuntimeError):
    """Public-safe failure; driver exceptions and URLs must not be logged."""


@contextmanager
def session_scope(engine: Engine | Connection):
    """Explicit transaction; commit on success, rollback/close on failure."""
    try:
        with Session(engine, join_transaction_mode="create_savepoint") as session, session.begin():
            yield session
    except SQLAlchemyError:
        raise DatabaseUnavailable("Database operation failed; inspect private configuration.") from None


def probe_postgresql(url: str | None = None) -> str:
    """Explicit psycopg connection probe. Returns only a credential-free status."""
    engine = None
    try:
        engine = create_optional_engine(url)
        if engine is None:
            return "not_configured"
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return "available"
    except Exception:
        return "unavailable"
    finally:
        if engine is not None:
            engine.dispose()
