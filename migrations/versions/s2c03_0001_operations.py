"""Additive synthetic pre-snapshot journal. No existing research DDL or rows changed."""
from alembic import op
import sqlalchemy as sa

revision = "s2c03_0001"
down_revision = "s2b01_0001"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('operation_study',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('code', sa.String(length=2), nullable=False),
    sa.Column('version', sa.String(length=120), nullable=False),
    sa.Column('provenance_id', sa.Uuid(), nullable=False),
    sa.CheckConstraint("code IN ('P1','P2','D1')", name=op.f('ck_operation_study_code')),
    sa.CheckConstraint("version ~ '^[A-Za-z0-9_.-]{1,120}$'", name=op.f('ck_operation_study_version')),
    sa.ForeignKeyConstraint(['provenance_id'], ['provenance.id'], name=op.f('fk_operation_study_provenance_id_provenance'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_operation_study'))
    )
    op.create_table('operation_corpus',
    sa.Column('corpus_id', sa.Uuid(), nullable=False),
    sa.Column('study_id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['corpus_id'], ['corpus.id'], name=op.f('fk_operation_corpus_corpus_id_corpus'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['study_id'], ['operation_study.id'], name=op.f('fk_operation_corpus_study_id_operation_study'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('corpus_id', name=op.f('pk_operation_corpus')),
    sa.UniqueConstraint('corpus_id', 'study_id', name=op.f('uq_operation_corpus_corpus_id'))
    )
    op.create_table('research_operation',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('study_id', sa.Uuid(), nullable=False),
    sa.Column('corpus_id', sa.Uuid(), nullable=True),
    sa.Column('idempotency_id', sa.Uuid(), nullable=False),
    sa.Column('synthetic_only', sa.Boolean(), nullable=False),
    sa.Column('kind', sa.String(length=32), nullable=False),
    sa.Column('version', sa.String(length=120), nullable=False),
    sa.Column('manifest_sha256', sa.String(length=64), nullable=False),
    sa.Column('contract_version', sa.String(length=16), nullable=False),
    sa.Column('configuration_ref', sa.Uuid(), nullable=False),
    sa.Column('configuration_version', sa.String(length=120), nullable=False),
    sa.Column('configuration_sha256', sa.String(length=64), nullable=False),
    sa.Column('method_ref', sa.Uuid(), nullable=False),
    sa.Column('parameters_ref', sa.Uuid(), nullable=False),
    sa.Column('provenance_id', sa.Uuid(), nullable=False),
    sa.Column('code_commit', sa.String(length=64), nullable=False),
    sa.Column('working_tree_dirty', sa.Boolean(), nullable=False),
    sa.Column('environment_lock_sha256', sa.String(length=64), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("code_commit ~ '^([0-9a-f]{40}|[0-9a-f]{64})$'", name=op.f('ck_research_operation_commit')),
    sa.CheckConstraint("configuration_sha256 ~ '^[0-9a-f]{64}$'", name=op.f('ck_research_operation_configuration_sha256_digest')),
    sa.CheckConstraint("configuration_version ~ '^[A-Za-z0-9_.-]{1,120}$'", name=op.f('ck_research_operation_configuration_version')),
    sa.CheckConstraint("contract_version = 's2a.v1'", name=op.f('ck_research_operation_contract')),
    sa.CheckConstraint("environment_lock_sha256 ~ '^[0-9a-f]{64}$'", name=op.f('ck_research_operation_environment_lock_sha256_digest')),
    sa.CheckConstraint("kind IN ('synthetic_inventory','scientific_stage')", name=op.f('ck_research_operation_kind')),
    sa.CheckConstraint("manifest_sha256 ~ '^[0-9a-f]{64}$'", name=op.f('ck_research_operation_manifest_sha256_digest')),
    sa.CheckConstraint("version ~ '^[A-Za-z0-9_.-]{1,120}$'", name=op.f('ck_research_operation_version')),
    sa.CheckConstraint('synthetic_only = true', name=op.f('ck_research_operation_synthetic')),
    sa.ForeignKeyConstraint(['corpus_id', 'study_id'], ['operation_corpus.corpus_id', 'operation_corpus.study_id'], name=op.f('fk_research_operation_corpus_id_operation_corpus'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['corpus_id'], ['corpus.id'], name=op.f('fk_research_operation_corpus_id_corpus'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['provenance_id'], ['provenance.id'], name=op.f('fk_research_operation_provenance_id_provenance'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['study_id'], ['operation_study.id'], name=op.f('fk_research_operation_study_id_operation_study'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_research_operation')),
    sa.UniqueConstraint('id', 'study_id', name=op.f('uq_research_operation_id')),
    sa.UniqueConstraint('study_id', 'idempotency_id', name=op.f('uq_research_operation_study_id'))
    )
    op.create_table('operation_dependency',
    sa.Column('operation_id', sa.Uuid(), nullable=False),
    sa.Column('dependency_id', sa.Uuid(), nullable=False),
    sa.Column('study_id', sa.Uuid(), nullable=False),
    sa.CheckConstraint('operation_id <> dependency_id', name=op.f('ck_operation_dependency_not_self')),
    sa.ForeignKeyConstraint(['dependency_id', 'study_id'], ['research_operation.id', 'research_operation.study_id'], name=op.f('fk_operation_dependency_dependency_id_research_operation'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['operation_id', 'study_id'], ['research_operation.id', 'research_operation.study_id'], name=op.f('fk_operation_dependency_operation_id_research_operation'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('operation_id', 'dependency_id', name=op.f('pk_operation_dependency'))
    )
    op.create_table('operation_event',
    sa.Column('operation_id', sa.Uuid(), nullable=False),
    sa.Column('sequence', sa.Integer(), nullable=False),
    sa.Column('previous_sequence', sa.Integer(), nullable=True),
    sa.Column('previous_state', sa.String(length=24), nullable=True),
    sa.Column('state', sa.String(length=24), nullable=False),
    sa.Column('recorded_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('failure_code', sa.String(length=32), nullable=True),
    sa.CheckConstraint("(sequence = 0 AND previous_sequence IS NULL AND previous_state IS NULL AND state = 'planned') OR (sequence > 0 AND previous_sequence IS NOT NULL AND previous_state IS NOT NULL AND previous_sequence = sequence - 1 AND ((previous_state = 'planned' AND state IN ('publishing','failed','reconcile')) OR (previous_state = 'publishing' AND state IN ('files_ready','reconcile','failed')) OR (previous_state = 'files_ready' AND state IN ('registering','publishing','reconcile')) OR (previous_state = 'registering' AND state IN ('staged','reconcile')) OR (previous_state = 'staged' AND state IN ('committed_verified','publishing','reconcile')) OR (previous_state = 'committed_verified' AND state IN ('reconcile')) OR (previous_state = 'reconcile' AND state IN ('publishing','failed')) OR (previous_state = 'failed' AND state IN ('reconcile'))))", name=op.f('ck_operation_event_transition')),
    sa.CheckConstraint("failure_code IS NULL OR failure_code IN ('interrupted','verification_failed','unavailable')", name=op.f('ck_operation_event_failure')),
    sa.CheckConstraint("state IN ('planned','publishing','files_ready','registering','staged','committed_verified','failed','reconcile')", name=op.f('ck_operation_event_state')),
    sa.ForeignKeyConstraint(['operation_id', 'previous_sequence', 'previous_state'], ['operation_event.operation_id', 'operation_event.sequence', 'operation_event.state'], name=op.f('fk_operation_event_operation_id_operation_event'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['operation_id'], ['research_operation.id'], name=op.f('fk_operation_event_operation_id_research_operation'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('operation_id', 'sequence', name=op.f('pk_operation_event')),
    sa.UniqueConstraint('operation_id', 'sequence', 'state', name=op.f('uq_operation_event_operation_id'))
    )
    op.create_table('operation_experiment_link',
    sa.Column('operation_id', sa.Uuid(), nullable=False),
    sa.Column('experiment_id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['experiment_id'], ['experiment_run.id'], name=op.f('fk_operation_experiment_link_experiment_id_experiment_run'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['operation_id'], ['research_operation.id'], name=op.f('fk_operation_experiment_link_operation_id_research_operation'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('operation_id', 'experiment_id', name=op.f('pk_operation_experiment_link'))
    )
    op.create_table('operation_object',
    sa.Column('operation_id', sa.Uuid(), nullable=False),
    sa.Column('direction', sa.String(length=6), nullable=False),
    sa.Column('object_ref', sa.Uuid(), nullable=False),
    sa.Column('byte_sha256', sa.String(length=64), nullable=False),
    sa.Column('version', sa.String(length=120), nullable=False),
    sa.Column('provenance_id', sa.Uuid(), nullable=False),
    sa.CheckConstraint("byte_sha256 ~ '^[0-9a-f]{64}$'", name=op.f('ck_operation_object_byte_sha256_digest')),
    sa.CheckConstraint("direction IN ('input','output')", name=op.f('ck_operation_object_direction')),
    sa.CheckConstraint("version ~ '^[A-Za-z0-9_.-]{1,120}$'", name=op.f('ck_operation_object_version')),
    sa.ForeignKeyConstraint(['operation_id'], ['research_operation.id'], name=op.f('fk_operation_object_operation_id_research_operation'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['provenance_id'], ['provenance.id'], name=op.f('fk_operation_object_provenance_id_provenance'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('operation_id', 'direction', 'object_ref', name=op.f('pk_operation_object'))
    )

def downgrade():
    raise RuntimeError("Destructive journal downgrade is not supported; restore an approved backup privately.")
