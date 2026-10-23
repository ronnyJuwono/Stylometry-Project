"""Synthetic rollback tests; these do NOT prove a PostgreSQL COMMIT survives restart."""

from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from contextlib import contextmanager
from uuid import uuid4

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.operations import Operations
import pytest
from sqlalchemy import Column, MetaData, PrimaryKeyConstraint, String, Table, func, insert, inspect, select, text
from sqlalchemy.exc import IntegrityError

from stylometry import contracts as c, models as old, operation_models as m
from stylometry.database import create_optional_engine
from stylometry.durable_operations import DurableRequest, DurableSyntheticRunner, OperationError, create_workspace, reopen_workspace
from stylometry.experiments.configurations import ExecutionPlan
from stylometry.migration_safety import assert_empty_development_target
from stylometry.pipeline.interfaces import StageInput
from stylometry.pipeline.registration import RegistrationRequest
from stylometry.recoverable_storage import RecoverableSyntheticWorkspace, RecoveryDescriptor
from stylometry.synthetic_publishing import PublicationPlan, PublicationMetadata, SyntheticPublicationError, WriterBusy
from stylometry.upgrade_safety import assert_initialized_upgrade, schema_evidence, NEW_REVISION, CATALOG_QUERIES
from test_research_pipeline import make_inventory, replace


class Policy:
    def allows_read(self, caller, reference):
        return caller == 'synthetic-test-capability'


def revision(name):
    path = Path('migrations/versions') / name
    spec = importlib.util.spec_from_file_location('synthetic_revision', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def apply(connection, filename):
    with Operations.context(MigrationContext.configure(connection)):
        revision(filename).upgrade()


@pytest.fixture
def initialized():
    url = os.getenv('STYLOMETRY_TEST_DATABASE_URL')
    if not url:
        pytest.skip('Isolated PostgreSQL test database not configured')
    engine = create_optional_engine(url)
    connection = engine.connect()
    transaction = connection.begin()
    try:
        assert_empty_development_target(connection, database='stylometry_test')
        apply(connection,'s2b01_0001_initial.py')
        Table('alembic_version',MetaData(),Column('version_num',String(32),nullable=False),
              PrimaryKeyConstraint('version_num',name='alembic_version_pkc')).create(connection)
        connection.execute(text("INSERT INTO alembic_version VALUES ('s2b01_0001')"))
        yield connection
    finally:
        transaction.rollback()
        connection.close()
        engine.dispose()


@pytest.fixture
def upgraded(initialized):
    assert_initialized_upgrade(initialized,database='stylometry_test',target=NEW_REVISION)
    apply(initialized,'s2c03_0001_operations.py')
    initialized.execute(text("UPDATE alembic_version SET version_num='s2c03_0001'"))
    return initialized


@pytest.fixture
def operation(synthetic_bundle):
    repro = synthetic_bundle.runs[0].reproducibility
    payload = b'ARTIFICIAL DURABLE RECOVERY BYTES ONLY'
    now, document, provenance = datetime.now(timezone.utc), uuid4(), uuid4()
    from stylometry.storage import StorageReference
    import hashlib
    publication = PublicationMetadata(synthetic_only=True,operation_id=uuid4(),series_ref=document,created_at=now,
        reproducibility=repro,reference=StorageReference(object_ref=uuid4(),byte_sha256=hashlib.sha256(payload).hexdigest(),
            provenance_id=provenance,media_type='application/octet-stream',processing_version='synthetic.v1'))
    plan = PublicationPlan(metadata=publication,content=payload)
    inventory = make_inventory(publication.reference,document_id=document)
    execution = ExecutionPlan(id=uuid4(),operation='synthetic_inventory',created_at=now,reproducibility=repro,
        inputs=StageInput(study_id=inventory.study.id,corpus_id=inventory.corpus.id,version=inventory.inventory_version,
            input_objects=(),approved_method_ref=uuid4(),parameters_ref=uuid4(),reproducibility=repro))
    registration = RegistrationRequest(synthetic_only=True,operation_id=execution.id,inventory=inventory,
        publications=(publication,),reproducibility=repro,created_at=now)
    return DurableRequest(execution=execution,registration=registration,idempotency_id=uuid4()), (plan,)


@pytest.fixture
def retained(operation):
    request, plans = operation
    workspace = create_workspace(request,authorizer=Policy(),caller='synthetic-test-capability')
    original = {name:(workspace.root/name).read_bytes() for name in ('synthetic.marker','recovery.json','catalog.json','publication-ledger.json')}
    try:
        yield workspace,request,plans
    finally:
        # Explicit synthetic fixture teardown after deliberate corruption. This
        # is NOT a service recovery/repair API and never touches external roots.
        if workspace._root is not None:
            for name,content in original.items():
                (workspace.root/name).write_bytes(content)
        workspace.close()


def test_additive_migration_matches_and_preserves_existing(initialized):
    def original_definitions():
        return {key:[tuple(row) for row in initialized.execute(text(CATALOG_QUERIES[key])) if row[0] in old.Base.metadata.tables]
                for key in ('relations','columns','constraints','indexes','triggers','rules')}
    before = original_definitions()
    rows = initialized.execute(text('SELECT * FROM task ORDER BY code')).all()
    # Representative non-seed research metadata must survive the additive DDL.
    key = uuid4()
    initialized.execute(insert(old.Provenance).values(id=key,recorded_at=datetime.now(timezone.utc),evidence_ref=uuid4(),evidence_sha256='1'*64))
    assert_initialized_upgrade(initialized,database='stylometry_test',target=NEW_REVISION)
    apply(initialized,'s2c03_0001_operations.py')
    assert compare_metadata(MigrationContext.configure(initialized,opts={'compare_type':True}),m.metadata) == []
    assert len(inspect(initialized).get_table_names()) == 23  # 15 + 7 + version
    assert initialized.execute(text('SELECT * FROM task ORDER BY code')).all()==rows
    assert initialized.scalar(select(old.Provenance.id))==key
    assert len(old.Base.metadata.tables)==15
    assert len(m.NEW_TABLES)==7
    assert original_definitions()==before


@pytest.mark.parametrize('change', [
    "UPDATE alembic_version SET version_num='unknown'",
    'CREATE TABLE unexpected (id integer)',
    'CREATE VIEW unexpected AS SELECT 1 AS id',
    'CREATE SCHEMA unexpected',
    "CREATE FUNCTION public.unexpected() RETURNS integer LANGUAGE sql AS 'SELECT 1'",
    'ALTER TABLE provenance DROP CONSTRAINT ck_provenance_evidence_sha256_format',
    'ALTER TABLE corpus ALTER COLUMN version TYPE varchar(121)',
    'CREATE INDEX unexpected ON corpus(version)',
    'CREATE TRIGGER unexpected BEFORE INSERT ON corpus FOR EACH ROW EXECUTE FUNCTION suppress_redundant_updates_trigger()',
    'ALTER TABLE corpus ENABLE ROW LEVEL SECURITY',
    "DELETE FROM task WHERE code='T05'",
])
def test_upgrade_refuses_revision_schema_or_seed_drift(initialized, change):
    initialized.execute(text(change))
    with pytest.raises((ValueError,RuntimeError)):
        assert_initialized_upgrade(initialized,database='stylometry_test',target=NEW_REVISION)


@pytest.mark.parametrize('database,target', [('other',NEW_REVISION),('stylometry_dev',NEW_REVISION),('stylometry_test','head')])
def test_upgrade_exact_identity_and_target(initialized,database,target):
    with pytest.raises(ValueError):
        assert_initialized_upgrade(initialized,database=database,target=target)


def test_empty_guard_still_refuses_initialized_target(initialized):
    with pytest.raises(ValueError):
        assert_empty_development_target(initialized,database='stylometry_test')
    with pytest.raises(RuntimeError):
        revision('s2c03_0001_operations.py').downgrade()


def test_stage_is_not_commit_and_outer_rollback_reenters(upgraded,retained):
    workspace,request,plans=retained
    runner=DurableSyntheticRunner()
    savepoint=upgraded.begin_nested()
    assert runner.stage(upgraded,workspace,request,plans)=='staged'
    history=runner.history(upgraded,request)
    assert [e['state'] for e in history]==['planned','publishing','files_ready','registering','staged']
    assert not any(e['state']=='committed_verified' for e in history)
    assert upgraded.scalar(select(func.count()).select_from(m.Operation))==1
    savepoint.rollback()
    assert upgraded.scalar(select(func.count()).select_from(m.Operation))==0
    descriptor=workspace.detach()
    recovered=reopen_workspace(descriptor,request,authorizer=Policy(),caller='synthetic-test-capability')
    try:
        assert runner.stage(upgraded,recovered,request,plans)=='staged'
        history = runner.history(upgraded,request)
        assert runner.stage(upgraded,recovered,request,plans)=='staged'
        assert runner.history(upgraded,request)==history
        assert upgraded.scalar(select(func.count()).select_from(m.Operation))==1
        assert upgraded.scalar(select(func.count()).select_from(old.SourceDocument))==1
    finally:recovered.close()


def test_published_files_survive_database_failure_and_retry(upgraded,retained,monkeypatch):
    import stylometry.durable_operations as service
    workspace,request,plans=retained
    real=service._register_rows
    monkeypatch.setattr(service,'_register_rows',lambda *a:(_ for _ in ()).throw(RuntimeError('private internal detail')))
    with pytest.raises(OperationError,match='incomplete'):
        DurableSyntheticRunner().stage(upgraded,workspace,request,plans)
    assert upgraded.scalar(select(func.count()).select_from(m.Operation))==0
    assert workspace.resolver().read(plans[0].metadata.reference,caller='synthetic-test-capability')==plans[0].content
    monkeypatch.setattr(service,'_register_rows',real)
    assert DurableSyntheticRunner().stage(upgraded,workspace,request,plans)=='staged'


def test_conflicting_request_and_idempotency_rejected(upgraded,retained):
    workspace,request,plans=retained
    runner=DurableSyntheticRunner()
    runner.stage(upgraded,workspace,request,plans)
    changed=replace(request,idempotency_id=uuid4())
    with pytest.raises(OperationError):runner.stage(upgraded,workspace,changed,plans)
    with pytest.raises(SyntheticPublicationError):reopen_workspace(workspace.descriptor,changed,authorizer=Policy())
    assert upgraded.scalar(select(func.count()).select_from(m.Operation))==1


@pytest.mark.parametrize('state,previous,sequence', [('committed_verified',None,0),('files_ready','planned',1),('publishing','planned',3)])
def test_sql_event_transition_constraints(upgraded,retained,state,previous,sequence):
    workspace,request,plans=retained
    DurableSyntheticRunner().stage(upgraded,workspace,request,plans)
    with pytest.raises(IntegrityError),upgraded.begin_nested():
        upgraded.execute(insert(m.OperationEvent).values(operation_id=request.execution.id,sequence=sequence,
            previous_sequence=0 if previous else None,previous_state=previous,state=state,recorded_at=datetime.now(timezone.utc)))


@pytest.mark.parametrize('mode', ['missing','corrupt'])
def test_actual_files_rechecked_even_after_staging(upgraded,retained,mode):
    workspace,request,plans=retained
    runner=DurableSyntheticRunner();runner.stage(upgraded,workspace,request,plans)
    path=workspace.root/'objects'/plans[0].metadata.reference.object_ref.hex/'payload'
    if mode=='missing':path.unlink()
    else:path.write_bytes(b'ARTIFICIAL CORRUPTION')
    with pytest.raises(OperationError):runner.stage(upgraded,workspace,request,plans)


def test_no_content_columns_or_baseline_mutation():
    assert len(old.Base.metadata.tables)==15
    for table in m.NEW_TABLES:
        assert not any(x in col.name for col in table.columns for x in ('text','content','path','password','url','payload'))


def test_default_deny_recovery_and_no_real_root_parameter(operation,monkeypatch):
    request,plans=operation
    monkeypatch.setenv('STYLOMETRY_PRIVATE_ROOT','DO-NOT-ACCESS-SYNTHETIC-SENTINEL')
    workspace=create_workspace(request)
    try:
        with pytest.raises(SyntheticPublicationError):workspace.publish(plans[0])
        with pytest.raises(TypeError):RecoverableSyntheticWorkspace(root='arbitrary')
        descriptor=workspace.descriptor
        assert descriptor.token not in repr(descriptor) and descriptor.basename not in str(descriptor)
        with pytest.raises(SyntheticPublicationError):
            RecoverableSyntheticWorkspace.reopen(replace(descriptor,basename='..'),operation_id=request.execution.id,
                manifest_sha256=request.fingerprint,publications=request.registration.publications)
    finally:workspace.close()


@pytest.mark.parametrize('evidence',['marker','descriptor','identity','catalog'])
def test_conflicting_recovery_evidence_refused(retained,evidence):
    workspace,request,plans=retained
    descriptor=workspace.descriptor
    if evidence=='marker':(workspace.root/'synthetic.marker').write_bytes(b'INVALID SYNTHETIC MARKER')
    if evidence=='descriptor':(workspace.root/'recovery.json').write_text('{}')
    if evidence=='identity':descriptor=replace(descriptor,inode=descriptor.inode+1)
    if evidence=='catalog':
        (workspace.root/'catalog.json').write_bytes(b'{"unfinished":')
    if evidence=='catalog':
        with pytest.raises(Exception):workspace.publish(plans[0])
    else:
        with pytest.raises(SyntheticPublicationError):reopen_workspace(descriptor,request,authorizer=Policy())


@pytest.mark.parametrize('kind',['control','payload'])
def test_orphan_temporaries_detected_fail_closed(retained,kind):
    workspace,request,plans=retained
    if kind=='control':path=workspace.root/(uuid4().hex+'.tmp')
    else:
        directory=workspace.root/'objects'/plans[0].metadata.reference.object_ref.hex
        directory.mkdir();path=directory/(uuid4().hex+'.tmp')
    path.write_bytes(b'ARTIFICIAL PARTIAL WRITE')
    assert 'orphan_'+kind+'_temporary' in workspace.inspect_incomplete()
    with pytest.raises(SyntheticPublicationError):workspace.publish(plans[0],retry=True)


CHILD = '''
import json,os,sys,time
from stylometry.durable_operations import DurableRequest,reopen_workspace
from stylometry.recoverable_storage import RecoveryDescriptor
from stylometry.synthetic_publishing import PublicationPlan
class Policy:
 def allows_read(self,caller,reference):return caller=='synthetic-test-capability'
data=json.loads(sys.stdin.read())
r=DurableRequest.model_validate_json(data['request'])
d=RecoveryDescriptor.model_validate_json(data['descriptor'])
p=PublicationPlan(metadata=r.registration.publications[0],content=b'ARTIFICIAL DURABLE RECOVERY BYTES ONLY')
w=reopen_workspace(d,r,authorizer=Policy(),caller='synthetic-test-capability')
mode=data['mode']
if mode=='hold':
 with w._exclusive():
  print('LOCKED',flush=True)
  time.sleep(30)
elif mode=='crash':
 w._checkpoint=lambda stage:os._exit(23) if stage=='after_payload' else None
 w.publish(p)
elif mode=='resume':
 w.reconcile(p)
 print('VERIFIED',flush=True)
 w.detach()
'''


def child_input(workspace,request,mode):
    return json.dumps(dict(request=request.model_dump_json(),descriptor=workspace.descriptor.model_dump_json(),mode=mode))


def test_real_process_interruption_restart_and_explicit_stale_lock_recovery(retained):
    workspace,request,plans=retained
    crash=subprocess.run([sys.executable,'-c',CHILD],input=child_input(workspace,request,'crash'),text=True,capture_output=True,timeout=20)
    assert crash.returncode==23
    assert 'incomplete_publication' in _inspect_without_lock(workspace)
    with pytest.raises(WriterBusy):workspace.reconcile(plans[0])
    workspace.release_abandoned_lock()
    resumed=subprocess.run([sys.executable,'-c',CHILD],input=child_input(workspace,request,'resume'),text=True,capture_output=True,timeout=20)
    assert resumed.returncode==0 and resumed.stdout.strip()=='VERIFIED'
    assert workspace.reconcile(plans[0])==plans[0].metadata.reference
    assert workspace.inspect_incomplete()==()


def _inspect_without_lock(workspace):
    # Private synthetic fixture inspection while a stale lock deliberately exists.
    return ('incomplete_publication',) if b'object_ready' in (workspace.root/'publication-ledger.json').read_bytes() else ()


def test_live_multiprocess_writer_cannot_be_stolen_or_overwritten(retained):
    workspace,request,plans=retained
    process=subprocess.Popen([sys.executable,'-c',CHILD],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    try:
        process.stdin.write(child_input(workspace,request,'hold'));process.stdin.close()
        assert process.stdout.readline().strip()=='LOCKED'
        with pytest.raises(WriterBusy):workspace.publish(plans[0])
        with pytest.raises(WriterBusy):workspace.release_abandoned_lock()
        assert not (workspace.root/'objects'/plans[0].metadata.reference.object_ref.hex).exists()
    finally:
        process.terminate();process.wait(timeout=10)
    workspace.release_abandoned_lock()
    workspace.publish(plans[0])


def test_unavailable_science_and_development_engine_refused_before_connect(retained,monkeypatch):
    workspace,request,plans=retained
    from sqlalchemy.engine import Engine
    monkeypatch.setattr(Engine,'connect',lambda *a,**k:pytest.fail('Unexpected connection'))
    engine=create_optional_engine('postgresql+psycopg://synthetic@127.0.0.1/stylometry_dev')
    try:
        with pytest.raises(OperationError):DurableSyntheticRunner().execute(engine,workspace,request,plans)
        scientific=replace(request,execution=replace(request.execution,operation='scientific_stage'))
        with pytest.raises(OperationError,match='unavailable'):create_workspace(scientific)
    finally:engine.dispose()


def test_migration_advisory_lock_refuses_another_connection(initialized):
    assert_initialized_upgrade(initialized,database='stylometry_test',target=NEW_REVISION)
    engine=create_optional_engine(os.environ['STYLOMETRY_TEST_DATABASE_URL'])
    try:
        with engine.connect() as other,other.begin():
            with pytest.raises(ValueError,match='in progress'):
                assert_initialized_upgrade(other,database='stylometry_test',target=NEW_REVISION)
    finally:engine.dispose()


def test_journal_request_hash_and_digest_constraints(upgraded,retained):
    workspace,request,plans=retained
    DurableSyntheticRunner().stage(upgraded,workspace,request,plans)
    with pytest.raises(IntegrityError),upgraded.begin_nested():
        upgraded.execute(text("UPDATE research_operation SET manifest_sha256='invalid'"))
    with pytest.raises(IntegrityError),upgraded.begin_nested():
        upgraded.execute(text('UPDATE research_operation SET synthetic_only=false'))
    with pytest.raises(IntegrityError),upgraded.begin_nested():
        upgraded.execute(insert(m.OperationDependency).values(operation_id=request.execution.id,
            dependency_id=request.execution.id,study_id=request.execution.inputs.study_id))


def test_completed_object_missing_before_catalog_is_not_recreated(retained):
    workspace,request,plans=retained
    def fail(stage):
        if stage=='after_payload':raise RuntimeError('synthetic interruption')
    workspace._checkpoint=fail
    with pytest.raises(SyntheticPublicationError):workspace.publish(plans[0])
    payload=workspace.root/'objects'/plans[0].metadata.reference.object_ref.hex/'payload'
    payload.unlink()
    workspace._checkpoint=lambda stage:None
    with pytest.raises(SyntheticPublicationError):workspace.reconcile(plans[0])
    assert not payload.exists()


class RollbackBoundaryEngine(__import__('sqlalchemy').engine.Engine):
    """Model execute() transaction boundaries with savepoints, NOT real COMMITs.

    It deliberately uses one connection under the fixture's rollback. These tests
    validate ordering/re-entry only, not independent visibility or crash durability.
    """
    def __init__(self, connection):
        self.connection=connection
        self.url=connection.engine.url
        self.boundaries=0

    @contextmanager
    def begin(self):
        self.boundaries+=1
        with self.connection.begin_nested():yield self.connection


@pytest.mark.parametrize('interruption',['after_plan_commit','after_stage_commit','after_verified_commit'])
def test_modeled_commit_boundaries_and_uncertain_acknowledgements(upgraded,retained,interruption):
    workspace,request,plans=retained
    engine=RollbackBoundaryEngine(upgraded)
    runner=DurableSyntheticRunner()
    def fail(stage):
        if stage==interruption:raise RuntimeError('synthetic lost acknowledgement')
    runner._checkpoint=fail
    with pytest.raises(OperationError):runner.execute(engine,workspace,request,plans)
    assert runner.history(upgraded,request)[-1]['state']=='reconcile'
    descriptor=workspace.detach()
    recovered=reopen_workspace(descriptor,request,authorizer=Policy(),caller='synthetic-test-capability')
    try:
        runner._checkpoint=lambda stage:None
        assert runner.execute(engine,recovered,request,plans)=='committed_verified'
        history=runner.history(upgraded,request)
        assert runner.execute(engine,recovered,request,plans)=='committed_verified'
        assert runner.history(upgraded,request)==history
        assert engine.boundaries>=7
        assert upgraded.scalar(select(func.count()).select_from(m.Operation))==1
    finally:recovered.close()


def test_durable_dependency_and_rerun_identity(upgraded,retained):
    workspace,request,plans=retained
    runner=DurableSyntheticRunner()
    runner.execute(RollbackBoundaryEngine(upgraded),workspace,request,plans)
    new_id=uuid4()
    rerun=replace(request,execution=replace(request.execution,id=new_id,dependency_run_ids=(request.execution.id,)),
        registration=replace(request.registration,operation_id=new_id),idempotency_id=uuid4())
    another=create_workspace(rerun,authorizer=Policy(),caller='synthetic-test-capability')
    try:
        assert runner.stage(upgraded,another,rerun,plans)=='staged'
        assert upgraded.scalar(select(func.count()).select_from(m.Operation))==2
        assert upgraded.scalar(select(func.count()).select_from(m.OperationDependency))==1
    finally:another.close()


def test_unknown_dependency_and_reused_idempotency_refused(upgraded,retained):
    workspace,request,plans=retained
    runner=DurableSyntheticRunner();runner.stage(upgraded,workspace,request,plans)
    for dependencies in ((),(uuid4(),)):
        new_id=uuid4()
        conflict=replace(request,execution=replace(request.execution,id=new_id,dependency_run_ids=dependencies),
            registration=replace(request.registration,operation_id=new_id))
        another=create_workspace(conflict,authorizer=Policy(),caller='synthetic-test-capability')
        try:
            with pytest.raises(OperationError):runner.stage(upgraded,another,conflict,plans)
        finally:another.close()
    assert upgraded.scalar(select(func.count()).select_from(m.Operation))==1


def test_real_alembic_upgrade_entrypoint_in_rollback_fixture(initialized,monkeypatch):
    from alembic import command
    from alembic.config import Config
    monkeypatch.setenv('STYLOMETRY_MIGRATION_TARGET','stylometry_test')
    monkeypatch.setenv('STYLOMETRY_MIGRATION_MODE','initialized')
    monkeypatch.setenv('STYLOMETRY_MIGRATION_REVISION',NEW_REVISION)
    config=Config('alembic.ini');config.attributes['connection']=initialized
    command.upgrade(config,NEW_REVISION)
    assert initialized.scalar(text('SELECT version_num FROM alembic_version'))==NEW_REVISION
    assert len(inspect(initialized).get_table_names())==23
    with pytest.raises(RuntimeError,match='Migration refused'):
        command.upgrade(config,NEW_REVISION)  # Already upgraded, never silently reapply.


@pytest.mark.parametrize('target',['head','s2b01_0001'])
def test_initialized_entrypoint_refuses_nonexact_revision(initialized,monkeypatch,target):
    from alembic import command
    from alembic.config import Config
    monkeypatch.setenv('STYLOMETRY_MIGRATION_TARGET','stylometry_test')
    monkeypatch.setenv('STYLOMETRY_MIGRATION_MODE','initialized')
    monkeypatch.setenv('STYLOMETRY_MIGRATION_REVISION',NEW_REVISION)
    config=Config('alembic.ini');config.attributes['connection']=initialized
    with pytest.raises(RuntimeError,match='Migration refused'):command.upgrade(config,target)


def test_offline_successor_cannot_bypass_preflight():
    from alembic import command
    from alembic.config import Config
    with pytest.raises(RuntimeError,match='Offline successor'):
        command.upgrade(Config('alembic.ini'),NEW_REVISION,sql=True)


@pytest.mark.parametrize('change',["SET LOCAL search_path=pg_catalog,public",'CREATE TEMP TABLE ambiguous (id integer)'])
def test_upgrade_refuses_ambiguous_session_namespace(initialized,change):
    initialized.execute(text(change))
    with pytest.raises(ValueError):assert_initialized_upgrade(initialized,database='stylometry_test',target=NEW_REVISION)


def test_operation_cooperative_lock_is_held_across_transaction(upgraded,retained):
    workspace,request,plans=retained
    DurableSyntheticRunner().stage(upgraded,workspace,request,plans)
    engine=create_optional_engine(os.environ['STYLOMETRY_TEST_DATABASE_URL'])
    try:
        with engine.connect() as other,other.begin():
            assert other.scalar(text('SELECT pg_try_advisory_xact_lock(21302405)')) is False
    finally:engine.dispose()


@pytest.mark.parametrize('filename', ['recovery.json','publication-ledger.json'])
def test_duplicate_or_partial_private_evidence_is_sanitized(retained,filename):
    workspace,request,plans=retained
    path=workspace.root/filename
    data=path.read_text()
    first=json.loads(data)
    key=next(iter(first))
    path.write_text('{'+json.dumps(key)+':null,'+data[1:])
    with pytest.raises(SyntheticPublicationError) as error:workspace.publish(plans[0])
    assert str(workspace.root) not in str(error.value)


def test_cleanup_refuses_live_writer_before_deleting_anything(retained):
    workspace,request,plans=retained
    workspace.publish(plans[0])
    with workspace._exclusive():
        with pytest.raises(WriterBusy):workspace.close()
        assert (workspace.root/'catalog.json').exists()
        assert workspace.resolver().verify(plans[0].metadata.reference,caller='synthetic-test-capability')


def test_closing_marker_requires_cleanup_only_reopen(retained):
    workspace,request,plans=retained
    (workspace.root/'closing.marker').write_bytes(workspace._token)
    descriptor=workspace.descriptor
    with pytest.raises(SyntheticPublicationError):reopen_workspace(descriptor,request,authorizer=Policy())
    clean=RecoverableSyntheticWorkspace.reopen(descriptor,operation_id=request.execution.id,
        manifest_sha256=request.fingerprint,publications=request.registration.publications,cleanup_only=True)
    with pytest.raises(SyntheticPublicationError):clean.publish(plans[0])
    workspace._root=None  # Hand off the exact owned test root to the cleanup capability.
    clean.close()


def test_different_operation_cannot_rebind_existing_object_uuid(upgraded,retained):
    import hashlib
    workspace,request,plans=retained
    runner=DurableSyntheticRunner();runner.stage(upgraded,workspace,request,plans)
    new_id=uuid4()
    content=b'OTHER ARTIFICIAL CONTENT'
    digest=hashlib.sha256(content).hexdigest()
    publication=replace(plans[0].metadata,reference=replace(plans[0].metadata.reference,byte_sha256=digest))
    inventory=replace(request.registration.inventory,documents=(replace(request.registration.inventory.documents[0],byte_sha256=digest),))
    conflicting=replace(request,execution=replace(request.execution,id=new_id),idempotency_id=uuid4(),
        registration=replace(request.registration,operation_id=new_id,inventory=inventory,publications=(publication,)))
    another=create_workspace(conflicting,authorizer=Policy(),caller='synthetic-test-capability')
    try:
        with pytest.raises(OperationError):runner.stage(upgraded,another,conflicting,(PublicationPlan(metadata=publication,content=content),))
        assert upgraded.scalar(select(func.count()).select_from(m.Operation))==1
    finally:another.close()


def test_autocommit_cannot_masquerade_as_a_guarded_transaction(initialized,retained):
    workspace,request,plans=retained
    engine=create_optional_engine(os.environ['STYLOMETRY_TEST_DATABASE_URL'])
    try:
        with engine.connect().execution_options(isolation_level='AUTOCOMMIT') as connection,connection.begin():
            with pytest.raises(ValueError,match='real PostgreSQL transaction'):
                assert_initialized_upgrade(connection,database='stylometry_test',target=NEW_REVISION)
            with pytest.raises(OperationError):DurableSyntheticRunner().stage(connection,workspace,request,plans)
    finally:engine.dispose()
