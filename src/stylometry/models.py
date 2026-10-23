"""S2A relational metadata mappings. Importing this module performs no I/O.

No writing content is modeled. Cross-row enforcement limits are documented in
docs/s2b01-implementation.md; direct SQL is not a validated ingestion boundary.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean, CHAR, CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint,
    Integer, MetaData, String, UniqueConstraint, Uuid,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention={
        "pk": "pk_%(table_name)s", "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s", "ck": "ck_%(table_name)s_%(constraint_name)s",
    })
    type_annotation_map = {UUID: Uuid, datetime: DateTime(timezone=True)}


def fk(target: str, *, nullable: bool = False, primary_key: bool = False):
    return mapped_column(Uuid, ForeignKey(target, ondelete="RESTRICT"),
                         nullable=nullable, primary_key=primary_key)


def check(expression: str, name: str):
    return CheckConstraint(expression, name=name)


def choices(column: str, values: tuple[str, ...]):
    return check(f"{column} IN ({', '.join(repr(v) for v in values)})", column)


CONTEXTS = ("source_inventory_100", "primary_80", "sensitivity_100", "balanced_five_task")
STATUSES = ("not_evaluated", "pass", "excluded", "review_required")
REASONS = ("missing_text", "below_word_threshold", "duplicate_text",
           "insufficient_eligible_tasks", "extraction_failed", "unresolved_method")


class Identified:
    id: Mapped[UUID] = mapped_column(primary_key=True)


class Reproducible:
    contract_version: Mapped[str] = mapped_column(String(16))
    configuration_version: Mapped[str] = mapped_column(String(120))
    configuration_ref: Mapped[UUID]
    configuration_sha256: Mapped[str] = mapped_column(String(64))
    code_commit: Mapped[str] = mapped_column(String(64))
    working_tree_dirty: Mapped[bool] = mapped_column(Boolean)
    environment_lock_sha256: Mapped[str] = mapped_column(String(64))


class Provenance(Identified, Base):
    __tablename__ = "provenance"
    recorded_at: Mapped[datetime]
    evidence_ref: Mapped[UUID]
    evidence_sha256: Mapped[str] = mapped_column(String(64))


class Corpus(Identified, Base):
    __tablename__ = "corpus"
    version: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime]
    provenance_id: Mapped[UUID] = fk("provenance.id")
    provenance: Mapped[Provenance] = relationship()


class Writer(Identified, Base):
    __tablename__ = "writer"
    __table_args__ = (UniqueConstraint("id", "corpus_id"),)
    corpus_id: Mapped[UUID] = fk("corpus.id")
    corpus: Mapped[Corpus] = relationship()


class Task(Base):
    __tablename__ = "task"
    __table_args__ = (check(
        "(code = 'T01' AND genre = 'narrative' AND form = 'paragraph') OR "
        "(code = 'T02' AND genre = 'descriptive' AND form = 'paragraph') OR "
        "(code = 'T03' AND genre = 'expository' AND form = 'paragraph') OR "
        "(code = 'T04' AND genre = 'persuasive' AND form = 'paragraph') OR "
        "(code = 'T05' AND genre = 'persuasive' AND form = 'essay')", "definition"),)
    code: Mapped[str] = mapped_column(String(3), primary_key=True)
    genre: Mapped[str] = mapped_column(String(32))
    form: Mapped[str] = mapped_column(String(16))


class SourceDocument(Identified, Base):
    __tablename__ = "source_document"
    __table_args__ = (
        UniqueConstraint("id", "corpus_id"),
        choices("media_type", ("application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                               "text/plain", "application/octet-stream")),
    )
    corpus_id: Mapped[UUID] = fk("corpus.id")
    private_object_ref: Mapped[UUID]
    byte_sha256: Mapped[str] = mapped_column(String(64))
    media_type: Mapped[str] = mapped_column(String(100))
    provenance_id: Mapped[UUID] = fk("provenance.id")
    acquired_at: Mapped[datetime]
    corpus: Mapped[Corpus] = relationship()
    provenance: Mapped[Provenance] = relationship()


class TextSample(Identified, Base):
    __tablename__ = "text_sample"
    __table_args__ = (
        ForeignKeyConstraint(["writer_id", "corpus_id"], ["writer.id", "writer.corpus_id"], ondelete="RESTRICT"),
        UniqueConstraint("corpus_id", "writer_id", "task_code"),
    )
    corpus_id: Mapped[UUID] = fk("corpus.id")
    writer_id: Mapped[UUID]
    task_code: Mapped[str] = mapped_column(ForeignKey("task.code", ondelete="RESTRICT"))
    provenance_id: Mapped[UUID] = fk("provenance.id")
    writer: Mapped[Writer] = relationship()
    corpus: Mapped[Corpus] = relationship(viewonly=True)
    task: Mapped[Task] = relationship()
    provenance: Mapped[Provenance] = relationship()


class ExtractionEvent(Identified, Reproducible, Base):
    __tablename__ = "extraction_event"
    __table_args__ = (
        choices("status", ("succeeded", "failed")),
        check("finished_at >= started_at", "times"),
        check("(status = 'succeeded' AND extracted_object_ref IS NOT NULL AND extracted_byte_sha256 IS NOT NULL) OR "
              "(status = 'failed' AND extracted_object_ref IS NULL AND extracted_byte_sha256 IS NULL)", "output_status"),
    )
    sample_id: Mapped[UUID] = fk("text_sample.id")
    source_document_id: Mapped[UUID] = fk("source_document.id")
    source_span_ref: Mapped[UUID]
    method_ref: Mapped[UUID]
    provenance_id: Mapped[UUID] = fk("provenance.id")
    started_at: Mapped[datetime]
    finished_at: Mapped[datetime]
    status: Mapped[str] = mapped_column(String(16))
    extracted_object_ref: Mapped[UUID | None]
    extracted_byte_sha256: Mapped[str | None] = mapped_column(String(64))
    sample: Mapped[TextSample] = relationship()
    source_document: Mapped[SourceDocument] = relationship()
    provenance: Mapped[Provenance] = relationship()


class CleanTextDerivation(Identified, Reproducible, Base):
    __tablename__ = "clean_text_derivation"
    __table_args__ = (
        UniqueConstraint("sample_id", "extraction_event_id", "version"),
        check("version > 0", "version_positive"),
        check("parent_derivation_id IS NULL OR parent_derivation_id <> id", "not_self_parent"),
        check("(version = 1 AND parent_derivation_id IS NULL) OR (version > 1 AND parent_derivation_id IS NOT NULL)", "parent_version"),
    )
    sample_id: Mapped[UUID] = fk("text_sample.id")
    extraction_event_id: Mapped[UUID] = fk("extraction_event.id")
    parent_derivation_id: Mapped[UUID | None] = fk("clean_text_derivation.id", nullable=True)
    version: Mapped[int]
    private_object_ref: Mapped[UUID]
    byte_sha256: Mapped[str] = mapped_column(String(64))
    method_ref: Mapped[UUID]
    provenance_id: Mapped[UUID] = fk("provenance.id")
    created_at: Mapped[datetime]
    sample: Mapped[TextSample] = relationship()
    extraction_event: Mapped[ExtractionEvent] = relationship()
    parent: Mapped["CleanTextDerivation | None"] = relationship(remote_side="CleanTextDerivation.id")
    provenance: Mapped[Provenance] = relationship()


class QCEvaluation(Identified, Reproducible, Base):
    __tablename__ = "qc_evaluation"
    __table_args__ = (
        choices("context", CONTEXTS), choices("status", STATUSES),
        check("(sample_id IS NOT NULL AND writer_id IS NULL) OR (sample_id IS NULL AND writer_id IS NOT NULL)", "target_xor"),
        check("word_count IS NULL OR word_count >= 0", "word_count"),
        check("word_threshold IS NULL OR word_threshold > 0", "word_threshold"),
        check("eligible_task_count IS NULL OR eligible_task_count BETWEEN 0 AND 5", "eligible_tasks"),
        check("minimum_eligible_tasks IS NULL OR minimum_eligible_tasks BETWEEN 1 AND 5", "minimum_tasks"),
        check("(word_count IS NULL) = (tokenizer_method_ref IS NULL)", "tokenizer_pair"),
        check("word_count IS NULL OR derivation_id IS NOT NULL", "count_derivation"),
        check("writer_id IS NULL OR (derivation_id IS NULL AND word_count IS NULL)", "writer_measurements"),
        check("sample_id IS NULL OR (eligible_task_count IS NULL AND minimum_eligible_tasks IS NULL)", "sample_measurements"),
        check("context NOT IN ('source_inventory_100', 'primary_80', 'sensitivity_100') OR "
              "(word_threshold IS NOT NULL AND word_threshold = CASE WHEN context = 'primary_80' THEN 80 ELSE 100 END)", "context_threshold"),
        check("writer_id IS NULL OR context <> 'primary_80' OR (minimum_eligible_tasks IS NOT NULL AND minimum_eligible_tasks = 4)", "primary_minimum"),
        check("writer_id IS NULL OR context <> 'balanced_five_task' OR (minimum_eligible_tasks IS NOT NULL AND minimum_eligible_tasks = 5)", "balanced_minimum"),
        check("status <> 'pass' OR (sample_id IS NOT NULL AND derivation_id IS NOT NULL AND word_count IS NOT NULL "
              "AND word_threshold IS NOT NULL AND word_count >= word_threshold) OR "
              "(writer_id IS NOT NULL AND eligible_task_count IS NOT NULL AND minimum_eligible_tasks IS NOT NULL "
              "AND eligible_task_count >= minimum_eligible_tasks)", "passing_measurements"),
    )
    sample_id: Mapped[UUID | None] = fk("text_sample.id", nullable=True)
    writer_id: Mapped[UUID | None] = fk("writer.id", nullable=True)
    context: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(24))
    derivation_id: Mapped[UUID | None] = fk("clean_text_derivation.id", nullable=True)
    word_count: Mapped[int | None]
    word_threshold: Mapped[int | None]
    tokenizer_method_ref: Mapped[UUID | None]
    eligible_task_count: Mapped[int | None]
    minimum_eligible_tasks: Mapped[int | None]
    evidence_ref: Mapped[UUID | None]
    provenance_id: Mapped[UUID] = fk("provenance.id")
    evaluated_at: Mapped[datetime]
    sample: Mapped[TextSample | None] = relationship()
    writer: Mapped[Writer | None] = relationship()
    derivation: Mapped[CleanTextDerivation | None] = relationship()
    provenance: Mapped[Provenance] = relationship()
    reasons: Mapped[list["QCReason"]] = relationship(back_populates="evaluation")
    related_samples: Mapped[list["QCRelatedSample"]] = relationship(back_populates="evaluation")


class QCReason(Base):
    __tablename__ = "qc_reason"
    __table_args__ = (choices("reason_code", REASONS),)
    qc_id: Mapped[UUID] = fk("qc_evaluation.id", primary_key=True)
    reason_code: Mapped[str] = mapped_column(String(40), primary_key=True)
    evaluation: Mapped[QCEvaluation] = relationship(back_populates="reasons")


class QCRelatedSample(Base):
    __tablename__ = "qc_related_sample"
    qc_id: Mapped[UUID] = fk("qc_evaluation.id", primary_key=True)
    related_sample_id: Mapped[UUID] = fk("text_sample.id", primary_key=True)
    evaluation: Mapped[QCEvaluation] = relationship(back_populates="related_samples")
    sample: Mapped[TextSample] = relationship()


class DatasetSnapshot(Identified, Reproducible, Base):
    __tablename__ = "dataset_snapshot"
    __table_args__ = (choices("context", CONTEXTS[1:]),)
    corpus_id: Mapped[UUID] = fk("corpus.id")
    version: Mapped[str] = mapped_column(String(120))
    context: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime]
    manifest_sha256: Mapped[str] = mapped_column(String(64))
    corpus: Mapped[Corpus] = relationship()
    members: Mapped[list["SnapshotMember"]] = relationship(back_populates="snapshot")


class SnapshotMember(Base):
    __tablename__ = "snapshot_member"
    snapshot_id: Mapped[UUID] = fk("dataset_snapshot.id", primary_key=True)
    sample_id: Mapped[UUID] = fk("text_sample.id", primary_key=True)
    derivation_id: Mapped[UUID] = fk("clean_text_derivation.id")
    clean_byte_sha256: Mapped[str] = mapped_column(String(64))
    sample_qc_id: Mapped[UUID] = fk("qc_evaluation.id")
    writer_qc_id: Mapped[UUID] = fk("qc_evaluation.id")
    snapshot: Mapped[DatasetSnapshot] = relationship(back_populates="members")
    sample: Mapped[TextSample] = relationship()
    derivation: Mapped[CleanTextDerivation] = relationship()
    sample_qc: Mapped[QCEvaluation] = relationship(foreign_keys=[sample_qc_id])
    writer_qc: Mapped[QCEvaluation] = relationship(foreign_keys=[writer_qc_id])


class ExperimentRun(Identified, Reproducible, Base):
    __tablename__ = "experiment_run"
    __table_args__ = (
        choices("status", ("planned", "running", "succeeded", "failed", "cancelled")),
        check("stage_number BETWEEN 1 AND 9", "stage_number"),
        check("started_at IS NULL OR started_at >= created_at", "start_time"),
        check("finished_at IS NULL OR finished_at >= COALESCE(started_at, created_at)", "finish_time"),
        check("(status = 'planned' AND started_at IS NULL AND finished_at IS NULL) OR "
              "(status = 'running' AND started_at IS NOT NULL AND finished_at IS NULL) OR "
              "(status IN ('succeeded', 'failed') AND started_at IS NOT NULL AND finished_at IS NOT NULL) OR "
              "(status = 'cancelled' AND finished_at IS NOT NULL)", "lifecycle"),
    )
    experiment_version: Mapped[str] = mapped_column(String(120))
    snapshot_id: Mapped[UUID] = fk("dataset_snapshot.id")
    snapshot_manifest_sha256: Mapped[str] = mapped_column(String(64))
    stage_number: Mapped[int]
    status: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime]
    started_at: Mapped[datetime | None]
    finished_at: Mapped[datetime | None]
    snapshot: Mapped[DatasetSnapshot] = relationship()
    outputs: Mapped[list["RunOutput"]] = relationship(back_populates="run")


class RunOutput(Base):
    __tablename__ = "run_output"
    run_id: Mapped[UUID] = fk("experiment_run.id", primary_key=True)
    provenance_id: Mapped[UUID] = fk("provenance.id", primary_key=True)
    run: Mapped[ExperimentRun] = relationship(back_populates="outputs")
    provenance: Mapped[Provenance] = relationship()


# Apply the same lexical checks to every approved hash/version column. These
# become ordinary named PostgreSQL CHECKs in the frozen initial migration.
for table in Base.metadata.tables.values():
    for column in table.columns:
        if column.name.endswith("sha256"):
            column.type = CHAR(64)
            table.append_constraint(check(f"{column.name} ~ '^[0-9a-f]{{64}}$'", column.name + "_format"))
        elif column.name == "code_commit":
            table.append_constraint(check("code_commit ~ '^([0-9a-f]{40}|[0-9a-f]{64})$'", "commit_format"))
        elif column.name in ("version", "configuration_version", "experiment_version") and not isinstance(column.type, Integer):
            table.append_constraint(check(f"{column.name} ~ '^[A-Za-z0-9_.-]{{1,120}}$'", column.name + "_format"))
        elif column.name == "contract_version":
            table.append_constraint(check("contract_version = 's2a.v1'", "contract_version"))
