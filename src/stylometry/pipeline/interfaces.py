"""Typed scientific stage boundaries; no methods are approved/executable here."""

from enum import StrEnum
from typing import Protocol
from uuid import UUID

from stylometry.contracts import Contract, Label, Reproducibility
from stylometry.storage import StorageReference


class ProcessingMethod(StrEnum):
    EXTRACTION = "extraction"
    CLEANING = "cleaning"
    QUALITY_CONTROL = "quality_control"
    FEATURE_ENGINEERING = "feature_engineering"


class StageInput(Contract):
    study_id: UUID
    corpus_id: UUID
    snapshot_id: UUID | None = None
    input_objects: tuple[StorageReference, ...]
    approved_method_ref: UUID
    parameters_ref: UUID
    version: Label
    reproducibility: Reproducibility


class StageOutput(Contract):
    output_objects: tuple[StorageReference, ...]
    provenance_ids: tuple[UUID, ...]
    receipt_ref: UUID


class StageUnavailable(RuntimeError):
    pass


class ResearchStage(Protocol):
    def execute(self, inputs: StageInput) -> StageOutput:
        """Future implementation must validate approvals/dependencies and append evidence."""
        ...


def execute_processing(method: ProcessingMethod, inputs: StageInput) -> StageOutput:
    raise StageUnavailable("Scientific processing method is unavailable pending separate approval.")
