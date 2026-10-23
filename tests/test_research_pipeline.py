"""Synthetic-only planning/runner contracts; no scientific values computed."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from stylometry import contracts as c
from stylometry.analysis.interfaces import AnalysisMethod, execute_analysis
from stylometry.experiments.configurations import ExecutionPlan
from stylometry.experiments.runner import SyntheticRunner
from stylometry.pipeline.interfaces import ProcessingMethod, StageInput, StageUnavailable, execute_processing
from stylometry.pipeline.inventory import (
    AuthorshipEntity, InventorySlot, InventoryUnit, StudyCode, StudyPlan,
    SubmissionState, SyntheticInventory,
)


def make_inventory(reference=None, *, document_id=None, study=StudyCode.P1):
    now = datetime.now(timezone.utc)
    provenance_id = reference.provenance_id if reference else uuid4()
    provenance = c.Provenance(id=provenance_id, recorded_at=now,
        evidence_ref=uuid4(), evidence_sha256=c.canonical_sha256({"artificial_evidence": True}))
    corpus = c.Corpus(id=uuid4(), version="synthetic.v1", created_at=now, provenance_id=provenance.id)
    codes = ("T01", "T02", "T03", "T04", "T05") if study == StudyCode.P1 else ("section_A", "section_B")
    author = AuthorshipEntity(id=uuid4(), kind="group" if study == StudyCode.P2 else "individual")
    unit = InventoryUnit(id=uuid4(), author_id=author.id,
        kind={StudyCode.P1: "task_collection", StudyCode.P2: "section_document", StudyCode.D1: "submission"}[study])
    documents = ()
    if reference:
        documents = (c.SourceDocument(id=document_id or uuid4(), corpus_id=corpus.id,
            private_object_ref=reference.object_ref, byte_sha256=reference.byte_sha256,
            media_type=reference.media_type, provenance_id=provenance.id, acquired_at=now),)
    slots = tuple(InventorySlot(id=uuid4(), unit_id=unit.id, slot_code=code,
        status=SubmissionState.PRESENT if documents and index == 0 else
               SubmissionState.MISSING if index % 2 == 0 else SubmissionState.UNRESOLVED,
        source_document_id=documents[0].id if documents and index == 0 else None,
        provenance_id=provenance.id) for index, code in enumerate(codes))
    return SyntheticInventory(synthetic_only=True, study=StudyPlan(id=uuid4(), code=study, slot_codes=codes),
        inventory_version="synthetic.inventory.v1", corpus=corpus, provenance=(provenance,),
        authors=(author,), units=(unit,), documents=documents, slots=slots)


def replace(model, **changes):
    return type(model)(**{**model.model_dump(), **changes})


@pytest.mark.parametrize("study,expected", [(StudyCode.P1, 5), (StudyCode.P2, 2), (StudyCode.D1, 2)])
def test_study_specific_inventory_and_summary(study, expected):
    inventory = make_inventory(study=study)
    summary = inventory.summary()
    assert summary.complete and summary.expected_slots == summary.declared_slots == expected
    assert summary.present == 0
    assert summary.missing + summary.unresolved == expected
    assert SyntheticInventory.model_validate_json(inventory.model_dump_json()) == inventory
    if study != StudyCode.P1:
        with pytest.raises(ValueError):
            inventory.as_p1_bundle()
    else:
        assert len(inventory.as_p1_bundle().samples) == 5


def test_undeclared_slots_are_not_invented_missing_submissions():
    inventory = make_inventory()
    partial = replace(inventory, slots=inventory.slots[:-1])
    assert not partial.summary().complete and len(partial.summary().undeclared_slots) == 1
    assert partial.summary().declared_slots == 4
    with pytest.raises(ValueError):
        partial.as_p1_bundle()


def test_duplicate_logical_slot_is_not_duplicate_text():
    inventory = make_inventory()
    duplicate = replace(inventory.slots[0], id=uuid4())
    with pytest.raises(ValidationError, match="Duplicate logical slot"):
        replace(inventory, slots=(*inventory.slots, duplicate))


@pytest.mark.parametrize("change", ["unit", "provenance", "document", "task", "writer", "corpus_provenance"])
def test_invalid_inventory_references(change):
    inv = make_inventory()
    with pytest.raises(ValidationError):
        if change == "writer":
            replace(inv, units=(replace(inv.units[0], author_id=uuid4()),))
        elif change == "corpus_provenance":
            replace(inv, corpus=replace(inv.corpus, provenance_id=uuid4()))
        else:
            updates = {"unit": {"unit_id": uuid4()}, "provenance": {"provenance_id": uuid4()},
                "document": {"status": SubmissionState.PRESENT, "source_document_id": uuid4()},
                "task": {"slot_code": "not_a_declared_slot"}}[change]
            replace(inv, slots=(replace(inv.slots[0], **updates), *inv.slots[1:]))


def test_p1_definition_group_and_repeated_unit_are_rejected():
    inv = make_inventory()
    with pytest.raises(ValidationError):
        replace(inv.study, slot_codes=("T01",))
    with pytest.raises(ValidationError):
        replace(inv, authors=(replace(inv.authors[0], kind="group"),))
    with pytest.raises(ValidationError):
        replace(inv, units=(*inv.units, replace(inv.units[0], id=uuid4())))


def test_dissertation_repeated_submissions_and_reference_categories():
    inv = make_inventory(study=StudyCode.D1)
    draft = replace(inv.units[0], id=uuid4(), parent_unit_id=inv.units[0].id)
    reference = replace(inv.units[0], id=uuid4(), kind="reference", reference_category="synthetic_reference")
    extended = replace(inv, units=(*inv.units, draft, reference))
    assert extended.summary().expected_slots == 6 and not extended.summary().complete
    with pytest.raises(ValidationError):
        replace(inv, units=(replace(inv.units[0], parent_unit_id=inv.units[0].id),))
    with pytest.raises(ValidationError):
        replace(inv, units=(replace(inv.units[0], kind="reference"),))


def test_p2_group_sections_and_equal_hashes_are_not_duplicate_slots():
    from stylometry.storage import StorageReference
    ref = StorageReference(object_ref=uuid4(), byte_sha256="0" * 64,
        provenance_id=uuid4(), media_type="application/octet-stream", processing_version="synthetic.v1")
    inv = make_inventory(ref, study=StudyCode.P2)
    unit = replace(inv.units[0], id=uuid4())
    document = replace(inv.documents[0], id=uuid4(), private_object_ref=uuid4())
    more_slots = tuple(replace(slot, id=uuid4(), unit_id=unit.id,
        source_document_id=document.id if slot.source_document_id else None) for slot in inv.slots)
    extended = replace(inv, units=(*inv.units, unit), documents=(*inv.documents, document),
        slots=(*inv.slots, *more_slots))
    assert extended.summary().complete and extended.summary().present == 2
    assert extended.documents[0].byte_sha256 == extended.documents[1].byte_sha256
    # No text equality adjudication or scientific exclusion is performed.


@pytest.mark.parametrize("method", list(ProcessingMethod))
def test_processing_stages_are_explicitly_unavailable(method):
    with pytest.raises(StageUnavailable):
        execute_processing(method, None)


@pytest.mark.parametrize("method", list(AnalysisMethod))
def test_analysis_stages_are_explicitly_unavailable(method):
    with pytest.raises(StageUnavailable):
        execute_analysis(method, None)


def execution_plan(inventory, repro, **changes):
    inputs = StageInput(study_id=inventory.study.id, corpus_id=inventory.corpus.id,
        input_objects=(), approved_method_ref=uuid4(), parameters_ref=uuid4(),
        version=inventory.inventory_version, reproducibility=repro)
    return ExecutionPlan(id=uuid4(), operation="synthetic_inventory", inputs=inputs,
        reproducibility=repro, created_at=datetime.now(timezone.utc), **changes)


def test_runner_lifecycle_dependencies_reruns_and_cancellation(synthetic_bundle):
    inv = make_inventory()
    repro = synthetic_bundle.runs[0].reproducibility
    runner = SyntheticRunner()
    first = execution_plan(inv, repro)
    assert runner.plan(first).status == c.RunStatus.PLANNED
    result = runner.execute(first.id, inv)
    assert result.status == c.RunStatus.SUCCEEDED and result.inventory_summary == inv.summary()
    assert [r.status for r in runner.history] == [c.RunStatus.PLANNED, c.RunStatus.RUNNING, c.RunStatus.SUCCEEDED]
    assert result.input_manifest_sha256 == c.canonical_sha256(inv.model_dump(mode="json"))
    rerun = execution_plan(inv, repro, dependency_run_ids=(first.id,))
    runner.plan(rerun)
    assert runner.execute(rerun.id, inv).status == c.RunStatus.SUCCEEDED
    with pytest.raises(ValueError):
        runner.plan(first)
    with pytest.raises(ValueError):
        runner.execute(first.id, inv)
    planned = execution_plan(inv, repro)
    runner.plan(planned)
    assert runner.cancel(planned.id).status == c.RunStatus.CANCELLED


def test_runner_rejects_unavailable_stages_and_dependencies(synthetic_bundle):
    inv = make_inventory()
    repro = synthetic_bundle.runs[0].reproducibility
    runner = SyntheticRunner()
    missing = execution_plan(inv, repro, dependency_run_ids=(uuid4(),))
    runner.plan(missing)
    assert runner.execute(missing.id, inv).error_code == "dependencies_unavailable"
    scientific = replace(execution_plan(inv, repro), operation="scientific_stage")
    runner.plan(scientific)
    assert runner.execute(scientific.id, inv).error_code == "scientific_stage_unavailable"
    invalid = execution_plan(inv, repro)
    runner.plan(invalid)
    assert runner.execute(invalid.id, make_inventory()).status == c.RunStatus.FAILED


def test_independent_synthetic_demo_without_database(monkeypatch):
    from sqlalchemy.engine import Engine
    from stylometry.pipeline.demo import synthetic_demo
    monkeypatch.setattr(Engine, "connect", lambda *a, **k: pytest.fail("Demo contacted SQL"))
    result = synthetic_demo()
    assert result["publication_verified"] and result["synthetic_run_status"] == "succeeded"
    assert result["scientific_stages_executed"] == 0 and not result["postgresql_accessed"]
    assert result["summary"]["present"] == 1 and result["summary"]["expected_slots"] == 5


def test_dashboard_never_runs_new_workflows(monkeypatch):
    from pathlib import Path
    from sqlalchemy.engine import Engine
    from streamlit.testing.v1 import AppTest
    from stylometry.synthetic_publishing import SyntheticWorkspace
    monkeypatch.setattr(Engine, "connect", lambda *a, **k: pytest.fail("Startup contacted SQL"))
    monkeypatch.setattr(SyntheticWorkspace, "__enter__", lambda *a, **k: pytest.fail("Startup created synthetic files"))
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py").run()
    assert not app.exception
