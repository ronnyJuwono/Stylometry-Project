"""Opt-in integration tests: empty local stylometry_test only, all DDL rolled back."""

import importlib.util
from datetime import datetime, timezone
import os
from pathlib import Path
from uuid import UUID

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import insert, inspect, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from stylometry import models as m
from stylometry.database import create_optional_engine, session_scope
from stylometry.migration_safety import assert_empty_development_target
from stylometry.persistence import RECORDS, load_validated_bundle, to_record


@pytest.fixture(scope="module")
def postgres_connection():
    url = os.getenv("STYLOMETRY_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Isolated PostgreSQL test database not configured")
    engine = create_optional_engine(url)
    connection = None
    transaction = None
    try:
        try:
            connection = engine.connect()
        except Exception:
            pytest.fail("Configured PostgreSQL test database is unavailable", pytrace=False)
        transaction = connection.begin()
        try:
            assert_empty_development_target(connection, database="stylometry_test")
        except Exception:
            pytest.fail("PostgreSQL test target is not verified empty/local/isolated", pytrace=False)
        spec = importlib.util.spec_from_file_location("initial", Path("migrations/versions/s2b01_0001_initial.py"))
        revision = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(revision)
        with Operations.context(MigrationContext.configure(connection)):
            revision.upgrade()
        yield connection
    finally:
        if transaction is not None:
            transaction.rollback()
        if connection is not None:
            connection.close()
        engine.dispose()


@pytest.fixture
def pg(postgres_connection, synthetic_bundle):
    savepoint = postgres_connection.begin_nested()
    session = Session(postgres_connection, join_transaction_mode="create_savepoint")
    try:
        for name in RECORDS:
            session.add_all(to_record(record) for record in getattr(synthetic_bundle, name))
        session.flush()
        yield session
    finally:
        session.close()
        savepoint.rollback()


def test_migration_matches_orm(postgres_connection):
    from alembic.autogenerate import compare_metadata
    ctx = MigrationContext.configure(postgres_connection, opts={"compare_type": True})
    assert compare_metadata(ctx, m.Base.metadata) == []
    assert len(inspect(postgres_connection).get_table_names()) == 15


def test_graph_relationships_roundtrip(pg, synthetic_bundle):
    actual = load_validated_bundle(pg)
    for name in RECORDS:
        assert {r.id: r for r in getattr(actual, name)} == {r.id: r for r in getattr(synthetic_bundle, name)}
    sample = pg.get(m.TextSample, synthetic_bundle.samples[0].id)
    assert sample.writer.corpus.id == sample.corpus_id
    snapshot = pg.get(m.DatasetSnapshot, synthetic_bundle.snapshots[0].id)
    assert snapshot.members[0].sample_qc.status == "pass"
    run = pg.get(m.ExperimentRun, synthetic_bundle.runs[0].id)
    assert run.snapshot.id == snapshot.id


@pytest.mark.parametrize("kind", ["pk", "fk", "slot", "hash", "version", "timestamp", "context", "status", "target", "threshold", "manifest_context", "stage", "lifecycle", "task", "member"])
def test_database_rejects_invalid_records(pg, synthetic_bundle, kind):
    b = synthetic_bundle
    with pytest.raises(IntegrityError), pg.begin_nested():
        if kind == "pk":
            pg.execute(insert(m.Writer).values(id=b.writers[0].id, corpus_id=b.corpora[0].id))
        elif kind == "fk":
            pg.execute(insert(m.Writer).values(id=UUID(int=777), corpus_id=UUID(int=778)))
        elif kind == "slot":
            pg.execute(insert(m.TextSample).values(id=UUID(int=777), corpus_id=b.corpora[0].id,
                writer_id=b.writers[0].id, task_code=b.samples[0].task, provenance_id=b.provenance[0].id))
        elif kind == "hash":
            pg.execute(update(m.Provenance).values(evidence_sha256="x" * 64))
        elif kind == "version":
            pg.execute(update(m.CleanTextDerivation).values(version=0))
        elif kind == "timestamp":
            pg.execute(update(m.ExtractionEvent).values(finished_at=text("started_at - interval '1 second'")))
        elif kind in ("context", "status", "threshold", "target"):
            values = {"context": {"context": "invalid"}, "status": {"status": "invalid"},
                      "threshold": {"word_threshold": None}, "target": {"sample_id": None, "writer_id": None}}[kind]
            pg.execute(update(m.QCEvaluation).values(**values))
        elif kind == "manifest_context":
            pg.execute(update(m.DatasetSnapshot).values(context="source_inventory_100"))
        elif kind == "stage":
            pg.execute(update(m.ExperimentRun).values(stage_number=10))
        elif kind == "lifecycle":
            pg.execute(update(m.ExperimentRun).values(status="running"))
        elif kind == "task":
            pg.execute(update(m.Task).where(m.Task.code == "T05").values(form="paragraph"))
        elif kind == "member":
            pg.execute(update(m.SnapshotMember).values(derivation_id=UUID(int=778)))


def test_cross_row_snapshot_mismatch_is_detected_by_contract(pg):
    from pydantic import ValidationError
    pg.execute(update(m.SnapshotMember).values(clean_byte_sha256="1" * 64))
    pg.expire_all()
    with pytest.raises(ValidationError):
        load_validated_bundle(pg)


def test_session_commit_and_rollback(postgres_connection):
    with session_scope(postgres_connection) as session:
        assert session.scalar(select(m.Task.code).limit(1))
    with pytest.raises(RuntimeError, match="synthetic rollback"):
        with session_scope(postgres_connection) as session:
            session.add(m.Provenance(id=UUID(int=8888), recorded_at=datetime.now(timezone.utc),
                        evidence_ref=UUID(int=8889), evidence_sha256="0" * 64))
            session.flush()
            raise RuntimeError("synthetic rollback")
    assert postgres_connection.scalar(select(m.Provenance.id).where(m.Provenance.id == UUID(int=8888))) is None


@pytest.mark.parametrize("model, values", [
    (m.Provenance, {"evidence_ref": None}),
    (m.ExtractionEvent, {"status": "failed"}),
    (m.ExtractionEvent, {"code_commit": "bad"}),
    (m.ExtractionEvent, {"configuration_version": "../bad"}),
    (m.ExtractionEvent, {"contract_version": "unapproved.v2"}),
    (m.CleanTextDerivation, {"parent_derivation_id": UUID(int=1)}),
    (m.QCEvaluation, {"word_count": -1}),
    (m.QCEvaluation, {"eligible_task_count": 6}),
    (m.QCEvaluation, {"word_threshold": 100}),
    (m.QCEvaluation, {"tokenizer_method_ref": None}),
    (m.QCEvaluation, {"derivation_id": UUID(int=9999)}),
    (m.ExperimentRun, {"snapshot_id": UUID(int=9999)}),
    (m.ExperimentRun, {"finished_at": text("created_at - interval '1 second'")}),
])
def test_additional_database_constraints(pg, model, values):
    with pytest.raises(IntegrityError), pg.begin_nested():
        pg.execute(update(model).values(**values))


def test_run_output_relationship(pg, synthetic_bundle):
    run = pg.get(m.ExperimentRun, synthetic_bundle.runs[0].id)
    run.status = "succeeded"
    run.started_at = run.finished_at = run.created_at
    run.outputs.append(m.RunOutput(provenance_id=synthetic_bundle.provenance[0].id))
    pg.flush()
    assert load_validated_bundle(pg).runs[0].output_provenance_ids == (synthetic_bundle.provenance[0].id,)
