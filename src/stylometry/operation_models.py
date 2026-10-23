"""Additive pre-snapshot journal. No I/O, payloads or changes to S2A mappings."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Integer, MetaData, String, UniqueConstraint, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from stylometry.models import Base as ResearchBase


# Copy reference definitions, never mutate the approved 15-table metadata.
metadata = MetaData(naming_convention=ResearchBase.metadata.naming_convention)
for table in ResearchBase.metadata.sorted_tables:
    table.to_metadata(metadata)


class JournalBase(DeclarativeBase):
    metadata = metadata
    type_annotation_map = {UUID: Uuid, datetime: DateTime(timezone=True)}


STATES = ('planned', 'publishing', 'files_ready', 'registering', 'staged', 'committed_verified', 'failed', 'reconcile')
TRANSITIONS = {
    'planned': ('publishing', 'failed', 'reconcile'),
    'publishing': ('files_ready', 'reconcile', 'failed'),
    'files_ready': ('registering', 'publishing', 'reconcile'),
    'registering': ('staged', 'reconcile'),
    'staged': ('committed_verified', 'publishing', 'reconcile'),
    'committed_verified': ('reconcile',),
    'reconcile': ('publishing', 'failed'),
    'failed': ('reconcile',),
}


def digest(column):
    return CheckConstraint(f"{column} ~ '^[0-9a-f]{{64}}$'", name=column + '_digest')


class StudyReference(JournalBase):
    __tablename__ = 'operation_study'
    __table_args__ = (CheckConstraint("code IN ('P1','P2','D1')", name='code'),
                      CheckConstraint("version ~ '^[A-Za-z0-9_.-]{1,120}$'", name='version'))
    id: Mapped[UUID] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(2))
    version: Mapped[str] = mapped_column(String(120))
    provenance_id: Mapped[UUID] = mapped_column(ForeignKey('provenance.id', ondelete='RESTRICT'))


class Operation(JournalBase):
    __tablename__ = 'research_operation'
    __table_args__ = (
        UniqueConstraint('study_id', 'idempotency_id'),
        UniqueConstraint('id', 'study_id'),
        ForeignKeyConstraint(['corpus_id', 'study_id'], ['operation_corpus.corpus_id', 'operation_corpus.study_id'], ondelete='RESTRICT'),
        digest('manifest_sha256'), digest('configuration_sha256'), digest('environment_lock_sha256'),
        CheckConstraint("kind IN ('synthetic_inventory','scientific_stage')", name='kind'),
        CheckConstraint('synthetic_only = true', name='synthetic'),
        CheckConstraint("contract_version = 's2a.v1'", name='contract'),
        CheckConstraint("version ~ '^[A-Za-z0-9_.-]{1,120}$'", name='version'),
        CheckConstraint("configuration_version ~ '^[A-Za-z0-9_.-]{1,120}$'", name='configuration_version'),
        CheckConstraint("code_commit ~ '^([0-9a-f]{40}|[0-9a-f]{64})$'", name='commit'),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True)
    study_id: Mapped[UUID] = mapped_column(ForeignKey('operation_study.id', ondelete='RESTRICT'))
    corpus_id: Mapped[UUID | None] = mapped_column(ForeignKey('corpus.id', ondelete='RESTRICT'))
    idempotency_id: Mapped[UUID]
    synthetic_only: Mapped[bool] = mapped_column(Boolean)
    kind: Mapped[str] = mapped_column(String(32))
    version: Mapped[str] = mapped_column(String(120))
    manifest_sha256: Mapped[str] = mapped_column(String(64))
    contract_version: Mapped[str] = mapped_column(String(16))
    configuration_ref: Mapped[UUID]
    configuration_version: Mapped[str] = mapped_column(String(120))
    configuration_sha256: Mapped[str] = mapped_column(String(64))
    method_ref: Mapped[UUID]
    parameters_ref: Mapped[UUID]
    provenance_id: Mapped[UUID] = mapped_column(ForeignKey('provenance.id', ondelete='RESTRICT'))
    code_commit: Mapped[str] = mapped_column(String(64))
    working_tree_dirty: Mapped[bool] = mapped_column(Boolean)
    environment_lock_sha256: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime]


class OperationCorpus(JournalBase):
    __tablename__ = 'operation_corpus'
    __table_args__ = (UniqueConstraint('corpus_id', 'study_id'),)
    corpus_id: Mapped[UUID] = mapped_column(ForeignKey('corpus.id', ondelete='RESTRICT'), primary_key=True)
    study_id: Mapped[UUID] = mapped_column(ForeignKey('operation_study.id', ondelete='RESTRICT'))


class OperationObject(JournalBase):
    __tablename__ = 'operation_object'
    __table_args__ = (
        digest('byte_sha256'),
        CheckConstraint("direction IN ('input','output')", name='direction'),
        CheckConstraint("version ~ '^[A-Za-z0-9_.-]{1,120}$'", name='version'),
    )
    operation_id: Mapped[UUID] = mapped_column(ForeignKey('research_operation.id', ondelete='RESTRICT'), primary_key=True)
    direction: Mapped[str] = mapped_column(String(6), primary_key=True)
    object_ref: Mapped[UUID] = mapped_column(primary_key=True)
    byte_sha256: Mapped[str] = mapped_column(String(64))
    version: Mapped[str] = mapped_column(String(120))
    provenance_id: Mapped[UUID] = mapped_column(ForeignKey('provenance.id', ondelete='RESTRICT'))


transition_sql = ' OR '.join(f"(previous_state = '{a}' AND state IN ({','.join(repr(b) for b in bs)}))" for a, bs in TRANSITIONS.items())


class OperationEvent(JournalBase):
    __tablename__ = 'operation_event'
    __table_args__ = (
        UniqueConstraint('operation_id', 'sequence', 'state'),
        ForeignKeyConstraint(['operation_id', 'previous_sequence', 'previous_state'],
                             ['operation_event.operation_id', 'operation_event.sequence', 'operation_event.state'], ondelete='RESTRICT'),
        CheckConstraint("state IN (" + ','.join(repr(s) for s in STATES) + ")", name='state'),
        CheckConstraint("(sequence = 0 AND previous_sequence IS NULL AND previous_state IS NULL AND state = 'planned') OR "
                        "(sequence > 0 AND previous_sequence IS NOT NULL AND previous_state IS NOT NULL AND previous_sequence = sequence - 1 AND (" + transition_sql + '))', name='transition'),
        CheckConstraint("failure_code IS NULL OR failure_code IN ('interrupted','verification_failed','unavailable')", name='failure'),
    )
    operation_id: Mapped[UUID] = mapped_column(ForeignKey('research_operation.id', ondelete='RESTRICT'), primary_key=True)
    sequence: Mapped[int] = mapped_column(Integer, primary_key=True)
    previous_sequence: Mapped[int | None] = mapped_column(Integer)
    previous_state: Mapped[str | None] = mapped_column(String(24))
    state: Mapped[str] = mapped_column(String(24))
    recorded_at: Mapped[datetime]
    failure_code: Mapped[str | None] = mapped_column(String(32))


class OperationDependency(JournalBase):
    __tablename__ = 'operation_dependency'
    __table_args__ = (
        ForeignKeyConstraint(['operation_id', 'study_id'], ['research_operation.id', 'research_operation.study_id'], ondelete='RESTRICT'),
        ForeignKeyConstraint(['dependency_id', 'study_id'], ['research_operation.id', 'research_operation.study_id'], ondelete='RESTRICT'),
        CheckConstraint('operation_id <> dependency_id', name='not_self'),
    )
    operation_id: Mapped[UUID] = mapped_column(primary_key=True)
    dependency_id: Mapped[UUID] = mapped_column(primary_key=True)
    study_id: Mapped[UUID]


class OperationExperimentLink(JournalBase):
    __tablename__ = 'operation_experiment_link'
    operation_id: Mapped[UUID] = mapped_column(ForeignKey('research_operation.id', ondelete='RESTRICT'), primary_key=True)
    experiment_id: Mapped[UUID] = mapped_column(ForeignKey('experiment_run.id', ondelete='RESTRICT'), primary_key=True)


NEW_TABLES = tuple(t for t in metadata.sorted_tables if t.name not in ResearchBase.metadata.tables)
