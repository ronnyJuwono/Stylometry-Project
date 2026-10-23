"""Transactional stylometry_test registration; no development database writes."""

from datetime import datetime, timezone
import json
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select, text

from stylometry import models as m
from stylometry.database import create_optional_engine
from stylometry.pipeline import registration
from stylometry.pipeline.registration import (
    RegistrationError, RegistrationReceipt, RegistrationRequest, RegistrationState,
    reconcile_registration, register_synthetic_inventory,
)
from stylometry.synthetic_publishing import SyntheticWorkspace
from test_postgresql import postgres_connection  # Reuse approved isolated/rollback fixture unchanged.
from test_research_pipeline import make_inventory, replace
from test_synthetic_publishing import SyntheticPolicy, workspace


@pytest.fixture
def test_connection(postgres_connection):
    savepoint = postgres_connection.begin_nested()
    try:
        yield postgres_connection
    finally:
        savepoint.rollback()


@pytest.fixture
def registration_input(workspace, synthetic_bundle):
    repro = synthetic_bundle.runs[0].reproducibility
    document_id = uuid4()
    plan = workspace.prepare(b"ARTIFICIAL REGISTRATION BYTES ONLY", series_ref=document_id,
        provenance_id=uuid4(), version="synthetic.source.v1", reproducibility=repro)
    inventory = make_inventory(plan.metadata.reference, document_id=document_id)
    request = RegistrationRequest(synthetic_only=True, operation_id=uuid4(), inventory=inventory,
        publications=(plan.metadata,), reproducibility=repro, created_at=datetime.now(timezone.utc))
    return request, (plan,)


def count(connection, model):
    return connection.scalar(select(func.count()).select_from(model))


def test_register_exact_retry_and_metadata_only(test_connection, workspace, registration_input):
    request, plans = registration_input
    receipt = register_synthetic_inventory(test_connection, workspace, request, plans)
    assert receipt.state == RegistrationState.STAGED  # Caller still owns transaction.
    assert count(test_connection, m.TextSample) == 5
    assert count(test_connection, m.Writer) == count(test_connection, m.SourceDocument) == 1
    assert reconcile_registration(test_connection, workspace, request, plans).state == RegistrationState.STAGED
    assert count(test_connection, m.TextSample) == 5
    assert RegistrationReceipt.model_validate_json(workspace._registration_bytes()).request == request
    assert b"ARTIFICIAL REGISTRATION BYTES" not in workspace._registration_bytes()
    assert count(test_connection, m.ExtractionEvent) == count(test_connection, m.ExperimentRun) == 0
    assert len(test_connection.scalars(text("SELECT tablename FROM pg_tables WHERE schemaname='public'")).all()) == 15


def test_database_failure_rolls_back_and_preserves_recovery(test_connection, workspace, registration_input, monkeypatch):
    request, plans = registration_input
    original = registration._register_rows
    def fail(session, inventory):
        original(session, inventory)
        raise RuntimeError("ARTIFICIAL PRIVATE FAILURE")
    monkeypatch.setattr(registration, "_register_rows", fail)
    with pytest.raises(RegistrationError) as error:
        register_synthetic_inventory(test_connection, workspace, request, plans)
    assert "PRIVATE" not in str(error.value)
    assert count(test_connection, m.TextSample) == count(test_connection, m.SourceDocument) == 0
    assert workspace.resolver().verify(plans[0].metadata.reference, caller="synthetic-test")
    assert RegistrationReceipt.model_validate_json(workspace._registration_bytes()).state == RegistrationState.NEEDS_RECONCILIATION
    monkeypatch.setattr(registration, "_register_rows", original)
    assert reconcile_registration(test_connection, workspace, request, plans).state == RegistrationState.STAGED
    assert count(test_connection, m.TextSample) == 5


def test_uncertain_post_savepoint_outcome_is_reconciled(test_connection, workspace, registration_input, monkeypatch):
    request, plans = registration_input
    def fail(stage):
        if stage == "after_database_commit":
            raise OSError("ARTIFICIAL RECEIPT FAILURE")
    monkeypatch.setattr(workspace, "_checkpoint", fail)
    with pytest.raises(RegistrationError):
        register_synthetic_inventory(test_connection, workspace, request, plans)
    assert count(test_connection, m.TextSample) == 5
    assert RegistrationReceipt.model_validate_json(workspace._registration_bytes()).state == RegistrationState.NEEDS_RECONCILIATION
    monkeypatch.setattr(workspace, "_checkpoint", lambda stage: None)
    reconcile_registration(test_connection, workspace, request, plans)
    assert count(test_connection, m.TextSample) == 5


def test_outer_rollback_is_not_mistaken_for_durable_success(test_connection, workspace, registration_input):
    request, plans = registration_input
    inner = test_connection.begin_nested()
    assert register_synthetic_inventory(test_connection, workspace, request, plans).state == RegistrationState.STAGED
    inner.rollback()
    assert count(test_connection, m.TextSample) == 0
    reconcile_registration(test_connection, workspace, request, plans)
    assert count(test_connection, m.TextSample) == 5


def test_changed_request_and_duplicate_logical_slot_are_rejected(test_connection, workspace, registration_input):
    request, plans = registration_input
    register_synthetic_inventory(test_connection, workspace, request, plans)
    changed_slots = (replace(request.inventory.slots[0], id=uuid4()), *request.inventory.slots[1:])
    changed = replace(request, operation_id=uuid4(), inventory=replace(request.inventory, slots=changed_slots))
    with pytest.raises(RegistrationError):
        register_synthetic_inventory(test_connection, workspace, changed, plans)
    with SyntheticWorkspace(authorizer=SyntheticPolicy(), caller="synthetic-test") as other:
        with pytest.raises(RegistrationError):
            register_synthetic_inventory(test_connection, other, changed, plans)
    assert count(test_connection, m.TextSample) == 5


def test_failed_publication_never_registers_metadata(test_connection, workspace, registration_input, monkeypatch):
    request, plans = registration_input
    def fail(stage):
        if stage == "before_payload_rename":
            raise OSError("ARTIFICIAL PUBLISH FAILURE")
    monkeypatch.setattr(workspace, "_checkpoint", fail)
    with pytest.raises(RegistrationError):
        register_synthetic_inventory(test_connection, workspace, request, plans)
    assert count(test_connection, m.Provenance) == count(test_connection, m.TextSample) == 0
    monkeypatch.setattr(workspace, "_checkpoint", lambda stage: None)
    reconcile_registration(test_connection, workspace, request, plans)
    assert count(test_connection, m.TextSample) == 5


def test_receipt_write_failure_after_rows_is_not_complete(test_connection, workspace, registration_input, monkeypatch):
    request, plans = registration_input
    original = workspace._save_registration
    def fail_once(content):
        if json.loads(content)["state"] == RegistrationState.STAGED:
            raise OSError("ARTIFICIAL JOURNAL FAILURE")
        return original(content)
    monkeypatch.setattr(workspace, "_save_registration", fail_once)
    with pytest.raises(RegistrationError):
        register_synthetic_inventory(test_connection, workspace, request, plans)
    assert RegistrationReceipt.model_validate_json(workspace._registration_bytes()).state == RegistrationState.NEEDS_RECONCILIATION
    monkeypatch.setattr(workspace, "_save_registration", original)
    reconcile_registration(test_connection, workspace, request, plans)
    assert count(test_connection, m.TextSample) == 5


def test_provenance_mismatch_is_rejected_before_publication(registration_input):
    request, _ = registration_input
    document = replace(request.inventory.documents[0], byte_sha256="0" * 64)
    with pytest.raises(ValidationError):
        replace(request, inventory=replace(request.inventory, documents=(document,)))


def test_no_automatic_or_development_database_registration(workspace, registration_input, monkeypatch):
    request, plans = registration_input
    engine = create_optional_engine("postgresql+psycopg://localhost/stylometry_dev")
    monkeypatch.setattr(engine, "connect", lambda *a, **k: pytest.fail("Registration contacted development"))
    try:
        with pytest.raises(RegistrationError):
            register_synthetic_inventory(engine, workspace, request, plans)
    finally:
        engine.dispose()
    assert workspace.publication_receipts() == ()


def test_registration_lock_rejects_competing_operation(test_connection, workspace, registration_input):
    request, plans = registration_input
    with workspace._exclusive("registration.lock"):
        with pytest.raises(RegistrationError):
            register_synthetic_inventory(test_connection, workspace, request, plans)
    assert count(test_connection, m.TextSample) == 0
