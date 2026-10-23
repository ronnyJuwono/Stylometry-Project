"""Windows-only synthetic temporary publishing. Not a research import service."""

from contextlib import contextmanager, ExitStack
from datetime import datetime, timezone
from enum import StrEnum
import hashlib
import os
from pathlib import Path
import shutil
import stat
import tempfile
from typing import Literal
from uuid import UUID, uuid4

from pydantic import model_validator

from stylometry import contracts as c
from stylometry.private_filesystem import read_private_file
from stylometry.storage import (
    CatalogEntry, FilesystemObjectResolver, PrivateCatalog, ReadAuthorizer, StorageReference,
    _parse_catalog,
)


class SyntheticPublicationError(RuntimeError):
    """Fixed public messages only; underlying OS/validation errors are private."""


class WriterBusy(SyntheticPublicationError):
    pass


class DuplicatePublication(SyntheticPublicationError):
    pass


class PublicationState(StrEnum):
    PREPARED = "prepared"
    OBJECT_READY = "object_ready"
    COMMITTED = "committed"


class PublicationMetadata(c.Contract):
    synthetic_only: Literal[True]
    operation_id: UUID
    series_ref: UUID
    reference: StorageReference
    created_at: c.Timestamp
    reproducibility: c.Reproducibility

    @model_validator(mode="after")
    def require_version(self):
        if self.reference.processing_version is None:
            raise ValueError("Synthetic publication requires an explicit supplied version")
        return self


class PublicationPlan(c.Contract):
    metadata: PublicationMetadata
    content: bytes  # In memory only; never serialized into catalog/ledger/SQL.

    @model_validator(mode="after")
    def validate_hash(self):
        if hashlib.sha256(self.content).hexdigest() != self.metadata.reference.byte_sha256:
            raise ValueError("Synthetic payload hash mismatch")
        return self


class PublicationReceipt(c.Contract):
    metadata: PublicationMetadata
    state: PublicationState


class PublicationLedger(c.Contract):
    schema_version: Literal["synthetic-publication.v1"] = "synthetic-publication.v1"
    records: tuple[PublicationReceipt, ...] = ()

    @model_validator(mode="after")
    def unique_operations(self):
        for keys in (
            [r.metadata.operation_id for r in self.records],
            [r.metadata.reference.object_ref for r in self.records],
            [(r.metadata.series_ref, r.metadata.reference.processing_version) for r in self.records],
        ):
            if len(keys) != len(set(keys)):
                raise ValueError("Duplicate publication identity/version")
        return self


@contextmanager
def _pin_directory(path: Path):
    """Hold no-reparse ancestor handles without write/delete sharing on Windows."""
    if os.name != "nt":
        raise SyntheticPublicationError("Synthetic publishing is unavailable on this platform.")
    import ctypes
    from ctypes import wintypes as w
    api = ctypes.WinDLL("kernel32", use_last_error=True)
    api.CreateFileW.argtypes = [w.LPCWSTR, w.DWORD, w.DWORD, ctypes.c_void_p, w.DWORD, w.DWORD, w.HANDLE]
    api.CreateFileW.restype = w.HANDLE
    api.CloseHandle.argtypes = [w.HANDLE]
    api.GetFileInformationByHandleEx.argtypes = [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD]
    api.GetFileInformationByHandleEx.restype = w.BOOL
    api.GetDriveTypeW.argtypes = [w.LPCWSTR]
    api.GetDriveTypeW.restype = w.UINT
    class Attributes(ctypes.Structure):
        _fields_ = [("attributes", w.DWORD), ("tag", w.DWORD)]
    if not path.is_absolute() or ".." in path.parts or path.drive.startswith("\\\\") or api.GetDriveTypeW(path.anchor) != 3:
        raise OSError("Unsafe synthetic directory")
    with ExitStack() as handles:
        current = Path(path.anchor)
        for part in (None, *path.parts[1:]):
            if part is not None:
                current /= part
            handle = api.CreateFileW("\\\\?\\" + str(current), 0x80, 1, None, 3, 0x02200000, None)
            if handle == ctypes.c_void_p(-1).value:
                raise OSError("Cannot pin synthetic directory")
            handles.callback(api.CloseHandle, handle)
            info = Attributes()
            if not api.GetFileInformationByHandleEx(handle, 9, ctypes.byref(info), ctypes.sizeof(info)):
                raise OSError("Cannot inspect synthetic directory")
            if info.attributes & 0x400 or not info.attributes & 0x10:
                raise OSError("Unsafe synthetic directory")
        yield


def _regular(path: Path):
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
            or getattr(info, "st_file_attributes", 0) & 0x400):
        raise OSError("Unsafe synthetic file")
    return info


class SyntheticWorkspace:
    """Own a NEW OS temporary root. Cannot attach to caller paths or live roots.

    A supplied read policy is still required; no production allow shortcut exists.
    Context exit deletes only this owned synthetic scratch tree. Private receipts
    enable retry within its lifetime; no process-restart recovery API is provided.
    """

    def __init__(self, *, authorizer: ReadAuthorizer | None = None, caller: object = None,
                 max_object_bytes: int = 32 * 1024 * 1024):
        if type(max_object_bytes) is not int or max_object_bytes <= 0:
            raise SyntheticPublicationError("Invalid synthetic publication limit.")
        self._root = None
        self._allocated_root = None
        self._token = uuid4().hex.encode("ascii")
        self._authorizer, self._caller = authorizer, caller
        self._limit = max_object_bytes

    @property
    def root(self) -> Path:
        if self._root is None:
            raise SyntheticPublicationError("Synthetic workspace is not active.")
        return self._root

    def __enter__(self):
        if os.name != "nt" or self._root is not None:
            raise SyntheticPublicationError("Synthetic workspace creation is unavailable.")
        try:
            parent = Path(tempfile.gettempdir()).resolve()
            repo = Path(__file__).resolve().parents[2]
            if parent.is_relative_to(repo) or repo.is_relative_to(parent):
                raise ValueError
            self._root = Path(tempfile.mkdtemp(prefix="stylometry-synthetic-", dir=parent))
            self._allocated_root = self._root
            self._identity = (self._root.stat().st_dev, self._root.stat().st_ino)
            with _pin_directory(self.root):
                (self.root / "objects").mkdir()
                self._new_file(self.root / "synthetic.marker", self._token)
                self._new_file(self.root / "catalog.json", PrivateCatalog(schema_version="private-storage.v1", entries=()).model_dump_json().encode())
                self._new_file(self.root / "publication-ledger.json", PublicationLedger().model_dump_json().encode())
            return self
        except Exception:
            try:
                self.close()
            except Exception:
                pass
            raise SyntheticPublicationError("Synthetic workspace creation failed.") from None

    def __exit__(self, *args):
        self.close()

    def close(self):
        if self._root is None:
            return
        root = self._root
        # Never recursively delete a changed/replaced/computed external target.
        try:
            info = root.lstat()
            if (root != self._allocated_root or root.resolve() != self._allocated_root
                    or (info.st_dev, info.st_ino) != self._identity
                    or getattr(info, "st_file_attributes", 0) & 0x400):
                raise ValueError
            shutil.rmtree(root)
        except Exception:
            raise SyntheticPublicationError("Synthetic workspace cleanup failed.") from None
        self._root = None

    @staticmethod
    def _new_file(path: Path, content: bytes):
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_BINARY, 0o600)
        with os.fdopen(fd, "wb") as handle:
            info = os.fstat(handle.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise OSError("Unsafe synthetic file")
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())

    def _guard(self):
        info = self.root.lstat()
        if (self.root != self._allocated_root or (info.st_dev, info.st_ino) != self._identity
                or read_private_file(self.root, ("synthetic.marker",), 128) != self._token):
            raise OSError("Unrecognized synthetic workspace")

    @contextmanager
    def _exclusive(self, lock_name: str = "writer.lock"):
        try:
            if lock_name not in ("writer.lock", "registration.lock"):
                raise ValueError
            with _pin_directory(self.root):
                self._guard()
                lock = self.root / lock_name
                try:
                    self._new_file(lock, self._token)
                except FileExistsError:
                    raise WriterBusy("Synthetic writer is busy; reconcile stale locks privately.") from None
                identity = _regular(lock)
                try:
                    yield
                finally:
                    current = _regular(lock)
                    if (current.st_dev, current.st_ino) != (identity.st_dev, identity.st_ino):
                        raise OSError("Synthetic lock changed")
                    lock.unlink()
        except SyntheticPublicationError:
            raise
        except Exception:
            raise SyntheticPublicationError("Synthetic operation incomplete; reconcile before retry.") from None

    def _atomic_control(self, name: str, content: bytes, limit: int):
        if name not in ("catalog.json", "publication-ledger.json", "registration.json") or len(content) > limit:
            raise ValueError("Synthetic control limit exceeded")
        target = self.root / name
        if target.exists() or target.is_symlink():
            _regular(target)
        staged = self.root / (uuid4().hex + ".tmp")
        try:
            self._new_file(staged, content)
            os.replace(staged, target)  # Same-directory Windows rename; failure retains old control file.
        finally:
            if staged.exists():
                _regular(staged)
                staged.unlink()

    def _checkpoint(self, stage: str):
        """No-op fault-injection seam for synthetic interruption tests."""

    def prepare(self, content: bytes, *, series_ref: UUID, provenance_id: UUID,
                version: str, reproducibility: c.Reproducibility,
                media_type: str = "application/octet-stream") -> PublicationPlan:
        try:
            if type(content) is not bytes or len(content) > self._limit:
                raise ValueError
            return PublicationPlan(metadata=PublicationMetadata(synthetic_only=True,
                operation_id=uuid4(), series_ref=series_ref, created_at=datetime.now(timezone.utc),
                reproducibility=reproducibility, reference=StorageReference(object_ref=uuid4(),
                    byte_sha256=hashlib.sha256(content).hexdigest(), provenance_id=provenance_id,
                    media_type=media_type, processing_version=version)), content=content)
        except Exception:
            raise SyntheticPublicationError("Invalid synthetic publication request.") from None

    def resolver(self) -> FilesystemObjectResolver:
        return FilesystemObjectResolver(self.root, authorizer=self._authorizer, max_object_bytes=self._limit)

    def publish(self, plan: PublicationPlan, *, retry: bool = False) -> StorageReference:
        try:
            metadata = PublicationMetadata.model_validate_json(plan.metadata.model_dump_json(warnings="error"))
            plan = PublicationPlan(metadata=metadata, content=plan.content)
            if len(plan.content) > self._limit:
                raise ValueError
            self.resolver()._authorize(plan.metadata.reference, self._caller)
        except Exception:
            raise SyntheticPublicationError("Synthetic publication denied or invalid.") from None
        with self._exclusive():
            ledger = PublicationLedger.model_validate_json(read_private_file(self.root, ("publication-ledger.json",), 4 * 1024 * 1024))
            catalog = _parse_catalog(read_private_file(self.root, ("catalog.json",), 1024 * 1024))
            old = next((r for r in ledger.records if r.metadata.operation_id == plan.metadata.operation_id), None)
            if old is not None:
                if not retry or old.metadata != plan.metadata:
                    raise DuplicatePublication("Synthetic operation already exists or differs.")
                if old.state == PublicationState.COMMITTED:
                    self.resolver().read(plan.metadata.reference, caller=self._caller)
                    return plan.metadata.reference
            elif any(r.state != PublicationState.COMMITTED for r in ledger.records):
                raise SyntheticPublicationError("Reconcile pending synthetic publication first.")
            records = list(ledger.records)
            if old is None:
                old = PublicationReceipt(metadata=plan.metadata, state=PublicationState.PREPARED)
                records.append(old)
            # Revalidates unique UUIDs and (logical series, supplied version).
            updated = PublicationLedger(records=tuple(records))
            reference = plan.metadata.reference
            if old.state == PublicationState.PREPARED and len(records) > len(ledger.records) and (self.root / "objects" / reference.object_ref.hex).exists():
                raise DuplicatePublication("Synthetic object location already exists.")
            entry = CatalogEntry(reference=reference, relative_path=f"objects/{reference.object_ref.hex}/payload")
            existing = next((e for e in catalog.entries if e.reference.object_ref == reference.object_ref), None)
            if existing is not None and existing != entry:
                raise SyntheticPublicationError("Catalog/reference conflict; reconciliation required.")
            next_catalog = PrivateCatalog(schema_version="private-storage.v1",
                entries=catalog.entries if existing else (*catalog.entries, entry))
            encoded = next_catalog.model_dump_json().encode()
            if len(encoded) > 1024 * 1024:
                raise SyntheticPublicationError("Synthetic catalog limit exceeded.")
            def state(value):
                receipts = tuple(PublicationReceipt(metadata=r.metadata,
                    state=value if r.metadata.operation_id == plan.metadata.operation_id else r.state)
                    for r in updated.records)
                self._atomic_control("publication-ledger.json", PublicationLedger(records=receipts).model_dump_json().encode(), 4 * 1024 * 1024)
            state(old.state)
            self._checkpoint("after_prepare")
            directory = self.root / "objects" / reference.object_ref.hex
            with _pin_directory(self.root / "objects"):
                if not directory.exists():
                    directory.mkdir()
                with _pin_directory(directory):
                    payload = directory / "payload"
                    if existing is None and not payload.exists():
                        staged = directory / (uuid4().hex + ".tmp")
                        try:
                            self._new_file(staged, plan.content)
                            self._checkpoint("before_payload_rename")
                            os.rename(staged, payload)  # Windows refuses an existing destination.
                        finally:
                            if staged.exists():
                                _regular(staged)
                                staged.unlink()
                    if hashlib.sha256(read_private_file(self.root, tuple(entry.relative_path.split("/")), self._limit)).hexdigest() != reference.byte_sha256:
                        raise SyntheticPublicationError("Synthetic object integrity check failed.")
            state(PublicationState.OBJECT_READY)
            self._checkpoint("after_payload")
            if existing is None:
                self._atomic_control("catalog.json", encoded, 1024 * 1024)
            self._checkpoint("after_catalog")
            self.resolver().read(reference, caller=self._caller)
            state(PublicationState.COMMITTED)
            return reference

    def reconcile(self, plan: PublicationPlan) -> StorageReference:
        return self.publish(plan, retry=True)

    def publication_receipts(self) -> tuple[PublicationReceipt, ...]:
        with self._exclusive():
            return PublicationLedger.model_validate_json(read_private_file(self.root, ("publication-ledger.json",), 4 * 1024 * 1024)).records

    def _registration_bytes(self) -> bytes | None:
        with self._exclusive():
            target = self.root / "registration.json"
            if not target.exists() and not target.is_symlink():
                return None
            return read_private_file(self.root, ("registration.json",), 4 * 1024 * 1024)

    def _save_registration(self, content: bytes):
        with self._exclusive():
            self._atomic_control("registration.json", content, 4 * 1024 * 1024)
