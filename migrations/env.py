"""Explicit migrations only. Never imported by the application."""

import os

from alembic import context
from sqlalchemy.engine import Connection

from stylometry.database import create_optional_engine
from stylometry.migration_safety import assert_empty_development_target
from stylometry.models import Base
from stylometry.upgrade_safety import assert_initialized_upgrade, NEW_REVISION, OLD_REVISION


def run():
    # Inspect the literal command destination before Alembic resolves "head".
    # This configures only a dialect; it opens no database connection.
    context.configure(dialect_name="postgresql")
    requested_revision = context.get_context().opts.get("destination_rev")
    if context.is_offline_mode():
        if requested_revision != OLD_REVISION:
            raise RuntimeError("Offline successor migration is refused; use guarded online preflight.")
        context.configure(dialect_name="postgresql", target_metadata=Base.metadata,
                          literal_binds=True)
        with context.begin_transaction():
            context.run_migrations()
        return
    engine = None
    try:
        provided = context.config.attributes.get("connection")
        if provided is not None:
            # Narrow test injection: never accepts a development connection and
            # never commits the fixture's enclosing transaction.
            if (not isinstance(provided, Connection) or not provided.in_transaction()
                    or os.environ.get("STYLOMETRY_MIGRATION_TARGET") != "stylometry_test"
                    or os.environ.get("STYLOMETRY_MIGRATION_MODE") != "initialized"
                    or os.environ.get("STYLOMETRY_MIGRATION_REVISION") != NEW_REVISION
                    or requested_revision != NEW_REVISION):
                raise RuntimeError("Explicit isolated upgrade fixture required.")
            with provided.begin_nested():
                assert_initialized_upgrade(provided, database="stylometry_test", target=NEW_REVISION)
                from stylometry.operation_models import metadata
                context.configure(connection=provided, target_metadata=metadata)
                context.run_migrations()
            return
        if os.environ.get("STYLOMETRY_MIGRATION_TARGET") != "stylometry_dev":
            raise RuntimeError("Explicit development migration designation is required.")
        engine = create_optional_engine()
        if engine is None:
            raise RuntimeError("Development database is not configured.")
        with engine.connect() as connection, connection.begin():
            if os.environ.get("STYLOMETRY_MIGRATION_MODE", "initial") == "initial":
                if requested_revision != OLD_REVISION:
                    raise RuntimeError("Initial migration requires its exact revision.")
                assert_empty_development_target(connection)
                target_metadata = Base.metadata
            elif (os.environ.get("STYLOMETRY_MIGRATION_MODE") == "initialized"
                  and os.environ.get("STYLOMETRY_MIGRATION_REVISION") == NEW_REVISION
                  and requested_revision == NEW_REVISION):
                assert_initialized_upgrade(connection, database="stylometry_dev", target=NEW_REVISION)
                from stylometry.operation_models import metadata
                target_metadata = metadata
            else:
                raise RuntimeError("Explicit migration mode/revision required.")
            context.configure(connection=connection, target_metadata=target_metadata)
            context.run_migrations()
    except Exception:
        # Alembic/driver exception text may contain connection details or values.
        raise RuntimeError("Migration refused or failed. Verify the explicit local target, revision and schema privately.") from None
    finally:
        if engine is not None:
            engine.dispose()


run()
