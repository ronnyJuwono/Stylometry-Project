"""Private object metadata only. No resolver implementation or file access."""

from typing import Annotated, Protocol
from uuid import UUID

from pydantic import StringConstraints

from stylometry.contracts import Contract, Label, Sha256


class StorageReference(Contract):
    object_ref: UUID
    byte_sha256: Sha256
    provenance_id: UUID
    media_type: Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9.+-]+/[A-Za-z0-9.+-]+$")] | None = None
    processing_version: Label | None = None


class PrivateObjectResolver(Protocol):
    def verify(self, reference: StorageReference) -> bool:
        """Privately resolve an authorized UUID and verify its exact byte hash.

        Implementations must authenticate access, contain paths under an approved
        private root, and never expose the physical locator to research records.
        No implementation is provided in S2B-01.
        """
        ...
