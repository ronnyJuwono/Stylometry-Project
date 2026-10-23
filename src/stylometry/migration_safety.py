"""Read-only target checks plus a transaction-scoped cooperative migration lock."""

from sqlalchemy import text
from sqlalchemy.engine import Connection


def assert_empty_development_target(connection: Connection, *, database: str = "stylometry_dev") -> None:
    """Permit only an explicitly selected empty local stylometry_dev database.

    This is intentionally initial-migration-only. No existing schema, including
    an Alembic version table, is treated as safe to alter. A later migration needs
    a reviewed successor policy. Concurrent noncooperating DDL must be excluded
    operationally by restricting database access during the migration.
    """
    url = connection.engine.url
    if database not in ("stylometry_dev", "stylometry_test"):
        raise ValueError("Unsupported development target.")
    if (url.drivername != "postgresql+psycopg" or url.database != database
            or url.host not in ("localhost", "127.0.0.1", "::1") or url.query):
        raise ValueError("An empty local development database is required.")
    connection.execute(text("SELECT pg_advisory_xact_lock(21302401)"))
    actual = connection.execute(text(
        "SELECT current_database(), inet_server_addr()::text"
    )).one()
    if actual[0] != database or actual[1] not in ("127.0.0.1/32", "::1/128", "127.0.0.1", "::1"):
        raise ValueError("Development target identity could not be verified.")
    # pg_depend records all schema-owned objects, including routines/types/views;
    # also reject custom schemas/extensions and database-level event triggers.
    occupied = connection.scalar(text("""
        SELECT
          EXISTS (SELECT 1 FROM pg_namespace
                  WHERE nspname !~ '^pg_' AND nspname NOT IN ('information_schema', 'public'))
          OR EXISTS (SELECT 1 FROM pg_depend d JOIN pg_namespace n
                     ON d.refclassid = 'pg_namespace'::regclass AND d.refobjid = n.oid
                     WHERE n.nspname = 'public')
          OR EXISTS (SELECT 1 FROM pg_extension WHERE extname <> 'plpgsql')
          OR EXISTS (SELECT 1 FROM pg_event_trigger)
    """))
    if occupied:
        raise ValueError("Development target is not empty.")
