"""Opt-in synthetic test coordinator, with explicit SQL commit boundaries.

Not a research ingestion service. No connections, migrations or files on import.
"""

from datetime import datetime, timezone
from uuid import UUID

from pydantic import model_validator
from sqlalchemy import insert, select, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session

from stylometry import contracts as c
from stylometry import models as research
from stylometry import operation_models as m
from stylometry.experiments.configurations import ExecutionPlan
from stylometry.experiments.runner import SyntheticRunner
from stylometry.persistence import RECORDS, load_validated_bundle, to_record
from stylometry.pipeline.registration import RegistrationRequest, _register_rows
from stylometry.recoverable_storage import RecoverableSyntheticWorkspace
from stylometry.upgrade_safety import local_identity, NEW_REVISION


class OperationError(RuntimeError):
    """Sanitized service boundary; never propagate driver/OS/request values."""


class DurableRequest(c.Contract):
    execution: ExecutionPlan
    registration: RegistrationRequest
    idempotency_id: UUID

    @model_validator(mode='after')
    def consistent(self):
        e, r = self.execution, self.registration
        inventory = r.inventory
        if (e.id != r.operation_id or e.reproducibility != r.reproducibility
                or e.created_at != r.created_at or e.inputs.study_id != inventory.study.id
                or e.inputs.corpus_id != inventory.corpus.id or e.inputs.version != inventory.inventory_version
                or e.inputs.snapshot_id is not None or e.inputs.input_objects):
            raise ValueError('Inconsistent synthetic operation request')
        return self

    @property
    def fingerprint(self):
        return c.canonical_sha256(self.model_dump(mode='json'))


def create_workspace(request: DurableRequest, **kwargs):
    request = _request(request)
    return RecoverableSyntheticWorkspace.create(operation_id=request.execution.id,
        manifest_sha256=request.fingerprint, publications=request.registration.publications, **kwargs)


def reopen_workspace(descriptor, request: DurableRequest, **kwargs):
    request = _request(request)
    return RecoverableSyntheticWorkspace.reopen(descriptor, operation_id=request.execution.id,
        manifest_sha256=request.fingerprint, publications=request.registration.publications, **kwargs)


def _request(request):
    try:
        request = DurableRequest.model_validate_json(request.model_dump_json(warnings='error'))
        if request.execution.operation != 'synthetic_inventory':
            raise ValueError
        return request
    except Exception:
        raise OperationError('Synthetic request refused; scientific methods remain unavailable.') from None


def _target(connection):
    local_identity(connection, 'stylometry_test')
    if connection.execute(text('SELECT version_num FROM public.alembic_version')).scalars().all() != [NEW_REVISION]:
        raise OperationError('Synthetic operation schema is not initialized at the reviewed revision.')
    # Global cooperative lock serializes initial identities/dependencies/metadata.
    if not connection.scalar(text('SELECT pg_try_advisory_xact_lock(21302405)')):
        raise OperationError('Synthetic journal is busy.')


def _values(request):
    e, r = request.execution, request.registration
    p = e.reproducibility
    return dict(id=e.id, study_id=e.inputs.study_id, corpus_id=e.inputs.corpus_id,
        idempotency_id=request.idempotency_id, synthetic_only=True, kind=e.operation,
        version=e.inputs.version, manifest_sha256=request.fingerprint,
        contract_version=p.contract_version,
        configuration_ref=p.configuration_ref, configuration_version=p.configuration_version,
        configuration_sha256=p.configuration_sha256, method_ref=e.inputs.approved_method_ref,
        parameters_ref=e.inputs.parameters_ref, provenance_id=r.inventory.corpus.provenance_id,
        code_commit=p.code_commit, working_tree_dirty=p.working_tree_dirty,
        environment_lock_sha256=p.environment_lock_sha256, created_at=e.created_at)


def _objects(request):
    return [dict(operation_id=request.execution.id, direction='output', object_ref=p.reference.object_ref,
        byte_sha256=p.reference.byte_sha256, version=p.reference.processing_version,
        provenance_id=p.reference.provenance_id) for p in request.registration.publications]


def _last(connection, operation_id):
    return connection.execute(select(m.OperationEvent.__table__).where(m.OperationEvent.operation_id == operation_id)
        .order_by(m.OperationEvent.sequence.desc()).limit(1)).mappings().first()


def _event(connection, operation_id, state, code=None):
    previous = _last(connection, operation_id)
    if previous and previous['state'] == state:
        return
    if previous and state not in m.TRANSITIONS[previous['state']]:
        raise OperationError('Invalid synthetic operation transition.')
    now = datetime.now(timezone.utc)
    earliest = previous['recorded_at'] if previous else connection.scalar(select(m.Operation.created_at).where(m.Operation.id==operation_id))
    if now < earliest:
        raise OperationError('Synthetic journal clock moved backwards.')
    connection.execute(insert(m.OperationEvent).values(operation_id=operation_id,
        sequence=previous['sequence']+1 if previous else 0,
        previous_sequence=previous['sequence'] if previous else None,
        previous_state=previous['state'] if previous else None, state=state,
        recorded_at=now, failure_code=code))


def _match(connection, request):
    values = _values(request)
    row = connection.execute(select(m.Operation.__table__).where(m.Operation.id == request.execution.id)).mappings().first()
    if row is None or dict(row) != values:
        raise OperationError('Synthetic journal identity conflicts or is missing.')
    study = connection.execute(select(m.StudyReference.__table__).where(m.StudyReference.id == request.execution.inputs.study_id)).mappings().first()
    expected_study = dict(id=request.execution.inputs.study_id, code=str(request.registration.inventory.study.code),
                         version='synthetic.v1', provenance_id=request.registration.inventory.corpus.provenance_id)
    if study is None or dict(study) != expected_study:
        raise OperationError('Synthetic study ownership differs.')
    objects = [dict(r) for r in connection.execute(select(m.OperationObject.__table__).where(m.OperationObject.operation_id == request.execution.id)).mappings()]
    if sorted(objects,key=lambda r:str(r['object_ref'])) != sorted(_objects(request),key=lambda r:str(r['object_ref'])):
        raise OperationError('Synthetic object manifest differs.')
    dependencies = set(connection.execute(select(m.OperationDependency.dependency_id).where(m.OperationDependency.operation_id == request.execution.id)).scalars())
    if dependencies != set(request.execution.dependency_run_ids):
        raise OperationError('Synthetic dependencies differ.')


def _plan(connection, request):
    _target(connection)
    found = connection.scalar(select(m.Operation.id).where(m.Operation.id == request.execution.id))
    if found is not None:
        _match(connection,request)
        return
    r = request.registration
    # Only provenance and corpus metadata may precede file publication.
    with Session(connection, join_transaction_mode='create_savepoint') as session, session.begin():
        for contract in (*r.inventory.provenance, r.inventory.corpus):
            record = to_record(contract)
            old = session.get(type(record),contract.id)
            if old is None:
                session.add(record)
                session.flush()
            else:
                for col in record.__table__.columns:
                    if getattr(old,col.name) != getattr(record,col.name):
                        raise OperationError('Existing synthetic ownership metadata conflicts.')
    study = dict(id=r.inventory.study.id, code=str(r.inventory.study.code),
        version='synthetic.v1', provenance_id=r.inventory.corpus.provenance_id)
    old = connection.execute(select(m.StudyReference.__table__).where(m.StudyReference.id == study['id'])).mappings().first()
    if old is None:
        connection.execute(insert(m.StudyReference).values(**study))
    elif dict(old) != study:
        raise OperationError('Synthetic study reference conflicts.')
    ownership = dict(corpus_id=r.inventory.corpus.id, study_id=study['id'])
    old_owner = connection.execute(select(m.OperationCorpus.__table__).where(m.OperationCorpus.corpus_id == ownership['corpus_id'])).mappings().first()
    if old_owner is None:
        connection.execute(insert(m.OperationCorpus).values(**ownership))
    elif dict(old_owner) != ownership:
        raise OperationError('Synthetic corpus already belongs to a different study.')
    # Dependencies must already be durably verified before planning: no cycles.
    for dependency in request.execution.dependency_run_ids:
        row = connection.execute(select(m.Operation.__table__).where(m.Operation.id == dependency)).mappings().first()
        last = _last(connection, dependency)
        if row is None or row['study_id'] != study['id'] or last is None or last['state'] != 'committed_verified':
            raise OperationError('Synthetic dependency unavailable.')
    connection.execute(insert(m.Operation).values(**_values(request)))
    for obj in _objects(request):
        known = connection.execute(select(m.OperationObject.__table__).where(m.OperationObject.object_ref==obj['object_ref'])).mappings()
        if any(any(row[key] != obj[key] for key in ('byte_sha256','version','provenance_id')) for row in known):
            raise OperationError('Existing object UUID has conflicting synthetic metadata.')
        source = next(p.reference for p in r.publications if p.reference.object_ref==obj['object_ref'])
        documents = connection.execute(select(research.SourceDocument.__table__).where(research.SourceDocument.private_object_ref==obj['object_ref'])).mappings()
        if any(row['byte_sha256'] != source.byte_sha256 or row['provenance_id'] != source.provenance_id or row['media_type'] != source.media_type for row in documents):
            raise OperationError('Existing source object metadata conflicts.')
        connection.execute(insert(m.OperationObject).values(**obj))
    for dependency in request.execution.dependency_run_ids:
        connection.execute(insert(m.OperationDependency).values(operation_id=request.execution.id,
            dependency_id=dependency,study_id=study['id']))
    _event(connection,request.execution.id,'planned')


def _files(workspace, request, plans):
    descriptor = workspace.descriptor
    if (descriptor.operation_id != request.execution.id or descriptor.manifest_sha256 != request.fingerprint
            or descriptor.publications != request.registration.publications
            or tuple(p.metadata for p in plans) != request.registration.publications):
        raise OperationError('Synthetic workspace or payload manifest differs.')
    for plan in plans:
        workspace.publish(plan,retry=True)
    for publication in request.registration.publications:
        workspace.resolver().read(publication.reference,caller=workspace._caller)


def _verify_rows(connection, request):
    _match(connection, request)
    incoming = request.registration.inventory.as_p1_bundle()
    with Session(connection, join_transaction_mode='create_savepoint') as session:
        actual = load_validated_bundle(session)
        for name in RECORDS:
            existing = {r.id:r for r in getattr(actual,name)}
            if any(existing.get(r.id) != r for r in getattr(incoming,name)):
                raise OperationError('Actual database metadata is missing or differs.')


def _stage(connection, workspace, request, plans):
    _plan(connection, request)
    previous = _last(connection,request.execution.id)['state']
    if previous in ('staged','committed_verified'):
        _files(workspace,request,plans)
        _verify_rows(connection,request)
        return 'staged'  # A caller-owned transaction is never a fresh commit claim.
    if previous not in ('planned','publishing','staged','files_ready','reconcile'):
        _event(connection,request.execution.id,'reconcile','interrupted')
    _event(connection,request.execution.id,'publishing')
    _files(workspace,request,plans)
    _event(connection,request.execution.id,'files_ready')
    _event(connection,request.execution.id,'registering')
    runner = SyntheticRunner()
    # Dependencies were checked durably above; the isolated in-memory runner has
    # no history to resolve them. Use the same immutable request without deps for
    # its inventory computation only, never persist this adapted request.
    plan = request.execution.model_copy(update={'dependency_run_ids': ()})
    runner.plan(plan)
    result = runner.execute(plan.id,request.registration.inventory)
    if result.error_code is not None:
        raise OperationError('Synthetic inventory execution failed.')
    with Session(connection,join_transaction_mode='create_savepoint') as session,session.begin():
        _register_rows(session,request.registration.inventory)
    _event(connection,request.execution.id,'staged')
    return 'staged'


class DurableSyntheticRunner:
    """Explicit stage API OR own-commit API. Both restricted to stylometry_test."""

    def stage(self, connection: Connection, workspace, request, plans):
        try:
            request = _request(request)
            if not isinstance(connection,Connection) or not connection.in_transaction():
                raise ValueError
            with workspace._exclusive('registration.lock'), connection.begin_nested():
                return _stage(connection,workspace,request,plans)
        except Exception:
            raise OperationError('Synthetic operation incomplete; reconcile the exact request.') from None

    def execute(self, engine: Engine, workspace, request, plans):
        """Own COMMITs explicitly, then check via an independent connection.

        Never pass a fixture-bound Connection here: stage() is for rollback tests.
        A lost commit acknowledgement is an uncertain outcome, requiring retry.
        """
        request = _request(request)
        try:
            if not isinstance(engine,Engine):
                raise ValueError
            # Reject a development URL before even opening a connection.
            u = engine.url
            if u.database != 'stylometry_test' or u.host not in ('127.0.0.1','localhost','::1') or u.query or u.drivername != 'postgresql+psycopg':
                raise ValueError
            with workspace._exclusive('registration.lock'):
                with engine.begin() as connection:
                    _plan(connection,request)
                    previous = _last(connection,request.execution.id)['state']
                    if previous not in ('staged','committed_verified'):
                        if previous not in ('planned','publishing','staged','files_ready','reconcile'):
                            _event(connection,request.execution.id,'reconcile','interrupted')
                        _event(connection,request.execution.id,'publishing')
                self._checkpoint('after_plan_commit')
                with engine.begin() as connection:
                    _target(connection)
                    _stage(connection,workspace,request,plans)
                self._checkpoint('after_stage_commit')
                # This is a fresh transaction after the previous commit returned.
                with engine.begin() as connection:
                    _target(connection)
                    _files(workspace,request,plans)
                    _verify_rows(connection,request)
                    _event(connection,request.execution.id,'committed_verified')
                self._checkpoint('after_verified_commit')
                return 'committed_verified'
        except Exception:
            # Best-effort marker, never assume an uncertain COMMIT was rolled back.
            try:
                if isinstance(engine,Engine) and engine.url.drivername == 'postgresql+psycopg' and engine.url.database == 'stylometry_test' and engine.url.host in ('127.0.0.1','localhost','::1') and not engine.url.query:
                    with engine.begin() as connection:
                        _target(connection)
                        _match(connection,request)
                        _event(connection,request.execution.id,'reconcile','interrupted')
            except Exception:
                pass
            raise OperationError('Synthetic operation incomplete; reconcile the exact request.') from None

    def history(self, connection, request):
        try:
            _target(connection)
            request = _request(request)
            _match(connection,request)
            return tuple(dict(r) for r in connection.execute(select(m.OperationEvent.__table__)
                .where(m.OperationEvent.operation_id == request.execution.id).order_by(m.OperationEvent.sequence)).mappings())
        except Exception:
            raise OperationError('Synthetic operation history unavailable.') from None

    def _checkpoint(self, stage):
        """Synthetic interruption seam; no scheduler/background worker."""
