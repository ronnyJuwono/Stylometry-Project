"""Harness guard regressions: temporary Git/filesystem evidence, no PostgreSQL."""

import copy
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.fixture
def harness():
    path = Path(__file__).resolve().parents[1] / 'tools' / 'validate_s2c03_durability.py'
    spec = importlib.util.spec_from_file_location('durability_harness_tests', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def git(repo, *args):
    return subprocess.check_output(['git', *args], cwd=repo, stderr=subprocess.PIPE).decode().strip()


@pytest.fixture
def reviewed_repo(tmp_path, harness):
    repo = tmp_path / 'repo'
    repo.mkdir()
    git(repo, 'init', '-q')
    git(repo, 'config', 'user.name', 'Synthetic Guard Test')
    git(repo, 'config', 'user.email', 'synthetic@example.invalid')
    git(repo, 'config', 'core.autocrlf', 'false')
    for name in ('src/stylometry/runtime.py', 'migrations/env.py', *harness.PROTECTED[2:]):
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('# artificial reviewed fixture\n')
    git(repo, 'add', '.')
    git(repo, 'commit', '-qm', 'artificial reviewed baseline')
    return repo, git(repo, 'rev-parse', 'HEAD')


def test_later_evidence_commits_are_reexecutable(harness, reviewed_repo):
    repo, reviewed = reviewed_repo
    for name in ('docs/report.md', 'tools/harness.py'):
        path = repo / name
        path.parent.mkdir(exist_ok=True)
        path.write_text('artificial evidence only\n')
        git(repo, 'add', name)
        git(repo, 'commit', '-qm', 'later evidence')
        harness.verify_reviewed_application(repo, reviewed)


@pytest.mark.parametrize('state', ['unstaged', 'staged', 'committed', 'assume-unchanged', 'skip-worktree'])
@pytest.mark.parametrize('name', ['src/stylometry/runtime.py', 'migrations/env.py', 'pyproject.toml', 'uv.lock'])
def test_runtime_changes_refused(harness, reviewed_repo, state, name):
    repo, reviewed = reviewed_repo
    if state in ('assume-unchanged', 'skip-worktree'):
        git(repo, 'update-index', '--' + state, name)
    (repo / name).write_text('# artificial unreviewed change\n')
    if state in ('staged', 'committed'):
        git(repo, 'add', name)
    if state == 'committed':
        git(repo, 'commit', '-qm', 'unreviewed runtime')
    with pytest.raises(AssertionError):
        harness.verify_reviewed_application(repo, reviewed)


def test_staged_runtime_change_refused_even_when_worktree_restored(harness, reviewed_repo):
    repo, reviewed = reviewed_repo
    path = repo / 'app.py'
    original = path.read_bytes()
    path.write_text('# staged unreviewed code\n')
    git(repo, 'add', 'app.py')
    path.write_bytes(original)
    with pytest.raises(AssertionError):
        harness.verify_reviewed_application(repo, reviewed)


def test_untracked_ignored_runtime_refused(harness, reviewed_repo):
    repo, reviewed = reviewed_repo
    (repo / '.gitignore').write_text('unreviewed.py\n')
    (repo / 'src/stylometry/unreviewed.py').write_text('# artificial extra module\n')
    with pytest.raises(AssertionError):
        harness.verify_reviewed_application(repo, reviewed)


def test_missing_reviewed_ancestor_refused(harness, reviewed_repo):
    repo, _ = reviewed_repo
    with pytest.raises(AssertionError):
        harness.verify_reviewed_application(repo, '0' * 40)


@pytest.fixture
def owned_evidence(tmp_path, monkeypatch, harness):
    repo, allocation = tmp_path / 'repo', tmp_path / 'allocation'
    repo.mkdir()
    allocation.mkdir()
    monkeypatch.setattr(harness, 'REPO', repo)
    monkeypatch.setattr(harness, 'POINTER', repo / '.env.s2c03b-owned-location')
    monkeypatch.setattr(harness.tempfile, 'gettempdir', lambda: str(allocation))
    # Allocates only synthetic files; no initdb or server lifecycle method runs.
    cluster = harness.OwnedCluster()
    cluster.data.mkdir()
    info = cluster.data.stat()
    cluster.data_identity = (info.st_dev, info.st_ino)
    cluster.system_id = '123456789'
    cluster.save_private()
    (cluster.data / 'postmaster.pid').write_text(
        f'123\n{cluster.data}\n0\n{cluster.port}\n\n127.0.0.1\n')
    data = dict(config=cluster.config, ownership=cluster.ownership, mode='schema')
    return cluster, data


def test_valid_private_evidence_reaches_worker_without_database(harness, owned_evidence, monkeypatch):
    _, data = owned_evidence
    monkeypatch.setattr(harness, 'owned_worker', lambda received, config: (received['mode'], config))
    assert harness.worker(data) == ('schema', data['config'])


@pytest.mark.parametrize('damage', [
    'missing-capability', 'wrong-capability', 'missing-pointer', 'corrupt-pointer', 'wrong-parent', 'wrong-parent-stamp',
    'missing-record', 'corrupt-record', 'wrong-root', 'wrong-directory', 'replaced-directory',
    'wrong-marker', 'wrong-record-token', 'wrong-system-id', 'wrong-port', 'reserved-port',
    'wrong-host', 'wrong-database', 'corrupt-postmaster', 'wrong-postmaster-port',
])
def test_worker_rejects_bad_evidence_before_engine(harness, owned_evidence, monkeypatch, damage):
    cluster, original = owned_evidence
    data = copy.deepcopy(original)
    record_path = cluster.root / 'instance-private.json'
    record = json.loads(record_path.read_text())
    if damage == 'missing-capability':
        data.pop('ownership')
    elif damage == 'wrong-capability':
        data['ownership']['token'] = 'incorrect artificial capability'
    elif damage == 'missing-pointer':
        harness.POINTER.unlink()
    elif damage == 'corrupt-pointer':
        harness.POINTER.write_text('{')
    elif damage == 'wrong-parent':
        pointer = json.loads(harness.POINTER.read_text())
        pointer['pid'] = -1
        harness.POINTER.write_text(json.dumps(pointer))
    elif damage == 'wrong-parent-stamp':
        pointer = json.loads(harness.POINTER.read_text())
        pointer['process_stamp'] = -1
        harness.POINTER.write_text(json.dumps(pointer))
    elif damage == 'missing-record':
        record_path.unlink()
    elif damage == 'corrupt-record':
        record_path.write_text('{')
    elif damage == 'wrong-root':
        record['identity'] = [-1, -1]
    elif damage == 'wrong-directory':
        record['data_directory'] = str(cluster.root / 'other')
    elif damage == 'replaced-directory':
        record['data_identity'] = [-1, -1]
    elif damage == 'wrong-marker':
        (cluster.root / 'owner.marker').write_text('incorrect artificial marker')
    elif damage == 'wrong-record-token':
        record['token'] = 'incorrect artificial capability'
    elif damage in ('wrong-system-id', 'wrong-port', 'reserved-port', 'wrong-host', 'wrong-database'):
        key, value = {
            'wrong-system-id': ('system_id', '987654321'), 'wrong-port': ('port', 1),
            'reserved-port': ('port', 5432), 'wrong-host': ('host', '192.0.2.1'),
            'wrong-database': ('database', 'stylometry_dev'),
        }[damage]
        data['config'][key] = value
        # Even internally consistent private evidence may not authorize these targets.
        if damage in ('reserved-port', 'wrong-host', 'wrong-database'):
            record[key] = value
    elif damage == 'corrupt-postmaster':
        (cluster.data / 'postmaster.pid').write_text('incomplete')
    elif damage == 'wrong-postmaster-port':
        path = cluster.data / 'postmaster.pid'
        path.write_text(path.read_text().replace(f'\n{cluster.port}\n', '\n5432\n'))
    if damage not in ('missing-record', 'corrupt-record'):
        record_path.write_text(json.dumps(record))

    def forbidden_engine(*args, **kwargs):
        pytest.fail('Rejected worker evidence reached database engine creation')

    monkeypatch.setattr(harness, 'engine_for', forbidden_engine)
    with pytest.raises((AssertionError, OSError, ValueError, KeyError)):
        harness.worker(data)


def test_direct_worker_cli_refuses_without_evidence(harness, monkeypatch, capsys):
    monkeypatch.setattr(sys, 'argv', [str(harness.__file__), '--worker'])
    monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps({'config': {'port': 5432}, 'mode': 'schema'})))
    monkeypatch.setattr(harness, 'engine_for', lambda *a, **kw: pytest.fail('Database access attempted'))
    assert harness.main() == 2
    captured = capsys.readouterr()
    assert captured.out == ''
    assert json.loads(captured.err) == {'error': 'AssertionError'}


def test_direct_worker_process_refuses_without_evidence(harness):
    result = subprocess.run([sys.executable, str(harness.__file__), '--worker'], input='{}',
                            capture_output=True, text=True, timeout=15,
                            creationflags=subprocess.CREATE_NO_WINDOW)
    assert result.returncode == 2
    assert result.stdout == ''
    assert json.loads(result.stderr) == {'error': 'AssertionError'}


def test_private_evidence_survives_real_child_isolation(harness, owned_evidence):
    cluster, data = owned_evidence
    # Windows .venv redirectors can be the immediate parent. Pin the harness's
    # live PID AND creation time instead of assuming os.getppid() is the harness.
    code = '''
import importlib.util, json, sys
from pathlib import Path
spec = importlib.util.spec_from_file_location('isolated_harness', sys.argv[1])
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)
h.REPO = Path(sys.argv[2])
h.POINTER = h.REPO / '.env.s2c03b-owned-location'
h.tempfile.gettempdir = lambda: sys.argv[3]
with h.verified_worker_config(json.loads(sys.stdin.read())):
    print('owned evidence accepted')
'''
    result = subprocess.run([sys.executable, '-c', code, str(harness.__file__), str(harness.REPO),
                             str(cluster.root.parent)], input=json.dumps(data), text=True, capture_output=True,
                            timeout=15, creationflags=subprocess.CREATE_NO_WINDOW)
    assert result.returncode == 0
    assert result.stdout.strip() == 'owned evidence accepted'
    assert result.stderr == ''


@pytest.mark.parametrize('field,value', [('system', '0'), ('database', 'stylometry_dev'), ('port', 5432)])
def test_connected_identity_mismatch_refuses_before_work(harness, owned_evidence, field, value):
    _, data = owned_evidence
    config = data['config']
    row = [harness.DATABASE, '127.0.0.1', config['port'], '180006', config['system_id']]
    if field in ('database', 'port', 'system'):
        row[{'database': 0, 'port': 2, 'system': 4}[field]] = value

    class Connection:
        class connection:
            class driver_connection:
                autocommit = False

        def execute(self, statement):
            class Result:
                def one(self):
                    return tuple(row)
            return Result()

    with pytest.raises(AssertionError):
        harness.identity(Connection(), config)
