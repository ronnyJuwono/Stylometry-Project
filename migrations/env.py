"""Explicit migrations only. Never imported by the application."""

import os

from alembic import context

from stylometry.database import create_optional_engine
from stylometry.migration_safety import assert_empty_development_target
from stylometry.models import Base


def run():
    if context.is_offline_mode():
        context.configure(dialect_name="postgresql", target_metadata=Base.metadata,
                          literal_binds=True)
        with context.begin_transaction():
            context.run_migrations()
        return
    engine = None
    try:
        if os.environ.get("STYLOMETRY_MIGRATION_TARGET") != "stylometry_dev":
            raise RuntimeError("Explicit development migration designation is required.")
        engine = create_optional_engine()
        if engine is None:
            raise RuntimeError("Development database is not configured.")
        with engine.connect() as connection, connection.begin():
            assert_empty_development_target(connection)
            context.configure(connection=connection, target_metadata=Base.metadata)
            context.run_migrations()
    except Exception:
        # Alembic/driver exception text may contain connection details or values.
        raise RuntimeError("Migration refused or failed. Verify the designated empty local development target privately.") from None
    finally:
        if engine is not None:
            engine.dispose()


run()
