"""Opt-in, read-only private object access; no ingestion or authentication."""

import hashlib
from pathlib import Path
from typing import Annotated, BinaryIO, Literal, Protocol
from uuid import UUID

from pydantic import StringConstraints, model_validator

from stylometry.contracts import Contract, Label, Sha256
from stylometry.private_filesystem import read_private_file


class StorageReference(Contract):
    object_ref: UUID
    byte_sha256: Sha256
    provenance_id: UUID
    media_type: Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9.+-]+/[A-Za-z0-9.+-]+$")] | None = None
    processing_version: Label | None = None


class PrivateObjectResolver(Protocol):
    def read(self, reference: StorageReference, *, caller: object = None) -> bytes:
        """Return verified bytes only after the supplied caller policy allows it."""
        ...

    def verify(self, reference: StorageReference, *, caller: object = None) -> bool:
        """Verify a readable object; False includes denial/unavailable/mismatch."""
        ...


class ReadAuthorizer(Protocol):
    def allows_read(self, caller: object, reference: StorageReference) -> bool:
        """External trusted policy; this layer cannot authenticate caller identity."""
        ...


class FutureObjectWriter(Protocol):
    def publish_new(self, reference: StorageReference, source: BinaryIO) -> None:
        """Future interface ONLY. Must hash-check, allocate a new UUID/version,
        refuse replacement and atomically publish bytes/catalog; not implemented.
        """
        ...


class PrivateStorageError(RuntimeError):
    """Public-safe error; do not expose internal filesystem/parser exceptions."""


class StorageAccessDenied(PrivateStorageError):
    pass


class StorageNotConfigured(PrivateStorageError):
    pass


class ObjectUnavailable(PrivateStorageError):
    pass


class ObjectIntegrityError(PrivateStorageError):
    pass


class CatalogEntry(Contract):
    reference: StorageReference
    # Relative physical location belongs ONLY in the private catalog, never DB.
    relative_path: str

    @model_validator(mode="after")
    def validate_location(self):
        if self.relative_path != f"objects/{self.reference.object_ref.hex}/payload":
            raise ValueError("Catalog location does not match opaque object layout")
        return self


class PrivateCatalog(Contract):
    schema_version: Literal["private-storage.v1"]
    entries: tuple[CatalogEntry, ...]

    @model_validator(mode="after")
    def validate_identity(self):
        ids = [entry.reference.object_ref for entry in self.entries]
        if len(ids) != len(set(ids)):
            raise ValueError("Catalog object references must be unique")
        return self


def _parse_catalog(content: bytes) -> PrivateCatalog:
    # Reject duplicate JSON keys rather than accepting last-value-wins remapping.
    import json

    def unique_keys(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate catalog key")
            result[key] = value
        return result

    data = json.loads(content.decode("utf-8"), object_pairs_hook=unique_keys)
    return PrivateCatalog.model_validate_json(json.dumps(data, allow_nan=False))


def _lookup(catalog: PrivateCatalog, reference: StorageReference) -> CatalogEntry:
    for entry in catalog.entries:
        if entry.reference.object_ref == reference.object_ref:
            if entry.reference != reference:
                raise ObjectIntegrityError("Private object metadata does not match.")
            return entry
    raise ObjectUnavailable("Private object is unavailable.")


class FilesystemObjectResolver:
    """Explicit caller policy + private catalog + contained, hash-verified reads.

    Construction performs no filesystem access. No default allow policy exists.
    The caller policy is an injected trust boundary, not implemented identity or
    authorization infrastructure. Bytes are returned only after a complete hash
    check; no path or live, unverified stream is exposed to application callers.
    """

    def __init__(self, root: Path | str | None = None, *,
                 authorizer: ReadAuthorizer | None = None,
                 max_object_bytes: int = 32 * 1024 * 1024):
        if type(max_object_bytes) is not int or max_object_bytes <= 0:
            raise PrivateStorageError("Invalid private storage limit.")
        self._root = root
        self._authorizer = authorizer
        self._max_object_bytes = max_object_bytes

    def _authorize(self, reference: StorageReference, caller: object) -> None:
        allowed = False
        try:
            if caller is not None and self._authorizer is not None:
                allowed = self._authorizer.allows_read(caller, reference) is True
        except Exception:
            pass
        if not allowed:
            raise StorageAccessDenied("Private object access denied.") from None

    def _configured_root(self) -> Path:
        if not self._root:
            raise StorageNotConfigured("Private storage is not configured.")
        try:
            root = Path(self._root)
            repository = Path(__file__).resolve().parents[2]
            if not root.is_absolute() or ".." in root.parts or root.drive.startswith("\\\\"):
                raise ValueError
            # Canonical comparison also catches Windows short-name aliases.
            # The original path is retained for no-link handle traversal below.
            canonical = root.resolve()
            if canonical.is_relative_to(repository) or repository.is_relative_to(canonical):
                raise ValueError
            return root
        except Exception:
            raise StorageNotConfigured("Private storage configuration is invalid.") from None

    def read(self, reference: StorageReference, *, caller: object = None) -> bytes:
        try:
            # Revalidate even frozen instances constructed via bypass APIs.
            if not isinstance(reference, StorageReference):
                raise ValueError
            reference = StorageReference.model_validate_json(reference.model_dump_json(warnings="error"))
        except Exception:
            raise ObjectUnavailable("Invalid private object reference.") from None
        self._authorize(reference, caller)
        root = self._configured_root()
        try:
            catalog = _parse_catalog(read_private_file(root, ("catalog.json",), 1024 * 1024))
            entry = _lookup(catalog, reference)
            content = read_private_file(root, tuple(entry.relative_path.split("/")), self._max_object_bytes)
            if hashlib.sha256(content).hexdigest() != reference.byte_sha256:
                raise ObjectIntegrityError("Private object integrity check failed.")
            return content
        except PrivateStorageError:
            raise
        except Exception:
            raise ObjectUnavailable("Private object is unavailable.") from None

    def verify(self, reference: StorageReference, *, caller: object = None) -> bool:
        try:
            self.read(reference, caller=caller)
            return True
        except PrivateStorageError:
            return False


def configured_resolver(*, authorizer: ReadAuthorizer | None = None) -> FilesystemObjectResolver:
    """Load local configuration; no research root, catalog or payload is opened."""
    from stylometry.config import private_storage_root

    try:
        return FilesystemObjectResolver(private_storage_root(), authorizer=authorizer)
    except Exception:
        raise StorageNotConfigured("Private storage configuration is unavailable.") from None
