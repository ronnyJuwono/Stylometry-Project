"""Explicit owned-cluster live validation. No connections or cluster setup on import.

Run only with separate authorization: python tools/validate_s2c03_durability.py --run-owned-cluster
Credentials, paths, descriptors and server logs stay in private owned scratch.
Existing databases/services are never used by this harness.
"""

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import time
import traceback
from uuid import uuid4

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
import psycopg
from psycopg import sql
from sqlalchemy import Column, MetaData, PrimaryKeyConstraint, String, Table, create_engine, inspect, select, text
from sqlalchemy.engine import URL

from stylometry import contracts as c, models as old
from stylometry.durable_operations import DurableRequest, DurableSyntheticRunner, OperationError, create_workspace, reopen_workspace, _verify_rows
from stylometry.experiments.configurations import ExecutionPlan
from stylometry.migration_safety import assert_empty_development_target
from stylometry.pipeline.interfaces import StageInput
from stylometry.pipeline.registration import RegistrationRequest
from stylometry.recoverable_storage import RecoveryDescriptor, _process_stamp
from stylometry.storage import StorageReference, StorageAccessDenied
from stylometry.synthetic_publishing import PublicationMetadata, PublicationPlan, SyntheticPublicationError, WriterBusy, _pin_directory
from stylometry.upgrade_safety import assert_initialized_upgrade, CATALOG_QUERIES
from stylometry.private_filesystem import read_private_file

REPO = Path(__file__).resolve().parents[1]
BIN = Path('C:/Program Files/PostgreSQL/18/bin')
DATABASE = 'stylometry_test'
REVIEWED = 'e298919059762f8883e297c584f134878114ab0e'
POINTER = REPO / '.env.s2c03b-owned-location'
PROTECTED = ('src', 'migrations', 'app.py', 'alembic.ini', 'pyproject.toml', 'uv.lock')


def check(condition, message):
    if not condition:
        raise AssertionError(message)  # Fixed engineering labels only.


def verify_reviewed_application(repo=REPO, reviewed=REVIEWED):
    """Accept later evidence commits, but pin HEAD, index and actual runtime bytes."""
    def git(*args):
        result = subprocess.run(['git', *args], cwd=repo, capture_output=True)
        check(result.returncode == 0, 'Reviewed application verification failed')
        return result.stdout

    git('merge-base', '--is-ancestor', reviewed, 'HEAD')
    for target in ('HEAD', '--cached'):
        git('diff', '--no-ext-diff', '--no-textconv', '--exit-code', reviewed, target, '--', *PROTECTED)
    names = git('ls-tree', '-r', '--name-only', reviewed, '--', *PROTECTED).decode().splitlines()
    check(bool(names), 'Reviewed application inventory missing')
    expected = set(names)
    actual = set()
    for name in PROTECTED:
        path = repo / name
        paths = path.rglob('*') if path.is_dir() else (path,)
        for candidate in paths:
            relative = candidate.relative_to(repo)
            if any(part == '__pycache__' or part.endswith('.egg-info') for part in relative.parts):
                continue  # Interpreter/install metadata, never imported source.
            check(not candidate.is_symlink() and not getattr(candidate.lstat(), 'st_file_attributes', 0) & 0x400,
                  'Protected application link refused')
            if candidate.is_file():
                actual.add(relative.as_posix())
    check(actual == expected, 'Protected application file inventory changed')
    for name in names:
        # Check bytes directly as well: assume-unchanged/skip-worktree cannot hide edits.
        baseline = git('show', reviewed + ':' + name)
        current = (repo / name).read_bytes()
        check(current.replace(b'\r\n', b'\n') == baseline.replace(b'\r\n', b'\n'),
              'Protected application contents changed')


def private_json(root, name):
    return json.loads(read_private_file(root, (name,), limit=32768))


@contextmanager
def verified_worker_config(data):
    """Anchor worker input to the parent's private lifecycle record before connecting.

    Capabilities travel over stdin only. This is ownership evidence within the
    existing trusted-same-account boundary, not authentication against that user.
    """
    check(os.name == 'nt', 'Windows-only owned worker')
    capability = data.get('ownership', {})
    check(isinstance(capability, dict) and type(capability.get('token')) is str
          and type(capability.get('root')) is str, 'Worker ownership evidence required')
    pointer = private_json(REPO, POINTER.name)
    root = Path(pointer['root'])
    parent = Path(tempfile.gettempdir()).resolve()
    check(root.is_absolute() and root.parent == parent and root.name.startswith('stylometry-durability-')
          and not root.is_relative_to(REPO) and not REPO.is_relative_to(root), 'Worker allocation refused')
    check(type(capability.get('token')) is str and type(pointer['token']) is str
          and secrets.compare_digest(capability['token'], pointer['token'])
          and capability.get('root') == str(root)
          and type(pointer['pid']) is int and pointer['pid'] > 0
          and type(pointer['process_stamp']) is int
          and _process_stamp(pointer['pid']) == pointer['process_stamp'],
          'Worker ownership capability refused')
    with _pin_directory(root), _pin_directory(root / 'cluster'):
        check(root.resolve() == root, 'Worker root moved')
        record = private_json(root, 'instance-private.json')
        marker = read_private_file(root, ('owner.marker',), limit=256).decode()
        info, cluster = root.lstat(), (root / 'cluster').lstat()
        check(record['root'] == str(root) and record['identity'] == [info.st_dev, info.st_ino]
              and record['data_directory'] == str(root / 'cluster')
              and record['data_identity'] == [cluster.st_dev, cluster.st_ino], 'Worker directory identity refused')
        check(type(record['token']) is str and secrets.compare_digest(record['token'], pointer['token'])
              and secrets.compare_digest(marker, pointer['token']), 'Worker marker refused')
        config = {key: record[key] for key in ('host', 'port', 'database', 'user', 'password', 'system_id', 'data_directory')}
        check(config == data.get('config'), 'Worker target differs from private record')
        check(config['host'] == '127.0.0.1' and config['database'] == DATABASE
              and type(config['port']) is int and 1 <= config['port'] <= 65535 and config['port'] != 5432
              and type(config['system_id']) is str and config['system_id'].isdigit()
              and int(config['system_id']) > 0, 'Worker target identity refused')
        pid = read_private_file(root, ('cluster', 'postmaster.pid'), limit=4096).decode().splitlines()
        check(len(pid) >= 6 and Path(pid[1]) == root / 'cluster' and int(pid[3]) == config['port']
              and pid[5] == '127.0.0.1', 'Worker postmaster evidence refused')
        yield config


def port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        value = sock.getsockname()[1]
    check(value != 5432, 'Reserved port refused')
    return value


def connect_config(config):
    return dict(host='127.0.0.1', port=config['port'], dbname=DATABASE,
                user=config['user'], password=config['password'], connect_timeout=5)


def engine_for(config, *, acknowledgement=None):
    url = URL.create('postgresql+psycopg', username=config['user'], password=config['password'],
                     host='127.0.0.1', port=config['port'], database=DATABASE)
    if acknowledgement is None:
        return create_engine(url, hide_parameters=True, connect_args={'connect_timeout':5})

    class AckConnection(psycopg.Connection):
        commits = 0

        def commit(self):
            super().commit()  # Actual PostgreSQL COMMIT, never a savepoint/mock.
            type(self).commits += 1
            if type(self).commits == acknowledgement:
                raise psycopg.OperationalError('Synthetic post-COMMIT acknowledgement fault')

    return create_engine(url, hide_parameters=True,
                         creator=lambda: AckConnection.connect(**connect_config(config)))


def identity(connection, config):
    result = connection.execute(text("SELECT current_database(),inet_server_addr()::text,inet_server_port(),current_setting('server_version_num'),system_identifier::text FROM pg_control_system()")).one()
    check(result[0]==DATABASE and result[1] in ('127.0.0.1','127.0.0.1/32') and tuple(result[2:])==(config['port'],'180006',config['system_id']), 'Disposable instance identity mismatch')
    check(connection.connection.driver_connection.autocommit is False, 'Autocommit refused')


def decode_case(data):
    request = DurableRequest.model_validate_json(data['request'])
    descriptor = RecoveryDescriptor.model_validate_json(data['descriptor'])
    plans = tuple(PublicationPlan.model_validate_json(p) for p in data['plans'])
    return request,descriptor,plans


class Policy:
    def allows_read(self, caller, reference):
        return caller == 'owned-artificial-validation'


def worker(data):
    with verified_worker_config(data) as config:
        return owned_worker(data, config)


def owned_worker(data, config):
    mode = data['mode']
    check(config['port'] != 5432, 'Existing service port refused')
    engine = engine_for(config,acknowledgement=data.get('acknowledgement'))
    try:
        with engine.connect() as conn:
            identity(conn,config)
            revision = conn.scalar(text('SELECT version_num FROM alembic_version'))
            count = len(inspect(conn).get_table_names())
            seeds = conn.execute(text('SELECT code,genre,form FROM task ORDER BY code')).all()
            from stylometry.paper1 import TASKS
            check([tuple(r) for r in seeds]==[(str(t.code),t.genre,t.form) for t in TASKS], 'Task seeds differ')
        if mode=='schema':
            return dict(revision=revision,tables=count,tasks=len(seeds))
        request,descriptor,plans = decode_case(data)
        workspace = reopen_workspace(descriptor,request,authorizer=Policy(),caller='owned-artificial-validation')
        try:
            if mode=='observe':
                with engine.connect() as conn:
                    identity(conn,config)
                    events=conn.execute(text('SELECT state FROM operation_event WHERE operation_id=:id ORDER BY sequence'),dict(id=request.execution.id)).scalars().all()
                    docs=conn.scalar(select(__import__('sqlalchemy').func.count()).select_from(old.SourceDocument).where(old.SourceDocument.corpus_id==request.execution.inputs.corpus_id))
                    if events and events[-1]=='committed_verified':
                        _verify_rows(conn,request)
                return dict(events=events,documents=docs,hashes=[workspace.resolver().verify(p.metadata.reference,caller='owned-artificial-validation') for p in plans])
            if mode=='hold':
                with workspace._exclusive():
                    Path(data['ready']).write_bytes(b'OWNED CHILD READY')
                    time.sleep(45)
                return dict(held=True)
            runner=DurableSyntheticRunner()
            if data.get('checkpoint'):
                def crash(stage):
                    if stage==data['checkpoint']:
                        os._exit(23)
                runner._checkpoint=crash
            if mode=='catalog_crash':
                seen=0
                def crash_catalog(stage):
                    nonlocal seen
                    if stage=='after_payload':
                        seen+=1
                        if seen==len(plans):
                            os._exit(24)
                workspace._checkpoint=crash_catalog
            try:
                result=runner.execute(engine,workspace,request,plans)
            except OperationError:
                check(mode in ('reject','acknowledgement'), 'Unexpected operation refusal')
                return dict(refused=True)
            check(mode not in ('reject','acknowledgement'), 'Expected refusal was not raised')
            return dict(state=result)
        finally:
            workspace.detach()  # Retain ONLY this owned synthetic workspace.
    finally:
        engine.dispose()


class OwnedCluster:
    def __init__(self):
        parent=Path(tempfile.gettempdir()).resolve()
        check(not parent.is_relative_to(REPO) and not REPO.is_relative_to(parent), 'Temporary parent overlaps repository')
        with _pin_directory(parent):
            self.root=Path(tempfile.mkdtemp(prefix='stylometry-durability-',dir=parent))
        self.allocated=self.root
        info=self.root.lstat()
        self.file_identity=(info.st_dev,info.st_ino)
        self.token=secrets.token_hex(32)
        (self.root/'owner.marker').write_text(self.token)
        self.data=self.root/'cluster'
        self.port=port()
        self.admin='owner_'+uuid4().hex[:12]
        self.admin_password=secrets.token_urlsafe(32)
        self.user='synthetic_'+uuid4().hex[:12]
        self.password=secrets.token_urlsafe(32)
        self.system_id=None
        self.data_identity=None
        self.running=False
        self.cases=[]
        self.records=[]
        self.phase='allocated'
        self.pointer_payload=json.dumps(dict(root=str(self.root),token=self.token,pid=os.getpid(),
                                             process_stamp=_process_stamp(os.getpid())))
        with POINTER.open('x') as handle:handle.write(self.pointer_payload)
        self.save_private()

    def owned(self):
        info=self.root.lstat()
        check(self.root==self.allocated and self.root.resolve()==self.allocated, 'Owned root moved')
        check((info.st_dev,info.st_ino)==self.file_identity and not getattr(info,'st_file_attributes',0)&0x400, 'Owned root replaced')
        check((self.root/'owner.marker').read_text()==self.token and self.port!=5432, 'Ownership marker refused')
        check(self.data.parent==self.root, 'Data directory containment refused')

    def save_private(self):
        self.owned()
        (self.root/'instance-private.json').write_text(json.dumps(dict(token=self.token,root=str(self.root),identity=self.file_identity,
            data_identity=self.data_identity,admin=self.admin,admin_password=self.admin_password,**self.config)))

    def native(self, binary, *args):
        self.owned()
        with (self.root/'native-private.log').open('ab') as handle:
            # A background PostgreSQL descendant must not retain a capture pipe
            # and keep communicate() waiting after pg_ctl itself has exited.
            result=subprocess.run([str(BIN/binary),*map(str,args)],stdout=handle,stderr=subprocess.STDOUT,
                                  timeout=45,creationflags=subprocess.CREATE_NO_WINDOW)
        check(result.returncode==0, 'Owned PostgreSQL lifecycle command failed')

    def admin_connection(self, database='postgres'):
        self.owned()
        return psycopg.connect(host='127.0.0.1',port=self.port,dbname=database,user=self.admin,
                               password=self.admin_password,connect_timeout=5,autocommit=True)

    def verify_server(self):
        self.owned()
        check(self.data.is_dir() and self.data.resolve().is_relative_to(self.root), 'Data directory refused')
        info = self.data.lstat()
        current_identity = (info.st_dev, info.st_ino)
        check(not getattr(info, 'st_file_attributes', 0) & 0x400
              and (self.data_identity is None or self.data_identity == current_identity), 'Cluster directory replaced')
        self.data_identity = current_identity
        with self.admin_connection() as conn:
            row=conn.execute("SELECT current_setting('data_directory'),inet_server_addr()::text,inet_server_port(),current_setting('server_version_num'),system_identifier::text FROM pg_control_system()").fetchone()
            check(Path(row[0]).resolve()==self.data.resolve() and row[1] in ('127.0.0.1','127.0.0.1/32') and tuple(row[2:4])==(self.port,'180006'), 'Server ownership or address mismatch')
            if self.system_id is not None:
                check(row[4]==self.system_id, 'Cluster system identifier changed')
            self.system_id=row[4]
        lines=(self.data/'postmaster.pid').read_text().splitlines()
        check(Path(lines[1]).resolve()==self.data.resolve() and int(lines[3])==self.port, 'Owned postmaster evidence mismatch')
        self.save_private()

    @property
    def config(self):
        return dict(host='127.0.0.1',database=DATABASE,port=self.port,user=self.user,password=self.password,
                    system_id=self.system_id,data_directory=str(self.data))

    @property
    def ownership(self):
        return dict(root=str(self.root), token=self.token)

    def start(self):
        try:
            self.native('pg_ctl.exe','-D',self.data,'-l',self.root/'server-private.log','-w','-t','30','start')
        except Exception:
            if (self.data/'postmaster.pid').exists():
                self.running=True  # Cleanup still must verify ownership before stopping.
            raise
        self.running=True
        self.verify_server()

    def stop(self):
        if self.running:
            self.verify_server()
            self.native('pg_ctl.exe','-D',self.data,'-m','fast','-w','-t','30','stop')
            self.running=False
            check(not (self.data/'postmaster.pid').exists(), 'Owned postmaster still present')

    def record(self, label):
        self.records.append(label)
        print(json.dumps(dict(check=label,result='passed')),flush=True)

    def bootstrap(self):
        self.phase='cluster initialization'
        password_file=self.root/'init-password'
        password_file.write_text(self.admin_password)
        self.native('initdb.exe','-D',self.data,'-U',self.admin,'--pwfile',password_file,'-A','scram-sha-256','--encoding=UTF8','--locale=C')
        password_file.unlink()
        with (self.data/'postgresql.conf').open('a') as handle:
            handle.write(f"\nlisten_addresses='127.0.0.1'\nport={self.port}\nfsync=on\nsynchronous_commit=on\nfull_page_writes=on\nshared_buffers='32MB'\nmax_connections=12\nlogging_collector=off\nlog_statement='none'\nlog_min_error_statement='panic'\n")
        self.start()
        with self.admin_connection() as conn:
            check(conn.execute('SELECT datname FROM pg_database WHERE datname=%s',(DATABASE,)).fetchone() is None,'Disposable database already exists')
            conn.execute(sql.SQL('CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE').format(sql.Identifier(self.user),sql.Literal(self.password)))
            conn.execute(sql.SQL('CREATE DATABASE {} OWNER {}').format(sql.Identifier(DATABASE),sql.Identifier(self.user)))
        with self.admin_connection(DATABASE) as conn:
            conn.execute(sql.SQL('GRANT EXECUTE ON FUNCTION pg_control_system() TO {}').format(sql.Identifier(self.user)))
        self.record('separate PostgreSQL 18.6 cluster, loopback port and dedicated role verified')
        self.phase='initial migration'
        engine=engine_for(self.config)
        try:
            with engine.begin() as conn:
                identity(conn,self.config)
                assert_empty_development_target(conn,database=DATABASE)
                spec=importlib.util.spec_from_file_location('frozen_initial',REPO/'migrations/versions/s2b01_0001_initial.py')
                initial=importlib.util.module_from_spec(spec);spec.loader.exec_module(initial)
                with Operations.context(MigrationContext.configure(conn)):
                    initial.upgrade()
                Table('alembic_version',MetaData(),Column('version_num',String(32),nullable=False),PrimaryKeyConstraint('version_num',name='alembic_version_pkc')).create(conn)
                conn.execute(text("INSERT INTO alembic_version VALUES ('s2b01_0001')"))
            check(self.child('schema')==dict(revision='s2b01_0001',tables=16,tasks=5),'Independent initial COMMIT visibility failed')
            self.record('initial migration real COMMIT independently visible: 15 tables, version and five seeds')
            self.phase='successor preflight'
            for statement,label in (("UPDATE alembic_version SET version_num='unknown'",'wrong predecessor revision refused'),
                                    ('CREATE TABLE public.unexpected_drift (id integer)','unknown predecessor schema drift refused')):
                with engine.connect() as conn,conn.begin() as transaction:
                    conn.execute(text(statement))
                    try:assert_initialized_upgrade(conn,database=DATABASE,target='s2c03_0001')
                    except ValueError:pass
                    else:raise AssertionError('Initialized guard accepted drift')
                    transaction.rollback()
                self.record(label)
            with engine.connect() as conn:
                before={key:[tuple(row) for row in conn.execute(text(CATALOG_QUERIES[key])) if row[0] in old.Base.metadata.tables]
                        for key in ('relations','columns','constraints','indexes','triggers','rules')}
            self.phase='successor migration'
            previous={k:os.environ.get(k) for k in ('STYLOMETRY_MIGRATION_TARGET','STYLOMETRY_MIGRATION_MODE','STYLOMETRY_MIGRATION_REVISION')}
            try:
                os.environ.update(STYLOMETRY_MIGRATION_TARGET=DATABASE,STYLOMETRY_MIGRATION_MODE='initialized',STYLOMETRY_MIGRATION_REVISION='s2c03_0001')
                with engine.begin() as conn:
                    identity(conn,self.config)
                    config=Config(str(REPO/'alembic.ini'));config.attributes['connection']=conn
                    command.upgrade(config,'s2c03_0001')
            finally:
                for k,v in previous.items():
                    if v is None:os.environ.pop(k,None)
                    else:os.environ[k]=v
            check(self.child('schema')==dict(revision='s2c03_0001',tables=23,tasks=5),'Independent successor COMMIT visibility failed')
            with engine.connect() as conn:
                after={key:[tuple(row) for row in conn.execute(text(CATALOG_QUERIES[key])) if row[0] in old.Base.metadata.tables]
                       for key in before}
                check(before==after,'Original schema definitions changed')
                for setting in ('fsync','synchronous_commit','full_page_writes'):
                    check(conn.scalar(text('SHOW '+setting))=='on','Durability setting disabled')
            self.record('guarded successor real COMMIT independently visible: 22 tables, version and unchanged seeds/schema')
        finally:engine.dispose()

    def case(self, *, count=1, request=None, plans=None):
        if request is None:
            sys.path.insert(0,str(REPO/'tests'))
            from test_research_pipeline import make_inventory,replace
            now=datetime.now(timezone.utc)
            repro=c.Reproducibility(configuration_version='synthetic.durability.v1',configuration_ref=uuid4(),
                configuration_sha256=c.canonical_sha256({'synthetic_only':True,'operation':'durability_validation'}),code_commit=REVIEWED,
                working_tree_dirty=True,environment_lock_sha256=hashlib.sha256((REPO/'uv.lock').read_bytes()).hexdigest())
            plans=[]
            for index in range(count):
                payload=b'ARTIFICIAL DURABILITY VALIDATION BYTES '+str(index).encode()
                metadata=PublicationMetadata(synthetic_only=True,operation_id=uuid4(),series_ref=uuid4(),created_at=now,reproducibility=repro,
                    reference=StorageReference(object_ref=uuid4(),byte_sha256=hashlib.sha256(payload).hexdigest(),provenance_id=uuid4(),
                        media_type='application/octet-stream',processing_version='synthetic.source.v1'))
                plans.append(PublicationPlan(metadata=metadata,content=payload))
            inventory=make_inventory(plans[0].metadata.reference,document_id=plans[0].metadata.series_ref)
            for plan in plans[1:]:
                metadata=plan.metadata
                provenance=c.Provenance(id=metadata.reference.provenance_id,recorded_at=now,evidence_ref=uuid4(),evidence_sha256='1'*64)
                document=c.SourceDocument(id=metadata.series_ref,corpus_id=inventory.corpus.id,private_object_ref=metadata.reference.object_ref,
                    byte_sha256=metadata.reference.byte_sha256,media_type=metadata.reference.media_type,provenance_id=provenance.id,acquired_at=now)
                inventory=replace(inventory,provenance=(*inventory.provenance,provenance),documents=(*inventory.documents,document))
            execution=ExecutionPlan(id=uuid4(),operation='synthetic_inventory',created_at=now,reproducibility=repro,
                inputs=StageInput(study_id=inventory.study.id,corpus_id=inventory.corpus.id,version=inventory.inventory_version,input_objects=(),
                    approved_method_ref=uuid4(),parameters_ref=uuid4(),reproducibility=repro))
            registration=RegistrationRequest(synthetic_only=True,operation_id=execution.id,inventory=inventory,
                publications=tuple(p.metadata for p in plans),reproducibility=repro,created_at=now)
            request=DurableRequest(execution=execution,registration=registration,idempotency_id=uuid4())
        workspace=create_workspace(request,authorizer=Policy(),caller='owned-artificial-validation')
        descriptor=workspace.detach()
        data=dict(request=request.model_dump_json(),descriptor=descriptor.model_dump_json(),plans=[p.model_dump_json() for p in plans])
        self.cases.append(data)
        (self.root/('case-'+str(len(self.cases))+'.json')).write_text(json.dumps(data))
        return data

    def child(self, mode, case=None, *, expected=0, **extra):
        self.verify_server()
        data=dict(config=self.config,ownership=self.ownership,mode=mode,**(case or {}),**extra)
        result=subprocess.run([sys.executable,str(Path(__file__).resolve()),'--worker'],input=json.dumps(data),text=True,
            capture_output=True,timeout=35,creationflags=subprocess.CREATE_NO_WINDOW,cwd=REPO)
        if result.stderr:
            with (self.root/'child-private.log').open('a') as handle:handle.write(result.stderr)
        check(result.returncode==expected,'Independent child outcome mismatch')
        return json.loads(result.stdout) if expected==0 else None

    def unlock(self, case):
        request,descriptor,_=decode_case(case)
        workspace=reopen_workspace(descriptor,request,authorizer=Policy(),caller='owned-artificial-validation')
        try:
            for name in ('writer.lock','registration.lock'):
                if (workspace.root/name).exists():
                    workspace.release_abandoned_lock(name)
        finally:workspace.detach()

    def complete(self, case):
        check(self.child('execute',case)==dict(state='committed_verified'),'Actual engine execution failed')
        first=self.child('observe',case)
        check(first['events'][-1]=='committed_verified' and all(first['hashes']),'Independent committed verification failed')
        self.child('execute',case)
        check(self.child('observe',case)==first,'Repeated reconciliation changed completed state')
        return first

    def validate(self):
        self.phase='real operation COMMIT checkpoints'
        positive=[]
        for checkpoint,state in (('after_plan_commit','publishing'),('after_stage_commit','staged'),('after_verified_commit','committed_verified')):
            case=self.case();positive.append(case)
            self.child('execute',case,checkpoint=checkpoint,expected=23)
            observation=self.child('observe',case)
            check(observation['events'][-1]==state,'Confirmed COMMIT not visible after process death')
            check(observation['documents']==(0 if state=='publishing' else 1),'Unexpected committed research rows')
            self.unlock(case)
            self.complete(case)
            self.record(checkpoint+': real COMMIT survives process exit; independent resume and idempotency passed')
        self.phase='catalog interruption'
        case=self.case(count=2);positive.append(case)
        self.child('catalog_crash',case,expected=24)
        partial=self.child('observe',case)
        check(partial['hashes']==[True,False] and partial['events'][-1]=='publishing','Prior catalog entry or partial-transition evidence invalid')
        self.unlock(case)
        self.complete(case)
        self.record('interrupted second publication preserves first catalog entry; explicit dead-owner recovery passed')
        self.phase='post-COMMIT acknowledgement injection'
        for ordinal in (1,2,3):
            case=self.case();positive.append(case)
            check(self.child('acknowledgement',case,acknowledgement=ordinal)==dict(refused=True),'Acknowledgement fault missing')
            observation=self.child('observe',case)
            check(observation['events'][-1]=='reconcile','Uncertain COMMIT not marked for reconciliation')
            check(observation['documents']==(0 if ordinal==1 else 1),'Actual COMMIT rows not independently visible')
            self.complete(case)
            self.record(f'actual COMMIT {ordinal} followed by controlled driver acknowledgement exception: persisted rows and retry verified')
        self.phase='orderly owned server restart'
        before=[self.child('observe',case) for case in positive]
        system_id=self.system_id
        self.stop();self.start()
        check(system_id==self.system_id,'Restart changed cluster identity')
        check(self.child('schema')==dict(revision='s2c03_0001',tables=23,tasks=5),'Schema did not survive server restart')
        for case,prior in zip(positive,before):
            check(self.child('observe',case)==prior,'Rows, history or files changed after server restart')
            check(self.complete(case)==prior,'Post-restart reconciliation changed completed operation')
        self.record('orderly restart of owned server: exact cluster identity, revisions, seven operations and eight object hashes persist')
        self.negative(positive[0])

    def negative(self, completed):
        from test_research_pipeline import replace
        self.phase='negative validation'
        request,descriptor,plans=decode_case(completed)
        before=self.child('observe',completed)
        conflicts=[('conflicting manifest',replace(request,idempotency_id=uuid4()),plans)]
        new_id=uuid4()
        conflicts.append(('reused idempotency',replace(request,execution=replace(request.execution,id=new_id),
            registration=replace(request.registration,operation_id=new_id)),plans))
        pub=replace(plans[0].metadata,reference=replace(plans[0].metadata.reference,processing_version='conflicting.v2'))
        conflicts.append(('conflicting version',replace(request,registration=replace(request.registration,publications=(pub,))),
            (PublicationPlan(metadata=pub,content=plans[0].content),)))
        digest=hashlib.sha256(b'CONFLICTING ARTIFICIAL BYTES').hexdigest()
        pub=replace(plans[0].metadata,reference=replace(plans[0].metadata.reference,byte_sha256=digest))
        inventory=replace(request.registration.inventory,documents=(replace(request.registration.inventory.documents[0],byte_sha256=digest),))
        conflicts.append(('conflicting object hash',replace(request,registration=replace(request.registration,inventory=inventory,publications=(pub,))),
            (PublicationPlan(metadata=pub,content=b'CONFLICTING ARTIFICIAL BYTES'),)))
        for label,changed,changed_plans in conflicts:
            other=self.case(request=changed,plans=changed_plans)
            check(self.child('reject',other)==dict(refused=True),'Conflicting request accepted')
            check(self.child('observe',completed)==before,'Conflict changed completed state')
            self.record(label+' refused without overwriting completed state')
        workspace=reopen_workspace(descriptor,request)  # No allow policy.
        try:
            try:workspace.resolver().read(plans[0].metadata.reference)
            except StorageAccessDenied:pass
            else:raise AssertionError('Unauthorized reader accepted')
        finally:workspace.detach()
        self.record('unauthorized reader refused after restart')
        for damage in ('missing','corrupted'):
            case=self.case();self.complete(case)
            r,d,p=decode_case(case)
            workspace=reopen_workspace(d,r,authorizer=Policy(),caller='owned-artificial-validation')
            try:
                payload=workspace.root/'objects'/p[0].metadata.reference.object_ref.hex/'payload'
                check(payload.resolve().is_relative_to(workspace.root.resolve()),'Payload containment refused')
                if damage=='missing':payload.unlink()
                else:payload.write_bytes(b'ARTIFICIAL CORRUPTION')
            finally:workspace.detach()
            check(self.child('reject',case)==dict(refused=True),'Damaged object accepted')
            self.record(damage+' completed object fails closed after real COMMIT')
        self.live_writer(completed)
        workspace=reopen_workspace(descriptor,request,authorizer=Policy(),caller='owned-artificial-validation')
        try:
            orphan=workspace.root/(uuid4().hex+'.tmp')
            orphan.write_bytes(b'ARTIFICIAL PARTIAL CONTROL EVIDENCE')
            check('orphan_control_temporary' in workspace.inspect_incomplete(),'Orphan evidence undetected')
            try:workspace.reconcile(plans[0])
            except SyntheticPublicationError:pass
            else:raise AssertionError('Orphan evidence accepted')
            orphan.unlink()  # Exact newly created artificial test file, not service repair.
        finally:workspace.detach()
        self.record('orphan partial control evidence detected and publication refused')
        engine=engine_for(self.config)
        try:
            with engine.connect() as conn,conn.begin() as tx:
                conn.execute(text("UPDATE alembic_version SET version_num='unknown'"))
                workspace=reopen_workspace(descriptor,request,authorizer=Policy(),caller='owned-artificial-validation')
                try:
                    try:DurableSyntheticRunner().stage(conn,workspace,request,plans)
                    except OperationError:pass
                    else:raise AssertionError('Wrong current revision accepted')
                finally:workspace.detach()
                tx.rollback()
            self.record('wrong current Alembic revision refused; disposable fault transaction rolled back')
            wrong={**self.config,'port':port()}
            bad=engine_for(wrong)
            try:
                try:
                    with bad.connect():pass
                except Exception:pass
                else:raise AssertionError('Unexpected listener at negative-test port')
            finally:bad.dispose()
            self.record('unbound incorrect loopback port refused; no fallback to existing instance')
            with engine.connect() as conn,conn.begin():
                try:identity(conn,{**self.config,'system_id':'0'})
                except AssertionError:pass
                else:raise AssertionError('Wrong cluster identity accepted')
            self.record('incorrect cluster system identity refused by harness')
        finally:engine.dispose()

    def live_writer(self, case):
        ready=self.root/('ready-'+uuid4().hex)
        self.verify_server()
        data=dict(config=self.config,ownership=self.ownership,mode='hold',ready=str(ready),**case)
        log=(self.root/'held-child-private.log').open('w')
        process=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--worker'],stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,stderr=log,text=True,creationflags=subprocess.CREATE_NO_WINDOW,cwd=REPO)
        request,descriptor,plans=decode_case(case)
        workspace=reopen_workspace(descriptor,request,authorizer=Policy(),caller='owned-artificial-validation')
        try:
            process.stdin.write(json.dumps(data));process.stdin.close()
            for _ in range(100):
                check(process.poll() is None,'Competing child exited early')
                if ready.exists():break
                time.sleep(.1)
            else:raise AssertionError('Competing child timeout')
            for operation in (lambda:workspace.publish(plans[0],retry=True),lambda:workspace.release_abandoned_lock()):
                try:operation()
                except WriterBusy:pass
                else:raise AssertionError('Live writer exclusion failed')
        finally:
            process.terminate();process.wait(timeout=10);log.close()
            workspace.detach()
        self.unlock(case)
        self.complete(case)
        self.record('live competing writer and lock stealing refused; confirmed dead owner explicitly released')

    def cleanup(self):
        self.owned()
        try:
            for case in self.cases:
                self.unlock(case)
                request,descriptor,_=decode_case(case)
                workspace=reopen_workspace(descriptor,request,authorizer=Policy(),caller='owned-artificial-validation')
                workspace.close()
        finally:
            self.stop()
        self.owned()
        check(not (self.data/'postmaster.pid').exists(),'Refusing running-cluster deletion')
        # No computed deletion until exact allocated absolute root/marker/identity
        # and stopped owned postmaster have all been rechecked. Never delete DBs
        # or paths supplied by a caller; this root was allocated by this process.
        with _pin_directory(self.root.parent):
            self.owned()
            shutil.rmtree(self.root)
        check(not self.root.exists(),'Owned infrastructure cleanup incomplete')
        pointer=POINTER.lstat()
        check(stat.S_ISREG(pointer.st_mode) and pointer.st_nlink==1 and not getattr(pointer,'st_file_attributes',0)&0x400
              and POINTER.read_text()==self.pointer_payload,'Private lifecycle pointer changed')
        POINTER.unlink()


def main():
    if sys.argv[1:]==['--worker']:
        try:
            result=worker(json.loads(sys.stdin.read()))
            print(json.dumps(result),flush=True)
            return 0
        except Exception as exc:
            # No raw DB/OS exceptions or private request values in output.
            print(json.dumps(dict(error=type(exc).__name__)),file=sys.stderr)
            return 2
    check(sys.argv[1:]==['--run-owned-cluster'],'Explicit owned-cluster execution flag required')
    check(os.name=='nt','Windows-only publishing validation')
    verify_reviewed_application()
    check(all((BIN/name).is_file() for name in ('initdb.exe','pg_ctl.exe','postgres.exe')),'PostgreSQL binary set missing')
    check(not POINTER.exists(),'An existing private lifecycle record requires inspection; refusing a new cluster')
    check(subprocess.run(['git','check-ignore','-q',str(POINTER)],cwd=REPO).returncode==0,'Private lifecycle record is not ignored')
    cluster=OwnedCluster()
    failure=None
    try:
        cluster.bootstrap()
        cluster.validate()
    except Exception as exc:
        failure=dict(phase=cluster.phase,error=type(exc).__name__,frames=[dict(file=Path(f.filename).name,line=f.lineno) for f in traceback.extract_tb(exc.__traceback__)][-5:])
        # Detailed evidence is private and removed only with this owned cluster.
        (cluster.root/'failure-private.log').write_text(traceback.format_exc())
    finally:
        try:cluster.cleanup()
        except Exception as exc:
            print(json.dumps(dict(cleanup='refused or incomplete',error=type(exc).__name__)),flush=True)
            return 3
    if failure:
        print(json.dumps(dict(failed=failure)),flush=True)
        return 1
    print(json.dumps(dict(passed=len(cluster.records),checks=cluster.records,cleanup='owned cluster and synthetic workspaces removed',
                         existing_service='not controlled by this harness')),flush=True)
    return 0


if __name__=='__main__':
    try:
        exit_code=main()
    except Exception as exc:
        # Even prerequisite failures must not print raw OS paths or DB details.
        print(json.dumps(dict(prerequisite_failure=type(exc).__name__)),flush=True)
        exit_code=1
    raise SystemExit(exit_code)
