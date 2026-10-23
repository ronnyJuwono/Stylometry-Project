"""Recoverable synthetic P1 metadata registration in stylometry_test ONLY.

Filesystem publication precedes SQL. No distributed atomicity is claimed.
P2/D1 and unrepresented P1 slot status/link data stay in private planning receipts.
"""

from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID

from pydantic import model_validator
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session

from stylometry import contracts as c
from stylometry.persistence import RECORDS, load_validated_bundle, to_record
from stylometry.pipeline.inventory import SyntheticInventory
from stylometry.synthetic_publishing import PublicationMetadata, PublicationPlan, SyntheticWorkspace


class RegistrationState(StrEnum):
    PLANNED = "planned"
    FILES_READY = "files_ready"
    STAGED = "staged_in_caller_transaction"
    REGISTERED = "registered"
    NEEDS_RECONCILIATION = "needs_reconciliation"


class RegistrationError(RuntimeError):
    pass


class RegistrationRequest(c.Contract):
    synthetic_only: bool
    operation_id: UUID
    inventory: SyntheticInventory
    publications: tuple[PublicationMetadata, ...]
    reproducibility: c.Reproducibility
    created_at: c.Timestamp

    @model_validator(mode="after")
    def validate_registration(self):
        if self.synthetic_only is not True:
            raise ValueError("Synthetic registration only")
        self.inventory.as_p1_bundle()  # Explicit P1-only schema boundary.
        publications = {p.series_ref: p for p in self.publications}
        if len(publications) != len(self.publications) or set(publications) != {d.id for d in self.inventory.documents}:
            raise ValueError("Each source document requires exactly one publication")
        if (len({p.operation_id for p in self.publications}) != len(self.publications)
                or len({p.reference.object_ref for p in self.publications}) != len(self.publications)):
            raise ValueError("Publication operation/object references must be distinct")
        for document in self.inventory.documents:
            publication = publications[document.id]
            ref = publication.reference
            if (ref.object_ref != document.private_object_ref or ref.byte_sha256 != document.byte_sha256
                    or ref.provenance_id != document.provenance_id or ref.media_type != document.media_type
                    or publication.reproducibility != self.reproducibility):
                raise ValueError("Source/publication provenance or configuration mismatch")
        return self


class RegistrationReceipt(c.Contract):
    request: RegistrationRequest
    request_sha256: c.Sha256
    state: RegistrationState
    updated_at: c.Timestamp

    @model_validator(mode="after")
    def validate_request_hash(self):
        if self.request_sha256 != c.canonical_sha256(self.request.model_dump(mode="json")):
            raise ValueError("Registration receipt manifest mismatch")
        return self


def _register_rows(session: Session, inventory: SyntheticInventory):
    identity = session.execute(text("SELECT current_database(), inet_server_addr()::text")).one()
    if identity[0] != "stylometry_test" or identity[1] not in ("127.0.0.1", "127.0.0.1/32", "::1", "::1/128"):
        raise RegistrationError("Synthetic database target is not verified.")
    session.execute(text("SELECT pg_advisory_xact_lock(21302404)"))
    incoming = inventory.as_p1_bundle()
    existing = load_validated_bundle(session)
    merged = {}
    additions = []
    for name, (_, model) in RECORDS.items():
        records = {r.id: r for r in getattr(existing, name)}
        for record in getattr(incoming, name):
            if record.id in records and records[record.id] != record:
                raise RegistrationError("Existing synthetic metadata differs; no overwrite permitted.")
            if record.id not in records:
                records[record.id] = record
                additions.append(to_record(record))
        merged[name] = tuple(records.values())
    c.ResearchBundle(**merged)  # Global IDs, logical slots and closed references.
    session.add_all(additions)
    session.flush()


def register_synthetic_inventory(bind: Connection, workspace: SyntheticWorkspace,
        request: RegistrationRequest, plans: tuple[PublicationPlan, ...]) -> RegistrationReceipt:
    """Explicit opt-in, idempotent exact-reference retry. No connection on import.

    Requires a caller-owned test transaction; returns STAGED, never a durable
    REGISTERED claim. The caller must roll it back before workspace disposal.
    Reconciliation repeats object verification and graph comparison; it never
    trusts a prior 'registered' receipt after a caller transaction rollback.
    """
    try:
        if not isinstance(bind, Connection) or not bind.in_transaction():
            raise ValueError
        url = bind.engine.url
        if (url.drivername != "postgresql+psycopg" or url.database != "stylometry_test"
                or url.host not in ("127.0.0.1", "localhost", "::1") or url.query):
            raise ValueError
        request = RegistrationRequest.model_validate_json(request.model_dump_json(warnings="error"))
        if tuple(p.metadata for p in plans) != request.publications:
            raise ValueError
        fingerprint = c.canonical_sha256(request.model_dump(mode="json"))
        with workspace._exclusive("registration.lock"):
            previous_bytes = workspace._registration_bytes()
            previous = RegistrationReceipt.model_validate_json(previous_bytes) if previous_bytes else None
            if previous is not None and (previous.request_sha256 != fingerprint or previous.request != request):
                raise RegistrationError("Synthetic workspace already belongs to a different registration.")
            def save(state):
                receipt = RegistrationReceipt(request=request, request_sha256=fingerprint,
                    state=state, updated_at=datetime.now(timezone.utc))
                workspace._save_registration(receipt.model_dump_json().encode())
                return receipt
            if previous is None:
                save(RegistrationState.PLANNED)
            try:
                for plan in plans:
                    workspace.publish(plan, retry=True)
                save(RegistrationState.FILES_READY)
                with Session(bind, join_transaction_mode="create_savepoint") as session, session.begin():
                    _register_rows(session, request.inventory)
                workspace._checkpoint("after_database_commit")
                return save(RegistrationState.STAGED)
            except Exception:
                try:
                    save(RegistrationState.NEEDS_RECONCILIATION)
                except Exception:
                    pass  # Earlier receipt remains; never invent a committed outcome.
                raise RegistrationError("Synthetic registration incomplete; reconcile the same request.") from None
    except RegistrationError:
        raise
    except Exception:
        raise RegistrationError("Synthetic registration refused or incomplete; inspect private receipts.") from None


def reconcile_registration(bind: Connection, workspace: SyntheticWorkspace,
        request: RegistrationRequest, plans: tuple[PublicationPlan, ...]) -> RegistrationReceipt:
    return register_synthetic_inventory(bind, workspace, request, plans)
