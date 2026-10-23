"""Engineering execution plans; private parameters are references, not text."""

from typing import Literal
from uuid import UUID

from pydantic import model_validator

from stylometry.contracts import Contract, Reproducibility, Timestamp
from stylometry.pipeline.interfaces import StageInput


class ExecutionPlan(Contract):
    id: UUID
    operation: Literal["synthetic_inventory", "scientific_stage"]
    inputs: StageInput
    dependency_run_ids: tuple[UUID, ...] = ()
    reproducibility: Reproducibility
    created_at: Timestamp

    @model_validator(mode="after")
    def validate_dependencies(self):
        if (self.inputs.reproducibility != self.reproducibility
                or len(set(self.dependency_run_ids)) != len(self.dependency_run_ids)
                or self.id in self.dependency_run_ids):
            raise ValueError("Execution configuration or dependencies are inconsistent")
        return self
