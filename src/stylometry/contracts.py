"""Validated metadata contracts, not ORM models or an analysis pipeline.

No raw writing, identifying fields, filesystem paths, or source URLs are modeled.
Opaque references resolve only through a future approved private storage service.
"""

import hashlib
import json
from datetime import datetime, timezone
from enum import StrEnum
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import (
    AfterValidator, BaseModel, ConfigDict, Field, StringConstraints, model_validator,
)

from stylometry.paper1 import TaskCode

Label = Annotated[str, StringConstraints(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9_.-]+$")]
Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
Commit = Annotated[str, StringConstraints(pattern=r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")]
NonNegative = Annotated[int, Field(ge=0)]
Positive = Annotated[int, Field(gt=0)]


def aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Timestamp must include a timezone")
    return value.astimezone(timezone.utc)


Timestamp = Annotated[datetime, AfterValidator(aware_utc)]


def canonical_sha256(value: object) -> str:
    """Hash JSON metadata using UTF-8, sorted keys, compact separators, no NaN.

    This is a proposed application manifest encoding, not text normalization.
    Arrays retain order; snapshot member arrays must be sorted by sample UUID.
    """
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=True, allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class Contract(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


class Provenance(Contract):
    id: UUID
    recorded_at: Timestamp
    evidence_ref: UUID
    evidence_sha256: Sha256
    # Evidence bytes and locators stay in approved private storage, outside Git.


class Corpus(Contract):
    id: UUID
    version: Label
    created_at: Timestamp
    provenance_id: UUID


class AnonymizedWriter(Contract):
    id: UUID
    corpus_id: UUID
    # UUID is an internal pseudonym, never a student ID or identity mapping.


class SourceDocument(Contract):
    id: UUID
    corpus_id: UUID
    private_object_ref: UUID
    byte_sha256: Sha256
    media_type: Literal[
        "application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/plain", "application/octet-stream",
    ]
    provenance_id: UUID
    acquired_at: Timestamp


class TextSample(Contract):
    """A logical writer/task slot; missing writing is still representable."""
    id: UUID
    corpus_id: UUID
    writer_id: UUID
    task: TaskCode
    provenance_id: UUID


class Reproducibility(Contract):
    contract_version: Literal["s2a.v1"] = "s2a.v1"
    configuration_version: Label
    configuration_ref: UUID
    configuration_sha256: Sha256
    code_commit: Commit
    working_tree_dirty: bool
    environment_lock_sha256: Sha256


class ExtractionStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class ExtractionEvent(Contract):
    id: UUID
    sample_id: UUID
    source_document_id: UUID
    source_span_ref: UUID  # private page/paragraph/task mapping evidence
    provenance_id: UUID
    method_ref: UUID  # approved extractor specification/version, no assumed extractor
    reproducibility: Reproducibility
    started_at: Timestamp
    finished_at: Timestamp
    status: ExtractionStatus
    extracted_object_ref: UUID | None = None
    extracted_byte_sha256: Sha256 | None = None

    @model_validator(mode="after")
    def validate_event(self) -> Self:
        if self.finished_at < self.started_at:
            raise ValueError("Extraction finish precedes start")
        has_output = self.extracted_object_ref is not None and self.extracted_byte_sha256 is not None
        has_any = self.extracted_object_ref is not None or self.extracted_byte_sha256 is not None
        if (self.status == ExtractionStatus.SUCCEEDED and not has_output
                or self.status == ExtractionStatus.FAILED and has_any):
            raise ValueError("Extraction output must match status")
        return self


class CleanTextDerivation(Contract):
    id: UUID
    sample_id: UUID
    extraction_event_id: UUID
    parent_derivation_id: UUID | None = None
    version: Positive
    private_object_ref: UUID
    byte_sha256: Sha256
    method_ref: UUID
    provenance_id: UUID
    reproducibility: Reproducibility
    created_at: Timestamp

    @model_validator(mode="after")
    def validate_parent(self) -> Self:
        if self.parent_derivation_id == self.id:
            raise ValueError("Derivation cannot be its own parent")
        if (self.version == 1) != (self.parent_derivation_id is None):
            raise ValueError("Only version one has no parent")
        return self


class QCContext(StrEnum):
    SOURCE_INVENTORY_100 = "source_inventory_100"
    PRIMARY_80 = "primary_80"
    SENSITIVITY_100 = "sensitivity_100"
    BALANCED_FIVE_TASK = "balanced_five_task"


class QCStatus(StrEnum):
    NOT_EVALUATED = "not_evaluated"
    PASS = "pass"
    EXCLUDED = "excluded"
    REVIEW_REQUIRED = "review_required"


class QCReason(StrEnum):
    MISSING_TEXT = "missing_text"
    BELOW_WORD_THRESHOLD = "below_word_threshold"
    DUPLICATE_TEXT = "duplicate_text"
    INSUFFICIENT_ELIGIBLE_TASKS = "insufficient_eligible_tasks"
    EXTRACTION_FAILED = "extraction_failed"
    UNRESOLVED_METHOD = "unresolved_method"


class QCEvaluation(Contract):
    """An explicitly supplied decision receipt; does not calculate eligibility."""
    id: UUID
    target_kind: Literal["sample", "writer"]
    target_id: UUID
    context: QCContext
    status: QCStatus
    reasons: tuple[QCReason, ...] = ()
    derivation_id: UUID | None = None
    word_count: NonNegative | None = None
    word_threshold: Positive | None = None
    tokenizer_method_ref: UUID | None = None
    eligible_task_count: Annotated[int, Field(ge=0, le=5)] | None = None
    minimum_eligible_tasks: Annotated[int, Field(ge=1, le=5)] | None = None
    related_sample_ids: tuple[UUID, ...] = ()
    evidence_ref: UUID | None = None
    provenance_id: UUID
    reproducibility: Reproducibility
    evaluated_at: Timestamp

    @model_validator(mode="after")
    def validate_decision(self) -> Self:
        if len(set(self.reasons)) != len(self.reasons):
            raise ValueError("QC reasons must be unique")
        if self.status in (QCStatus.PASS, QCStatus.NOT_EVALUATED) and self.reasons:
            raise ValueError("Pass/unassessed decisions cannot have exclusion reasons")
        if self.status in (QCStatus.EXCLUDED, QCStatus.REVIEW_REQUIRED) and not self.reasons:
            raise ValueError("Excluded/review decisions need reasons")
        expected = {QCContext.SOURCE_INVENTORY_100: 100, QCContext.PRIMARY_80: 80,
                    QCContext.SENSITIVITY_100: 100}.get(self.context)
        if expected is not None and self.word_threshold != expected:
            raise ValueError("Word threshold must match the named QC context")
        if (self.word_count is None) != (self.tokenizer_method_ref is None):
            raise ValueError("Word counts require a tokenizer method reference and vice versa")
        if self.target_kind == "writer" and (
            self.derivation_id is not None or self.word_count is not None or self.related_sample_ids
        ):
            raise ValueError("Text-specific measurements belong to sample QC")
        if self.target_kind == "sample" and (
            self.eligible_task_count is not None or self.minimum_eligible_tasks is not None
        ):
            raise ValueError("Task eligibility counts belong to writer QC")
        if self.word_count is not None and self.derivation_id is None:
            raise ValueError("Word count must identify the exact text derivation")
        if QCReason.BELOW_WORD_THRESHOLD in self.reasons:
            if (self.word_count is None or self.word_threshold is None
                    or self.word_count >= self.word_threshold):
                raise ValueError("Word exclusion needs a count below its recorded threshold")
        if QCReason.MISSING_TEXT in self.reasons:
            if self.target_kind != "sample" or self.derivation_id is not None or self.word_count is not None:
                raise ValueError("Missing text cannot carry a text derivation or count")
        if QCReason.DUPLICATE_TEXT in self.reasons:
            if (self.target_kind != "sample" or not self.related_sample_ids
                    or self.target_id in self.related_sample_ids or self.evidence_ref is None):
                raise ValueError("Duplicate exclusion requires other samples and private evidence")
        if len(set(self.related_sample_ids)) != len(self.related_sample_ids):
            raise ValueError("Duplicate sample references must be unique")
        if QCReason.INSUFFICIENT_ELIGIBLE_TASKS in self.reasons:
            if (self.target_kind != "writer" or self.eligible_task_count is None
                    or self.minimum_eligible_tasks is None
                    or self.eligible_task_count >= self.minimum_eligible_tasks):
                raise ValueError("Task exclusion needs writer counts below the recorded minimum")
        if self.context == QCContext.PRIMARY_80 and self.target_kind == "writer":
            if self.minimum_eligible_tasks != 4:
                raise ValueError("Primary writer minimum is four eligible tasks")
        if self.context == QCContext.BALANCED_FIVE_TASK and self.target_kind == "writer":
            if self.minimum_eligible_tasks != 5:
                raise ValueError("Balanced writer minimum is five eligible tasks")
        if self.status == QCStatus.PASS:
            if self.target_kind == "sample" and (
                self.derivation_id is None or self.word_count is None
                or self.word_threshold is None or self.word_count < self.word_threshold
            ):
                raise ValueError("Passing sample needs a versioned text and qualifying count")
            if self.target_kind == "writer" and (
                self.eligible_task_count is None or self.minimum_eligible_tasks is None
                or self.eligible_task_count < self.minimum_eligible_tasks
            ):
                raise ValueError("Passing writer needs qualifying task counts")
        return self


class SnapshotMember(Contract):
    sample_id: UUID
    derivation_id: UUID
    clean_byte_sha256: Sha256
    sample_qc_id: UUID
    writer_qc_id: UUID


class DatasetSnapshot(Contract):
    id: UUID
    corpus_id: UUID
    version: Label
    context: QCContext
    created_at: Timestamp
    reproducibility: Reproducibility
    members: tuple[SnapshotMember, ...]
    manifest_sha256: Sha256

    @model_validator(mode="after")
    def validate_manifest(self) -> Self:
        ids = [member.sample_id for member in self.members]
        if ids != sorted(set(ids), key=str):
            raise ValueError("Snapshot members must be unique and sorted by sample UUID")
        if self.context == QCContext.SOURCE_INVENTORY_100:
            raise ValueError("Inventory classification cannot define an analytical snapshot")
        if canonical_sha256(self.model_dump(mode="json", exclude={"manifest_sha256"})) != self.manifest_sha256:
            raise ValueError("Snapshot manifest hash mismatch")
        return self


class RunStatus(StrEnum):
    PLANNED = "planned"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ExperimentRun(Contract):
    id: UUID
    experiment_version: Label
    snapshot_id: UUID
    snapshot_manifest_sha256: Sha256
    stage_number: Annotated[int, Field(ge=1, le=9)]
    status: RunStatus
    reproducibility: Reproducibility
    created_at: Timestamp
    started_at: Timestamp | None = None
    finished_at: Timestamp | None = None
    output_provenance_ids: tuple[UUID, ...] = ()

    @model_validator(mode="after")
    def validate_lifecycle(self) -> Self:
        if self.started_at is not None and self.started_at < self.created_at:
            raise ValueError("Run start precedes creation")
        if self.finished_at is not None and self.finished_at < (self.started_at or self.created_at):
            raise ValueError("Run finish precedes start/creation")
        if self.status == RunStatus.PLANNED and (
            self.started_at or self.finished_at or self.output_provenance_ids
        ):
            raise ValueError("Planned run cannot imply execution")
        if self.status == RunStatus.RUNNING and (self.started_at is None or self.finished_at is not None):
            raise ValueError("Running run requires start and no finish")
        if self.status in (RunStatus.SUCCEEDED, RunStatus.FAILED) and (
            self.started_at is None or self.finished_at is None
        ):
            raise ValueError("Executed terminal run requires start and finish")
        if self.status == RunStatus.CANCELLED and self.finished_at is None:
            raise ValueError("Cancelled run requires finish timestamp")
        if self.output_provenance_ids and self.started_at is None:
            raise ValueError("Run outputs require execution to have started")
        if len(set(self.output_provenance_ids)) != len(self.output_provenance_ids):
            raise ValueError("Run output provenance references must be unique")
        return self


class ResearchBundle(Contract):
    """Closed metadata graph: validates references without reading private objects.

    Individual records validate shape; use this boundary for referential checks.
    Persisted services must also enforce the proposed schema constraints.
    """
    provenance: tuple[Provenance, ...]
    corpora: tuple[Corpus, ...]
    writers: tuple[AnonymizedWriter, ...]
    documents: tuple[SourceDocument, ...]
    samples: tuple[TextSample, ...]
    extractions: tuple[ExtractionEvent, ...]
    derivations: tuple[CleanTextDerivation, ...]
    evaluations: tuple[QCEvaluation, ...]
    snapshots: tuple[DatasetSnapshot, ...]
    runs: tuple[ExperimentRun, ...]

    @model_validator(mode="after")
    def validate_graph(self) -> Self:
        indexes = {}
        all_ids: set[UUID] = set()
        for name in type(self).model_fields:
            records = getattr(self, name)
            ids = {record.id for record in records}
            if len(ids) != len(records) or ids & all_ids:
                raise ValueError("Metadata record UUIDs must be globally unique")
            all_ids.update(ids)
            indexes[name] = {record.id: record for record in records}

        def require(table: str, key: UUID):
            if key not in indexes[table]:
                raise ValueError(f"Unresolved {table} reference")
            return indexes[table][key]

        for name in ("corpora", "documents", "samples", "extractions", "derivations", "evaluations"):
            for record in getattr(self, name):
                require("provenance", record.provenance_id)
        for writer in self.writers:
            require("corpora", writer.corpus_id)
        for document in self.documents:
            require("corpora", document.corpus_id)
        slots = set()
        for sample in self.samples:
            writer = require("writers", sample.writer_id)
            if writer.corpus_id != sample.corpus_id:
                raise ValueError("Sample and writer must share corpus")
            slot = (sample.corpus_id, sample.writer_id, sample.task)
            if slot in slots:
                raise ValueError("One logical sample per corpus/writer/task slot")
            slots.add(slot)
        for event in self.extractions:
            sample = require("samples", event.sample_id)
            document = require("documents", event.source_document_id)
            if sample.corpus_id != document.corpus_id:
                raise ValueError("Extraction source and sample must share corpus")
            if event.started_at < document.acquired_at:
                raise ValueError("Extraction precedes source acquisition")
        versions = set()
        for derivation in self.derivations:
            event = require("extractions", derivation.extraction_event_id)
            if event.sample_id != derivation.sample_id or event.status != ExtractionStatus.SUCCEEDED:
                raise ValueError("Derivation requires successful extraction of the same sample")
            if derivation.created_at < event.finished_at:
                raise ValueError("Derivation precedes extraction")
            version_key = (derivation.sample_id, derivation.extraction_event_id, derivation.version)
            if version_key in versions:
                raise ValueError("Derivation version must be unique within extraction/sample")
            versions.add(version_key)
            if derivation.parent_derivation_id is not None:
                parent = require("derivations", derivation.parent_derivation_id)
                if (parent.sample_id != derivation.sample_id
                        or parent.extraction_event_id != derivation.extraction_event_id
                        or parent.version + 1 != derivation.version
                        or parent.created_at > derivation.created_at):
                    raise ValueError("Derivation parent must be the previous version of the same extraction/sample")
                # Strictly increasing positive versions also prevent ancestry cycles.
        for qc in self.evaluations:
            target = require("samples" if qc.target_kind == "sample" else "writers", qc.target_id)
            if qc.derivation_id is not None:
                derivation = require("derivations", qc.derivation_id)
                if derivation.sample_id != target.id or qc.evaluated_at < derivation.created_at:
                    raise ValueError("QC must reference an existing version of its sample")
            for other_id in qc.related_sample_ids:
                other = require("samples", other_id)
                if other.corpus_id != target.corpus_id:
                    raise ValueError("Duplicate evidence samples must share corpus")
        for snapshot in self.snapshots:
            require("corpora", snapshot.corpus_id)
            writer_tasks: dict[UUID, set[TaskCode]] = {}
            writer_decisions: dict[UUID, QCEvaluation] = {}
            for member in snapshot.members:
                sample = require("samples", member.sample_id)
                derivation = require("derivations", member.derivation_id)
                if (sample.corpus_id != snapshot.corpus_id or derivation.sample_id != sample.id
                        or derivation.byte_sha256 != member.clean_byte_sha256):
                    raise ValueError("Snapshot membership must pin matching corpus/text/hash")
                for qc_id, kind, target_id in (
                    (member.sample_qc_id, "sample", sample.id),
                    (member.writer_qc_id, "writer", sample.writer_id),
                ):
                    qc = require("evaluations", qc_id)
                    if (qc.target_kind != kind or qc.target_id != target_id
                            or qc.status != QCStatus.PASS or qc.context != snapshot.context
                            or qc.reproducibility.configuration_sha256 != snapshot.reproducibility.configuration_sha256
                            or qc.reproducibility.configuration_version != snapshot.reproducibility.configuration_version
                            or qc.evaluated_at > snapshot.created_at):
                        raise ValueError("Snapshot requires matching analytical PASS receipts")
                    if kind == "sample" and qc.derivation_id != derivation.id:
                        raise ValueError("Sample QC must assess the pinned derivation")
                    if kind == "writer":
                        if sample.writer_id in writer_decisions and writer_decisions[sample.writer_id].id != qc.id:
                            raise ValueError("One writer decision per snapshot writer")
                        writer_decisions[sample.writer_id] = qc
                writer_tasks.setdefault(sample.writer_id, set()).add(sample.task)
            for writer_id, tasks in writer_tasks.items():
                if len(tasks) < writer_decisions[writer_id].minimum_eligible_tasks:
                    raise ValueError("Snapshot writer lacks the recorded minimum task membership")
                if len(tasks) != writer_decisions[writer_id].eligible_task_count:
                    raise ValueError("Snapshot membership differs from the writer eligibility receipt")
        for run in self.runs:
            snapshot = require("snapshots", run.snapshot_id)
            if (run.snapshot_manifest_sha256 != snapshot.manifest_sha256
                    or run.created_at < snapshot.created_at):
                raise ValueError("Run must pin an existing snapshot hash")
            for provenance_id in run.output_provenance_ids:
                require("provenance", provenance_id)
        return self
