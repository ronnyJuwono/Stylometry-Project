"""Synchronous synthetic inventory runner. No queue, scheduler, or scientific engine."""

from datetime import datetime, timezone
from uuid import UUID

from stylometry.contracts import RunStatus, canonical_sha256
from stylometry.experiments.configurations import ExecutionPlan
from stylometry.experiments.results import ExecutionReceipt
from stylometry.pipeline.inventory import SyntheticInventory


class SyntheticRunner:
    def __init__(self):
        self._history: list[ExecutionReceipt] = []

    @property
    def history(self) -> tuple[ExecutionReceipt, ...]:
        return tuple(self._history)

    def plan(self, plan: ExecutionPlan) -> ExecutionReceipt:
        plan = ExecutionPlan.model_validate_json(plan.model_dump_json())
        if any(r.plan.id == plan.id for r in self._history):
            raise ValueError("Execution IDs are append-only; allocate a new ID for a rerun")
        receipt = ExecutionReceipt(plan=plan, status=RunStatus.PLANNED)
        self._history.append(receipt)
        return receipt

    def execute(self, run_id: UUID, inventory: SyntheticInventory) -> ExecutionReceipt:
        prior = next((r for r in reversed(self._history) if r.plan.id == run_id), None)
        if prior is None or prior.status != RunStatus.PLANNED:
            raise ValueError("Only an existing planned execution can start")
        plan = prior.plan
        now = datetime.now(timezone.utc)
        succeeded = {r.plan.id for r in self._history if r.status == RunStatus.SUCCEEDED}
        if not set(plan.dependency_run_ids) <= succeeded:
            return self._fail(plan, now, "dependencies_unavailable")
        if plan.operation != "synthetic_inventory":
            return self._fail(plan, now, "scientific_stage_unavailable")
        self._history.append(ExecutionReceipt(plan=plan, status=RunStatus.RUNNING, started_at=now))
        try:
            inventory = SyntheticInventory.model_validate_json(inventory.model_dump_json())
            if (inventory.study.id != plan.inputs.study_id or inventory.corpus.id != plan.inputs.corpus_id
                    or plan.inputs.version != inventory.inventory_version
                    or plan.inputs.snapshot_id is not None or plan.inputs.input_objects):
                raise ValueError
            result = ExecutionReceipt(plan=plan, status=RunStatus.SUCCEEDED, started_at=now,
                finished_at=datetime.now(timezone.utc), inventory_summary=inventory.summary(),
                input_manifest_sha256=canonical_sha256(inventory.model_dump(mode="json")))
        except Exception:
            result = self._fail(plan, now, "invalid_synthetic_inventory", append=False)
        self._history.append(result)
        return result

    def _fail(self, plan, started_at, code, *, append=True):
        receipt = ExecutionReceipt(plan=plan, status=RunStatus.FAILED, started_at=started_at,
            finished_at=datetime.now(timezone.utc), error_code=code)
        if append:
            self._history.append(receipt)
        return receipt

    def cancel(self, run_id: UUID) -> ExecutionReceipt:
        prior = next((r for r in reversed(self._history) if r.plan.id == run_id), None)
        if prior is None or prior.status != RunStatus.PLANNED:
            raise ValueError("Only planned synchronous runs can be cancelled")
        result = ExecutionReceipt(plan=prior.plan, status=RunStatus.CANCELLED,
            finished_at=datetime.now(timezone.utc))
        self._history.append(result)
        return result
