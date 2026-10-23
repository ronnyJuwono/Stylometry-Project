"""Explicit synthetic restart capabilities. Never attach to caller-selected roots."""

from contextlib import contextmanager
from datetime import datetime, timezone
import ctypes
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from functools import wraps
from uuid import UUID

from pydantic import Field

from stylometry import contracts as c
from stylometry.private_filesystem import read_private_file
from stylometry.storage import _parse_catalog
from stylometry.synthetic_publishing import (
    SyntheticWorkspace, SyntheticPublicationError, WriterBusy, PublicationMetadata,
    PublicationLedger, _pin_directory, _regular,
)


def _unique_json(content):
    def pairs(items):
        result = {}
        for key,value in items:
            if key in result:
                raise ValueError('Ambiguous synthetic evidence')
            result[key]=value
        return result
    return json.loads(content,object_pairs_hook=pairs)


def _record(model, content):
    return model.model_validate_json(json.dumps(_unique_json(content),allow_nan=False))


class RecoveryDescriptor(c.Contract):
    """Private bearer capability. Persist only privately; never log/put in SQL/Git."""
    basename: str = Field(repr=False)
    device: int = Field(repr=False)
    inode: int = Field(repr=False)
    token: str = Field(repr=False)
    operation_id: UUID = Field(repr=False)
    manifest_sha256: c.Sha256 = Field(repr=False)
    publications: tuple[PublicationMetadata, ...] = Field(repr=False)
    max_object_bytes: int = Field(repr=False)
    created_at: c.Timestamp = Field(repr=False)

    def __str__(self):
        return '<private synthetic recovery capability>'


def _process_stamp(pid: int) -> int | None:
    """Windows creation FILETIME; None means positively absent, errors fail closed."""
    if os.name != 'nt':
        raise OSError('Unsupported recovery platform')
    from ctypes import wintypes as w
    api = ctypes.WinDLL('kernel32', use_last_error=True)
    api.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
    api.OpenProcess.restype = w.HANDLE
    api.GetProcessTimes.argtypes = [w.HANDLE, ctypes.POINTER(w.FILETIME), ctypes.POINTER(w.FILETIME), ctypes.POINTER(w.FILETIME), ctypes.POINTER(w.FILETIME)]
    api.GetExitCodeProcess.argtypes = [w.HANDLE, ctypes.POINTER(w.DWORD)]
    api.CloseHandle.argtypes = [w.HANDLE]
    handle = api.OpenProcess(0x1000, False, pid)
    if not handle:
        if ctypes.get_last_error() == 87:  # ERROR_INVALID_PARAMETER: PID absent
            return None
        raise OSError('Cannot establish synthetic lock owner')
    try:
        exit_code = w.DWORD()
        if not api.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
            raise OSError('Cannot establish synthetic process state')
        if exit_code.value != 259:  # STILL_ACTIVE
            return None
        times = [w.FILETIME() for _ in range(4)]
        if not api.GetProcessTimes(handle, *(ctypes.byref(t) for t in times)):
            raise OSError('Cannot establish synthetic lock owner')
        return times[0].dwLowDateTime + (times[0].dwHighDateTime << 32)
    finally:
        api.CloseHandle(handle)


def sanitized(method):
    @wraps(method)
    def boundary(*args, **kwargs):
        try:
            return method(*args, **kwargs)
        except SyntheticPublicationError:
            raise
        except Exception:
            raise SyntheticPublicationError('Synthetic recovery refused or incomplete.') from None
    return boundary


class RecoverableSyntheticWorkspace(SyntheticWorkspace):
    """Default context cleanup retained; detach explicitly transfers retention duty.

    Descriptor plus root marker/identity and immutable recovery record are all
    required. The descriptor is a capability, not production authentication.
    """

    @classmethod
    def create(cls, *, operation_id, manifest_sha256, publications, **kwargs):
        workspace = cls(**kwargs)
        try:
            workspace.__enter__()
            workspace._descriptor = RecoveryDescriptor(basename=workspace.root.name,
                device=workspace._identity[0], inode=workspace._identity[1],
                token=workspace._token.decode('ascii'), operation_id=operation_id,
                manifest_sha256=manifest_sha256, publications=publications,
                max_object_bytes=workspace._limit, created_at=datetime.now(timezone.utc))
            with _pin_directory(workspace.root):
                workspace._new_file(workspace.root / 'recovery.json', workspace._descriptor.model_dump_json().encode())
            return workspace
        except Exception:
            workspace.close()
            raise SyntheticPublicationError('Synthetic recovery allocation failed.') from None

    @classmethod
    def reopen(cls, descriptor: RecoveryDescriptor, *, operation_id, manifest_sha256, publications, cleanup_only=False, **kwargs):
        workspace = None
        try:
            d = RecoveryDescriptor.model_validate_json(descriptor.model_dump_json())
            if (os.name != 'nt' or not re.fullmatch(r'stylometry-synthetic-[a-z0-9_]{8}', d.basename)
                    or not re.fullmatch(r'[0-9a-f]{32}', d.token)
                    or d.operation_id != operation_id or d.manifest_sha256 != manifest_sha256
                    or d.publications != publications or d.max_object_bytes <= 0):
                raise ValueError
            workspace = cls(max_object_bytes=d.max_object_bytes, **kwargs)
            parent = Path(tempfile.gettempdir()).resolve()
            repo = Path(__file__).resolve().parents[2]
            if parent.is_relative_to(repo) or repo.is_relative_to(parent):
                raise ValueError
            workspace._root = workspace._allocated_root = parent / d.basename
            workspace._identity = (d.device, d.inode)
            workspace._token = d.token.encode('ascii')
            workspace._descriptor = d
            workspace._cleanup_only = cleanup_only
            with _pin_directory(workspace.root):
                workspace._guard(allow_closing=cleanup_only)
                saved = _record(RecoveryDescriptor,read_private_file(workspace.root, ('recovery.json',), 4*1024*1024))
                if saved != d:
                    raise ValueError
            return workspace
        except Exception:
            # Never clean up a refused attachment, even if part of it looked valid.
            raise SyntheticPublicationError('Synthetic recovery evidence refused.') from None

    @property
    def descriptor(self):
        return self._descriptor

    @sanitized
    def detach(self) -> RecoveryDescriptor:
        with _pin_directory(self.root):
            self._guard()
            descriptor = self._descriptor
        self._root = None
        return descriptor

    def _guard(self, *, allow_closing=False):
        super()._guard()
        closing = self.root / 'closing.marker'
        if closing.exists() or closing.is_symlink():
            if read_private_file(self.root, ('closing.marker',), 128) != self._token or not allow_closing:
                raise OSError('Synthetic workspace is closing')
        if hasattr(self, '_descriptor'):
            saved = _record(RecoveryDescriptor,read_private_file(self.root, ('recovery.json',), 4*1024*1024))
            if saved != self._descriptor:
                raise OSError('Synthetic recovery evidence changed')
            ledger = _record(PublicationLedger,read_private_file(self.root, ('publication-ledger.json',), 4*1024*1024))
            allowed = {p.operation_id:p for p in saved.publications}
            if any(allowed.get(r.metadata.operation_id) != r.metadata for r in ledger.records):
                raise OSError('Synthetic ledger evidence differs')
            catalog = _parse_catalog(read_private_file(self.root, ('catalog.json',), 1024*1024))
            known = {r.metadata.reference.object_ref:r.metadata.reference for r in ledger.records}
            if any(known.get(e.reference.object_ref) != e.reference for e in catalog.entries):
                raise OSError('Synthetic catalog evidence differs')

    @contextmanager
    def _exclusive(self, lock_name='writer.lock', *, _cleanup=False):
        try:
            if lock_name not in ('writer.lock', 'registration.lock', 'recovery.lock'):
                raise ValueError
            if getattr(self,'_cleanup_only',False) and not _cleanup:
                raise ValueError
            with _pin_directory(self.root):
                self._guard(allow_closing=_cleanup)
                lock = self.root / lock_name
                content = json.dumps({'pid': os.getpid(), 'stamp': _process_stamp(os.getpid()),
                    'token': self._token.decode(), 'manifest': self._descriptor.manifest_sha256}).encode()
                try:
                    self._new_file(lock, content)
                except FileExistsError:
                    raise WriterBusy('Synthetic lock exists; explicit recovery required.') from None
                identity = _regular(lock)
                try:
                    yield
                finally:
                    current = _regular(lock)
                    if (current.st_dev,current.st_ino) != (identity.st_dev,identity.st_ino):
                        raise OSError('Synthetic lock changed')
                    lock.unlink()
        except SyntheticPublicationError:
            raise
        except Exception:
            raise SyntheticPublicationError('Synthetic operation refused or incomplete.') from None

    @sanitized
    def close(self):
        if self._root is None:
            return
        if not hasattr(self,'_descriptor'):
            return super().close()
        # Prevent a cooperating writer from starting between lock release and
        # deletion. A live/stale lock prevents cleanup BEFORE any tree deletion.
        with self._exclusive('registration.lock',_cleanup=True), self._exclusive(_cleanup=True), self._exclusive('recovery.lock',_cleanup=True):
            closing = self.root / 'closing.marker'
            if not closing.exists():
                self._new_file(closing,self._token)
        super().close()

    @sanitized
    def release_abandoned_lock(self, lock_name='writer.lock'):
        """Explicit operator action; only a provably absent original PID incarnation.

        No timeout stealing. An abandoned recovery.lock itself requires private
        inspection; it is deliberately not automatically recoverable.
        """
        with self._exclusive('recovery.lock'):
            if lock_name not in ('writer.lock','registration.lock'):
                raise SyntheticPublicationError('Unsupported synthetic lock.')
            try:
                path = self.root / lock_name
                before = _regular(path)
                record = _unique_json(read_private_file(self.root, (lock_name,), 2048))
                if (set(record) != {'pid','stamp','token','manifest'}
                        or type(record['pid']) is not int or not 0 < record['pid'] <= 0xffffffff
                        or type(record['stamp']) is not int or record['stamp'] <= 0
                        or record['token'] != self._token.decode()
                        or record['manifest'] != self._descriptor.manifest_sha256):
                    raise ValueError
                if _process_stamp(record['pid']) == record['stamp']:
                    raise WriterBusy('Synthetic lock owner remains live; recovery refused.')
                after = _regular(path)
                if (before.st_dev,before.st_ino) != (after.st_dev,after.st_ino):
                    raise ValueError
                path.unlink()
            except WriterBusy:
                raise
            except Exception:
                raise SyntheticPublicationError('Abandoned lock evidence refused.') from None

    @sanitized
    def inspect_incomplete(self) -> tuple[str, ...]:
        """Return fixed categories only, never physical names/paths or contents."""
        with self._exclusive():
            categories = set()
            ledger = _record(PublicationLedger,read_private_file(self.root, ('publication-ledger.json',), 4*1024*1024))
            allowed = {p.operation_id: p for p in self._descriptor.publications}
            if any(allowed.get(r.metadata.operation_id) != r.metadata for r in ledger.records):
                raise SyntheticPublicationError('Conflicting synthetic journal.')
            references = {p.reference.object_ref: p.reference for p in self._descriptor.publications}
            catalog = _parse_catalog(read_private_file(self.root, ('catalog.json',), 1024*1024))
            if any(references.get(e.reference.object_ref) != e.reference for e in catalog.entries):
                raise SyntheticPublicationError('Conflicting synthetic catalog.')
            with _pin_directory(self.root / 'objects'):
                for entry in (self.root / 'objects').iterdir():
                    if entry.name not in {key.hex for key in references}:
                        raise SyntheticPublicationError('Unrecognized synthetic object evidence.')
            if any(r.state != 'committed' for r in ledger.records):
                categories.add('incomplete_publication')
            if any(self.root.glob('*.tmp')):
                categories.add('orphan_control_temporary')
            for p in self._descriptor.publications:
                directory = self.root / 'objects' / p.reference.object_ref.hex
                if directory.exists():
                    with _pin_directory(directory):
                        if any(directory.glob('*.tmp')):
                            categories.add('orphan_payload_temporary')
            return tuple(sorted(categories))

    @sanitized
    def publish(self, plan, *, retry=False):
        if plan.metadata not in self._descriptor.publications:
            raise SyntheticPublicationError('Synthetic manifest conflict.')
        if any(category.startswith('orphan_') for category in self.inspect_incomplete()):
            raise SyntheticPublicationError('Orphan staging evidence requires explicit private inspection.')
        with self._exclusive():
            ledger = _record(PublicationLedger,read_private_file(self.root, ('publication-ledger.json',), 4*1024*1024))
            old = next((r for r in ledger.records if r.metadata.operation_id == plan.metadata.operation_id),None)
            if old is not None and old.state != 'prepared':
                reference = plan.metadata.reference
                content = read_private_file(self.root, ('objects',reference.object_ref.hex,'payload'), self._limit)
                if hashlib.sha256(content).hexdigest() != reference.byte_sha256:
                    raise SyntheticPublicationError('Published synthetic evidence missing or corrupted.')
        return super().publish(plan, retry=retry)
