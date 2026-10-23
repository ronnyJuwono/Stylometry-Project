"""Run with python -m stylometry.pipeline.demo. Artificial bytes; no SQL or UI."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
from uuid import uuid4

from stylometry import contracts as c
from stylometry.experiments.configurations import ExecutionPlan
from stylometry.experiments.runner import SyntheticRunner
from stylometry.pipeline.interfaces import StageInput
from stylometry.pipeline.inventory import (
    AuthorshipEntity, InventorySlot, InventoryUnit, StudyCode, StudyPlan,
    SubmissionState, SyntheticInventory,
)
from stylometry.synthetic_publishing import SyntheticWorkspace


class _DemonstrationPolicy:
    """Test capability for a fresh temporary workspace, never production identity."""
    def __init__(self, capability):
        self._capability = capability

    def allows_read(self, caller, reference):
        return caller is self._capability


def synthetic_demo() -> dict:
    repository = Path(__file__).resolve().parents[3]
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repository).decode().strip()
    dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=repository))
    configuration = {"synthetic_only": True, "operation": "inventory_demo.v1"}
    repro = c.Reproducibility(configuration_version="synthetic.demo.v1", configuration_ref=uuid4(),
        configuration_sha256=c.canonical_sha256(configuration), code_commit=commit,
        working_tree_dirty=dirty, environment_lock_sha256=hashlib.sha256((repository / "uv.lock").read_bytes()).hexdigest())
    capability = object()
    with SyntheticWorkspace(authorizer=_DemonstrationPolicy(capability), caller=capability) as workspace:
        now, provenance_id, document_id = datetime.now(timezone.utc), uuid4(), uuid4()
        plan = workspace.prepare(b"ARTIFICIAL DEMONSTRATION BYTES ONLY", series_ref=document_id,
            provenance_id=provenance_id, version="synthetic.source.v1", reproducibility=repro)
        ref = plan.metadata.reference
        provenance = c.Provenance(id=provenance_id, recorded_at=now, evidence_ref=uuid4(),
            evidence_sha256=c.canonical_sha256({"artificial_metadata_evidence_stub": True}))
        corpus = c.Corpus(id=uuid4(), version="synthetic.demo.v1", created_at=now, provenance_id=provenance.id)
        author = AuthorshipEntity(id=uuid4(), kind="individual")
        unit = InventoryUnit(id=uuid4(), author_id=author.id, kind="task_collection")
        study = StudyPlan(id=uuid4(), code=StudyCode.P1, slot_codes=("T01", "T02", "T03", "T04", "T05"))
        source = c.SourceDocument(id=document_id, corpus_id=corpus.id, private_object_ref=ref.object_ref,
            byte_sha256=ref.byte_sha256, media_type=ref.media_type, provenance_id=provenance.id, acquired_at=now)
        slots = tuple(InventorySlot(id=uuid4(), unit_id=unit.id, slot_code=code,
            status=SubmissionState.PRESENT if index == 0 else SubmissionState.MISSING if index % 2 == 0 else SubmissionState.UNRESOLVED,
            source_document_id=source.id if index == 0 else None, provenance_id=provenance.id)
            for index, code in enumerate(study.slot_codes))
        inventory = SyntheticInventory(synthetic_only=True, study=study, corpus=corpus,
            inventory_version="synthetic.inventory.v1", provenance=(provenance,), authors=(author,),
            units=(unit,), documents=(source,), slots=slots)
        workspace.publish(plan)
        verified = workspace.resolver().read(ref, caller=capability) == plan.content
        runner = SyntheticRunner()
        execution = ExecutionPlan(id=uuid4(), operation="synthetic_inventory", created_at=now, reproducibility=repro,
            inputs=StageInput(study_id=study.id, corpus_id=corpus.id, input_objects=(),
                approved_method_ref=uuid4(), parameters_ref=uuid4(), version=inventory.inventory_version,
                reproducibility=repro))
        runner.plan(execution)
        receipt = runner.execute(execution.id, inventory)
        return {"synthetic_only": True, "summary": inventory.summary().model_dump(mode="json"),
                "publication_verified": verified, "synthetic_run_status": str(receipt.status),
                "scientific_stages_executed": 0, "postgresql_accessed": False}


if __name__ == "__main__":
    print(json.dumps(synthetic_demo(), indent=2))
