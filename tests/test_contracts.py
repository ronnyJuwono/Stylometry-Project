"""Validate artificial metadata, never compute scientific measurements."""

from datetime import timedelta
from uuid import UUID

import pytest
from pydantic import ValidationError

from stylometry.contracts import (
    AnonymizedWriter, CleanTextDerivation, DatasetSnapshot, ExperimentRun,
    ExtractionEvent, ExtractionStatus, QCContext, QCEvaluation, QCReason, QCStatus,
    ResearchBundle, RunStatus, canonical_sha256,
)
from stylometry.paper1 import REPORTED_CORPORA, TASKS, Task, TaskCode


def fields(record, **updates):
    """Revalidate constructors; model_copy/model_construct bypass validation."""
    return {**record.model_dump(), **updates}


def bundle_with(bundle, **updates):
    return ResearchBundle(**fields(bundle, **updates))


def test_synthetic_graph_json_roundtrip(synthetic_bundle):
    encoded = synthetic_bundle.model_dump_json()
    assert ResearchBundle.model_validate_json(encoded) == synthetic_bundle
    assert all(run.status == RunStatus.PLANNED for run in synthetic_bundle.runs)
    with pytest.raises(ValidationError):
        synthetic_bundle.samples = ()


@pytest.mark.parametrize("change", [
    {"student_name": "synthetic-forbidden-field"},
    {"id": "not-a-uuid"},
])
def test_writer_rejects_unknown_fields_and_untyped_ids(synthetic_bundle, change):
    with pytest.raises(ValidationError):
        AnonymizedWriter(**fields(synthetic_bundle.writers[0], **change))


@pytest.mark.parametrize("change", [
    {"word_count": -1}, {"word_count": "80"}, {"word_threshold": 100},
    {"tokenizer_method_ref": None}, {"derivation_id": None},
    {"evaluated_at": "2026-10-22"},
    {"status": QCStatus.EXCLUDED},
    {"reasons": (QCReason.MISSING_TEXT,)},
])
def test_invalid_sample_qc(synthetic_bundle, change):
    with pytest.raises(ValidationError):
        QCEvaluation(**fields(synthetic_bundle.evaluations[0], **change))


def test_threshold_contexts_remain_separate(synthetic_bundle):
    primary = synthetic_bundle.evaluations[0]
    assert primary.word_count == 80 and primary.status == QCStatus.PASS
    with pytest.raises(ValidationError):
        QCEvaluation(**fields(primary, context=QCContext.SOURCE_INVENTORY_100, word_threshold=100))
    inventory = QCEvaluation(**fields(
        primary, context=QCContext.SOURCE_INVENTORY_100, word_threshold=100,
        status=QCStatus.EXCLUDED, reasons=(QCReason.BELOW_WORD_THRESHOLD,),
    ))
    assert inventory.word_count == primary.word_count
    sensitivity = QCEvaluation(**fields(inventory, context=QCContext.SENSITIVITY_100))
    assert sensitivity.context != inventory.context


def test_missing_duplicate_and_writer_exclusions(synthetic_bundle):
    sample = synthetic_bundle.evaluations[0]
    missing = QCEvaluation(**fields(
        sample, status=QCStatus.EXCLUDED, reasons=(QCReason.MISSING_TEXT,),
        derivation_id=None, word_count=None, tokenizer_method_ref=None,
    ))
    assert missing.word_count is None  # Missing is not a measured zero.
    duplicate = QCEvaluation(**fields(
        sample, status=QCStatus.EXCLUDED, reasons=(QCReason.DUPLICATE_TEXT,),
        related_sample_ids=(synthetic_bundle.samples[1].id,), evidence_ref=UUID(int=9999),
    ))
    with pytest.raises(ValidationError):
        QCEvaluation(**fields(duplicate, evidence_ref=None))
    with pytest.raises(ValidationError):
        QCEvaluation(**fields(duplicate, related_sample_ids=(sample.target_id,)))
    writer = synthetic_bundle.evaluations[-1]
    excluded = QCEvaluation(**fields(
        writer, status=QCStatus.EXCLUDED, reasons=(QCReason.INSUFFICIENT_ELIGIBLE_TASKS,),
        eligible_task_count=3,
    ))
    assert excluded.minimum_eligible_tasks == 4
    with pytest.raises(ValidationError):
        QCEvaluation(**fields(excluded, eligible_task_count=4))


def test_unknown_balanced_threshold_has_no_default(synthetic_bundle):
    sample = synthetic_bundle.evaluations[0]
    with pytest.raises(ValidationError):
        QCEvaluation(**fields(sample, context=QCContext.BALANCED_FIVE_TASK, word_threshold=None))


def test_inclusive_threshold_boundary_and_reason_consistency(synthetic_bundle):
    sample = synthetic_bundle.evaluations[0]
    excluded = QCEvaluation(**fields(
        sample, word_count=79, status=QCStatus.EXCLUDED,
        reasons=(QCReason.BELOW_WORD_THRESHOLD,),
    ))
    assert excluded.word_threshold == 80
    with pytest.raises(ValidationError):
        QCEvaluation(**fields(excluded, word_count=80))
    with pytest.raises(ValidationError):
        QCEvaluation(**fields(sample, word_count=79))


def test_hashes_and_timestamps(synthetic_bundle):
    event = synthetic_bundle.extractions[0]
    for change in (
        {"finished_at": event.started_at - timedelta(seconds=1)},
        {"started_at": event.started_at.replace(tzinfo=None)},
        {"extracted_byte_sha256": "bad-digest"},
        {"status": ExtractionStatus.FAILED},
        {"extracted_object_ref": None},
    ):
        with pytest.raises(ValidationError):
            ExtractionEvent(**fields(event, **change))
    failed = ExtractionEvent(**fields(
        event, status=ExtractionStatus.FAILED, extracted_object_ref=None, extracted_byte_sha256=None,
    ))
    assert failed.extracted_byte_sha256 is None


def test_clean_lineage_and_append_only_versions(synthetic_bundle):
    first = synthetic_bundle.derivations[0]
    second = CleanTextDerivation(**fields(
        first, id=UUID(int=8000), version=2, parent_derivation_id=first.id,
    ))
    valid = bundle_with(synthetic_bundle, derivations=(*synthetic_bundle.derivations, second))
    assert valid.derivations[-1].parent_derivation_id == first.id
    for change in (
        {"version": 3},
        {"parent_derivation_id": synthetic_bundle.derivations[1].id},
        {"parent_derivation_id": UUID(int=8001)},
    ):
        changed = CleanTextDerivation(**fields(second, **change))
        with pytest.raises(ValidationError):
            bundle_with(synthetic_bundle, derivations=(*synthetic_bundle.derivations, changed))
    with pytest.raises(ValidationError):
        CleanTextDerivation(**fields(first, parent_derivation_id=first.id))
    # A second extraction may start its own v1 chain; no overwriting of first v1.
    event = ExtractionEvent(**fields(synthetic_bundle.extractions[0], id=UUID(int=8002)))
    reextracted = CleanTextDerivation(**fields(first, id=UUID(int=8003), extraction_event_id=event.id))
    bundle_with(synthetic_bundle, extractions=(*synthetic_bundle.extractions, event),
                derivations=(*synthetic_bundle.derivations, reextracted))


def test_unresolved_foreign_keys_and_duplicate_slots(synthetic_bundle):
    with pytest.raises(ValidationError):
        bundle_with(synthetic_bundle, documents=())
    repeated = type(synthetic_bundle.samples[0])(**fields(synthetic_bundle.samples[0], id=UUID(int=8000)))
    with pytest.raises(ValidationError):
        bundle_with(synthetic_bundle, samples=(*synthetic_bundle.samples, repeated))


def test_snapshot_hash_and_membership_guards(synthetic_bundle):
    snapshot = synthetic_bundle.snapshots[0]
    data = snapshot.model_dump(mode="json", exclude={"manifest_sha256"})
    assert canonical_sha256(data) == snapshot.manifest_sha256
    assert canonical_sha256({"b": 2, "a": 1}) == canonical_sha256({"a": 1, "b": 2})
    for change in (
        {"version": "tampered"},
        {"members": tuple(reversed(snapshot.members))},
        {"context": QCContext.SOURCE_INVENTORY_100},
        {"members": (*snapshot.members, snapshot.members[0])},
    ):
        with pytest.raises(ValidationError):
            DatasetSnapshot(**fields(snapshot, **change))
    changed_member = type(snapshot.members[0])(**fields(snapshot.members[0], clean_byte_sha256="1" * 64))
    payload = fields(snapshot, members=(changed_member, *snapshot.members[1:]))
    # Rehash a structurally valid but referentially incorrect snapshot.
    from pydantic import TypeAdapter
    manifest = TypeAdapter(dict).dump_python({k: v for k, v in payload.items() if k != "manifest_sha256"}, mode="json")
    changed = DatasetSnapshot(**{**payload, "manifest_sha256": canonical_sha256(manifest)})
    with pytest.raises(ValidationError):
        bundle_with(synthetic_bundle, snapshots=(changed,))


def test_inventory_receipt_cannot_admit_analytical_member(synthetic_bundle):
    qc = synthetic_bundle.evaluations[0]
    inventory = QCEvaluation(**fields(
        qc, context=QCContext.SOURCE_INVENTORY_100, word_threshold=100, word_count=100,
    ))
    with pytest.raises(ValidationError):
        bundle_with(synthetic_bundle, evaluations=(inventory, *synthetic_bundle.evaluations[1:]))


def test_snapshot_configuration_and_writer_coverage(synthetic_bundle):
    first = synthetic_bundle.evaluations[0]
    repro = type(first.reproducibility)(**fields(
        first.reproducibility, configuration_version="different.v2",
    ))
    changed = QCEvaluation(**fields(first, reproducibility=repro))
    with pytest.raises(ValidationError):
        bundle_with(synthetic_bundle, evaluations=(changed, *synthetic_bundle.evaluations[1:]))
    writer = synthetic_bundle.evaluations[-1]
    changed_writer = QCEvaluation(**fields(writer, eligible_task_count=5))
    with pytest.raises(ValidationError):
        bundle_with(synthetic_bundle, evaluations=(*synthetic_bundle.evaluations[:-1], changed_writer))


def test_cross_corpus_and_failed_extraction_lineage(synthetic_bundle):
    # Individually valid documents/events must still fit the complete graph.
    document = synthetic_bundle.documents[0]
    changed = type(document)(**fields(document, corpus_id=UUID(int=9990)))
    with pytest.raises(ValidationError):
        bundle_with(synthetic_bundle, documents=(changed,))
    event = synthetic_bundle.extractions[0]
    failed = ExtractionEvent(**fields(
        event, status=ExtractionStatus.FAILED, extracted_object_ref=None, extracted_byte_sha256=None,
    ))
    with pytest.raises(ValidationError):
        bundle_with(synthetic_bundle, extractions=(failed, *synthetic_bundle.extractions[1:]))


def test_run_snapshot_integrity_and_valid_lifecycles(synthetic_bundle):
    planned = synthetic_bundle.runs[0]
    changed = ExperimentRun(**fields(planned, snapshot_manifest_sha256="1" * 64))
    with pytest.raises(ValidationError):
        bundle_with(synthetic_bundle, runs=(changed,))
    for status in (RunStatus.SUCCEEDED, RunStatus.FAILED):
        finished = ExperimentRun(**fields(
            planned, status=status, started_at=planned.created_at,
            finished_at=planned.created_at + timedelta(seconds=1),
        ))
        bundle_with(synthetic_bundle, runs=(finished,))
    cancelled = ExperimentRun(**fields(planned, status=RunStatus.CANCELLED, finished_at=planned.created_at))
    with pytest.raises(ValidationError):
        ExperimentRun(**fields(cancelled, output_provenance_ids=(UUID(int=1),)))


def test_task_definition_cannot_silently_change():
    with pytest.raises(ValidationError):
        Task(code=TaskCode.T05, genre="narrative", form="paragraph")


@pytest.mark.parametrize("change", [
    {"finished_at": "2026-10-22"}, {"stage_number": 10},
    {"status": RunStatus.SUCCEEDED}, {"status": RunStatus.RUNNING},
    {"output_provenance_ids": (UUID(int=1),)},
])
def test_planned_runs_cannot_imply_execution(synthetic_bundle, change):
    with pytest.raises(ValidationError):
        ExperimentRun(**fields(synthetic_bundle.runs[0], **change))


def test_reference_counts_are_not_measurements_or_snapshot_constraints(synthetic_bundle):
    assert [(r.students, r.texts) for r in REPORTED_CORPORA] == [(46, 200), (35, 163), (24, 110), (23, 115)]
    assert REPORTED_CORPORA[0].potential_task_slots == 230
    assert all(r.basis == "reported_reference_not_recomputed" for r in REPORTED_CORPORA)
    assert len(synthetic_bundle.snapshots[0].members) == 4  # Not forced to reported 163.
    assert [t.code for t in TASKS] == list(TaskCode)
    assert TASKS[-1].form == "essay" and TASKS[-2].form == "paragraph"
