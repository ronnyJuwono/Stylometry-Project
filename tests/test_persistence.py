"""Offline synthetic persistence checks; no private files or live database."""

from datetime import datetime
from uuid import UUID

import pytest
from alembic import command
from alembic.config import Config
from pydantic import ValidationError
from sqlalchemy import DateTime, ForeignKeyConstraint, create_mock_engine
from sqlalchemy.orm import configure_mappers

from stylometry import contracts as c, models as m
from stylometry.database import DatabaseUnavailable, probe_postgresql, session_scope
from stylometry.persistence import RECORDS, to_contract, to_record
from stylometry.storage import StorageReference


def test_schema_compiles_without_connecting():
    configure_mappers()
    statements = []
    engine = create_mock_engine("postgresql+psycopg://", lambda sql, *a, **k: statements.append(str(sql.compile(dialect=engine.dialect))))
    m.Base.metadata.create_all(engine)
    assert len(m.Base.metadata.tables) == 15
    assert len(statements) == 15
    for table in m.Base.metadata.tables.values():
        assert table.primary_key.columns
        for col in table.columns:
            assert col.name not in {"text", "raw_text", "cleaned_text", "student_name", "path", "password"}
            if isinstance(col.type, DateTime):
                assert col.type.timezone
        for constraint in table.constraints:
            if isinstance(constraint, ForeignKeyConstraint):
                assert constraint.ondelete == "RESTRICT"


def test_every_contract_roundtrips(synthetic_bundle):
    for name in RECORDS:
        for contract in getattr(synthetic_bundle, name):
            assert to_contract(to_record(contract)) == contract


def test_association_roundtrips(synthetic_bundle):
    qc = synthetic_bundle.evaluations[0]
    duplicate = c.QCEvaluation(**{**qc.model_dump(), "status": c.QCStatus.EXCLUDED,
        "reasons": (c.QCReason.DUPLICATE_TEXT,), "evidence_ref": UUID(int=999),
        "related_sample_ids": (synthetic_bundle.samples[1].id,)})
    assert to_contract(to_record(duplicate)) == duplicate
    planned = synthetic_bundle.runs[0]
    run = c.ExperimentRun(**{**planned.model_dump(), "status": c.RunStatus.SUCCEEDED,
        "started_at": planned.created_at, "finished_at": planned.created_at,
        "output_provenance_ids": (synthetic_bundle.provenance[0].id,)})
    assert to_contract(to_record(run)) == run


def test_invalid_orm_values_are_revalidated(synthetic_bundle):
    record = to_record(synthetic_bundle.evaluations[0])
    record.word_threshold = 100
    with pytest.raises(ValidationError):
        to_contract(record)
    record = to_record(synthetic_bundle.provenance[0])
    record.recorded_at = datetime(2026, 1, 1)
    with pytest.raises(ValidationError):
        to_contract(record)
    record = to_record(synthetic_bundle.evaluations[0])
    record.writer_id = UUID(int=123)
    with pytest.raises(ValueError, match="exactly one"):
        to_contract(record)


def test_storage_reference_rejects_paths_and_extra_text(synthetic_bundle):
    data = dict(object_ref=UUID(int=900), byte_sha256="0" * 64,
                provenance_id=synthetic_bundle.provenance[0].id,
                media_type="text/plain", processing_version="synthetic.v1")
    assert StorageReference(**data).object_ref == UUID(int=900)
    for update in ({"object_ref": "F:\\private\\writing.txt"}, {"raw_text": "forbidden"},
                   {"byte_sha256": "bad"}, {"processing_version": "../private"}):
        with pytest.raises(ValidationError):
            StorageReference(**{**data, **update})


def test_offline_migration_is_frozen_and_contains_no_connection(monkeypatch):
    from io import StringIO
    import stylometry.database as db
    monkeypatch.setattr(db, "create_optional_engine", lambda *a, **k: pytest.fail("Offline connected"))
    output = StringIO()
    cfg = Config("alembic.ini", output_buffer=output)
    command.upgrade(cfg, "head", sql=True)
    sql = output.getvalue()
    assert sql.count("CREATE TABLE") == 16  # 15 research tables + Alembic version.
    assert "TIMESTAMP WITH TIME ZONE" in sql
    assert "INSERT INTO task" in sql
    assert "s2b01_0001" in sql
    source = __import__("pathlib").Path("migrations/versions/s2b01_0001_initial.py").read_text()
    assert "stylometry.models" not in source


def test_online_migration_requires_explicit_designation(monkeypatch):
    monkeypatch.delenv("STYLOMETRY_MIGRATION_TARGET", raising=False)
    with pytest.raises(RuntimeError, match="Migration refused"):
        command.upgrade(Config("alembic.ini"), "head")


def test_connection_probe_does_not_expose_configuration(monkeypatch):
    import stylometry.database as db
    monkeypatch.setattr(db, "database_url", lambda: None)
    assert probe_postgresql() == "not_configured"
    assert probe_postgresql("invalid-secret-url") == "unavailable"


def test_session_errors_are_sanitized():
    from sqlalchemy import create_engine, text
    engine = create_engine("sqlite://")
    with pytest.raises(DatabaseUnavailable) as error:
        with session_scope(engine) as session:
            session.execute(text("SELECT secret_dummy FROM nonexistent"))
    assert "secret_dummy" not in str(error.value)
    assert error.value.__suppress_context__
    engine.dispose()


def test_transaction_scope_commits_rolls_back_and_closes():
    from sqlalchemy import create_engine, text
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE synthetic_transaction (id INTEGER PRIMARY KEY)"))
    with session_scope(engine) as session:
        session.execute(text("INSERT INTO synthetic_transaction VALUES (1)"))
    with pytest.raises(RuntimeError, match="artificial failure"):
        with session_scope(engine) as session:
            session.execute(text("INSERT INTO synthetic_transaction VALUES (2)"))
            raise RuntimeError("artificial failure")
    with engine.connect() as connection:
        assert list(connection.scalars(text("SELECT id FROM synthetic_transaction"))) == [1]
    engine.dispose()


def test_app_startup_does_not_connect(monkeypatch):
    from streamlit.testing.v1 import AppTest
    import sqlalchemy.engine
    monkeypatch.setattr(sqlalchemy.engine.Engine, "connect", lambda *a, **k: pytest.fail("Startup connected"))
    monkeypatch.setattr(m.Base.metadata, "create_all", lambda *a, **k: pytest.fail("Startup created tables"))
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://localhost/unconfigured_test")
    from pathlib import Path
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py").run()
    assert not app.exception


@pytest.mark.parametrize("url", [
    "postgresql+psycopg://localhost/production",
    "postgresql+psycopg://remote.invalid/stylometry_dev",
    "postgresql+psycopg://localhost/stylometry_dev?host=remote.invalid",
    "postgresql+psycopg:///stylometry_dev",
    "sqlite://",
])
def test_migration_guard_refuses_unsafe_targets_before_sql(url):
    from types import SimpleNamespace
    from sqlalchemy.engine import make_url
    from stylometry.migration_safety import assert_empty_development_target
    connection = SimpleNamespace(engine=SimpleNamespace(url=make_url(url)))
    with pytest.raises(ValueError, match="empty local"):
        assert_empty_development_target(connection)


@pytest.mark.parametrize("database, address, occupied, allowed", [
    ("stylometry_dev", "127.0.0.1", False, True),
    ("stylometry_dev", "::1", False, True),
    ("production", "127.0.0.1", False, False),
    ("stylometry_dev", "10.0.0.1", False, False),
    ("stylometry_dev", "127.0.0.1", True, False),
])
def test_migration_guard_checks_actual_database_and_contents(database, address, occupied, allowed):
    from types import SimpleNamespace
    from sqlalchemy.engine import make_url
    from stylometry.migration_safety import assert_empty_development_target
    connection = SimpleNamespace(
        engine=SimpleNamespace(url=make_url("postgresql+psycopg://localhost/stylometry_dev")),
        execute=lambda *a: SimpleNamespace(one=lambda: (database, address)),
        scalar=lambda *a: occupied,
    )
    if allowed:
        assert_empty_development_target(connection)
    else:
        with pytest.raises(ValueError):
            assert_empty_development_target(connection)
