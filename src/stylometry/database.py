"""Optional SQLAlchemy engine factory. No schema creation or automatic connection."""

from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import make_url

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
    return create_engine(parsed, pool_pre_ping=True, hide_parameters=True)
