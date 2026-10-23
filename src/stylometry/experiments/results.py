"""Synthetic execution receipt; not a persisted S2A research-run claim."""

from pydantic import model_validator

from stylometry.contracts import Contract, Label, RunStatus, Sha256, Timestamp
from stylometry.experiments.configurations import ExecutionPlan
from stylometry.pipeline.inventory import InventorySummary


class ExecutionReceipt(Contract):
    plan: ExecutionPlan
    status: RunStatus
    started_at: Timestamp | None = None
    finished_at: Timestamp | None = None
    input_manifest_sha256: Sha256 | None = None
    inventory_summary: InventorySummary | None = None
    error_code: Label | None = None

    @model_validator(mode="after")
    def validate_state(self):
        if self.started_at is not None and self.started_at < self.plan.created_at:
            raise ValueError("Execution start precedes plan")
        if self.finished_at is not None and self.finished_at < (self.started_at or self.plan.created_at):
            raise ValueError("Execution finish precedes start/plan")
        if self.status == RunStatus.PLANNED and (self.started_at or self.finished_at or self.inventory_summary or self.error_code):
            raise ValueError("Planned is not executed")
        if self.status == RunStatus.RUNNING and (self.started_at is None or self.finished_at is not None):
            raise ValueError("Running requires start only")
        if self.status in (RunStatus.SUCCEEDED, RunStatus.FAILED) and (self.started_at is None or self.finished_at is None):
            raise ValueError("Terminal execution needs start/finish")
        if self.status == RunStatus.CANCELLED and self.finished_at is None:
            raise ValueError("Cancellation requires finish")
        if self.status == RunStatus.SUCCEEDED and (self.inventory_summary is None or self.error_code is not None):
            raise ValueError("Synthetic success requires a summary and no error")
        if self.status == RunStatus.SUCCEEDED and (self.plan.operation != "synthetic_inventory" or self.input_manifest_sha256 is None):
            raise ValueError("Only a hashed synthetic inventory execution can succeed")
        if self.status != RunStatus.SUCCEEDED and self.inventory_summary is not None:
            raise ValueError("Only successful synthetic execution has a result")
        if self.status == RunStatus.FAILED and self.error_code is None:
            raise ValueError("Failed execution requires a safe error code")
        return self
