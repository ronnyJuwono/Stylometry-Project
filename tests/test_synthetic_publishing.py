"""Artificial bytes in library-created temporary roots only; no live root."""

import os
from pathlib import Path
import subprocess
from threading import Event, Thread
from uuid import uuid4

import pytest

from stylometry.storage import FilesystemObjectResolver, StorageAccessDenied
from stylometry.synthetic_publishing import (
    DuplicatePublication, PublicationPlan, PublicationState, SyntheticPublicationError,
    SyntheticWorkspace, WriterBusy,
)


class SyntheticPolicy:
    def allows_read(self, caller, reference):
        return caller == "synthetic-test"


@pytest.fixture
def workspace():
    if os.name != "nt":
        pytest.skip("Synthetic writer is intentionally Windows-only pending platform review")
    with SyntheticWorkspace(authorizer=SyntheticPolicy(), caller="synthetic-test") as store:
        yield store


def prepare(store, synthetic_bundle, *, series=None, version="synthetic.v1"):
    return store.prepare(b"ARTIFICIAL BINARY ONLY\x00\xff", series_ref=series or uuid4(),
        provenance_id=uuid4(), version=version, reproducibility=synthetic_bundle.runs[0].reproducibility)


def test_publish_verified_binary_and_no_default_allow(workspace, synthetic_bundle):
    plan = prepare(workspace, synthetic_bundle)
    ref = workspace.publish(plan)
    assert workspace.resolver().read(ref, caller="synthetic-test") == plan.content
    assert workspace.publication_receipts()[0].state == PublicationState.COMMITTED
    assert b"ARTIFICIAL BINARY" not in (workspace.root / "publication-ledger.json").read_bytes()
    with pytest.raises(StorageAccessDenied):
        FilesystemObjectResolver(workspace.root).read(ref, caller="synthetic-test")


def test_workspace_cleanup_and_no_attach_interface(synthetic_bundle):
    with SyntheticWorkspace(authorizer=SyntheticPolicy(), caller="synthetic-test") as store:
        root = store.root
        store.publish(prepare(store, synthetic_bundle))
    assert not root.exists()
    with pytest.raises(TypeError):
        SyntheticWorkspace(root=Path("synthetic-not-accepted"))


def test_denied_publishing_leaves_empty_catalog(synthetic_bundle):
    with SyntheticWorkspace() as store:
        with pytest.raises(SyntheticPublicationError):
            store.publish(prepare(store, synthetic_bundle))
        assert store.publication_receipts() == ()


def test_never_overwrite_object_or_series_version(workspace, synthetic_bundle):
    plan = prepare(workspace, synthetic_bundle)
    ref = workspace.publish(plan)
    catalog = (workspace.root / "catalog.json").read_bytes()
    with pytest.raises(DuplicatePublication):
        workspace.publish(plan)
    duplicate = prepare(workspace, synthetic_bundle, series=plan.metadata.series_ref)
    with pytest.raises(SyntheticPublicationError):
        workspace.publish(duplicate)
    assert (workspace.root / "catalog.json").read_bytes() == catalog
    assert workspace.reconcile(plan) == ref
    v2 = prepare(workspace, synthetic_bundle, series=plan.metadata.series_ref, version="synthetic.v2")
    assert workspace.publish(v2).object_ref != ref.object_ref
    assert workspace.resolver().read(ref, caller="synthetic-test") == plan.content


@pytest.mark.parametrize("phase", ["after_prepare", "before_payload_rename", "after_payload", "after_catalog"])
def test_interruption_retains_previous_entries_and_retry(workspace, synthetic_bundle, monkeypatch, phase):
    prior = prepare(workspace, synthetic_bundle)
    workspace.publish(prior)
    planned = prepare(workspace, synthetic_bundle)
    def interrupt(stage):
        if stage == phase:
            raise OSError("SYNTHETIC-PRIVATE-ERROR /not/a/research/path")
    monkeypatch.setattr(workspace, "_checkpoint", interrupt)
    with pytest.raises(SyntheticPublicationError) as error:
        workspace.publish(planned)
    assert "PRIVATE-ERROR" not in str(error.value) and "/not/" not in str(error.value)
    assert workspace.resolver().read(prior.metadata.reference, caller="synthetic-test") == prior.content
    receipts = workspace.publication_receipts()
    assert receipts[0].state == PublicationState.COMMITTED
    assert receipts[1].state != PublicationState.COMMITTED
    assert not (workspace.root / "writer.lock").exists()
    assert not tuple(workspace.root.rglob("*.tmp"))
    with pytest.raises(SyntheticPublicationError):
        workspace.publish(prepare(workspace, synthetic_bundle))
    monkeypatch.setattr(workspace, "_checkpoint", lambda stage: None)
    assert workspace.reconcile(planned) == planned.metadata.reference
    assert all(r.state == PublicationState.COMMITTED for r in workspace.publication_receipts())


def test_simultaneous_writer_is_rejected(workspace, synthetic_bundle, monkeypatch):
    started, release = Event(), Event()
    errors = []
    def checkpoint(stage):
        if stage == "after_prepare":
            started.set()
            if not release.wait(10):
                raise RuntimeError("Synthetic coordination timeout")
    monkeypatch.setattr(workspace, "_checkpoint", checkpoint)
    first, second = prepare(workspace, synthetic_bundle), prepare(workspace, synthetic_bundle)
    def publish():
        try:
            workspace.publish(first)
        except Exception as error:
            errors.append(type(error).__name__)
    thread = Thread(target=publish)
    thread.start()
    try:
        assert started.wait(10)
        with pytest.raises(WriterBusy):
            workspace.publish(second)
    finally:
        release.set()
        thread.join(timeout=10)
    assert not thread.is_alive() and not errors


def test_stale_lock_fails_closed(workspace, synthetic_bundle):
    (workspace.root / "writer.lock").write_bytes(b"SYNTHETIC STALE LOCK")
    with pytest.raises(WriterBusy):
        workspace.publish(prepare(workspace, synthetic_bundle))
    assert (workspace.root / "writer.lock").read_bytes() == b"SYNTHETIC STALE LOCK"


def test_object_hash_mismatch_is_not_repaired(workspace, synthetic_bundle):
    plan = prepare(workspace, synthetic_bundle)
    ref = workspace.publish(plan)
    payload = workspace.root / "objects" / ref.object_ref.hex / "payload"
    payload.write_bytes(b"CORRUPTED SYNTHETIC BYTES")
    with pytest.raises(SyntheticPublicationError):
        workspace.reconcile(plan)
    assert payload.read_bytes() == b"CORRUPTED SYNTHETIC BYTES"


def test_invalid_payload_and_limits(workspace, synthetic_bundle):
    plan = prepare(workspace, synthetic_bundle)
    changed = PublicationPlan.model_construct(metadata=plan.metadata, content=b"OTHER ARTIFICIAL BYTES")
    with pytest.raises(SyntheticPublicationError):
        workspace.publish(changed)
    assert workspace.publication_receipts() == ()
    with SyntheticWorkspace(max_object_bytes=1) as tiny:
        with pytest.raises(SyntheticPublicationError):
            prepare(tiny, synthetic_bundle)
    with pytest.raises(ValueError):
        workspace._atomic_control("catalog.json", b"TOO LARGE", 1)


def test_unsafe_catalog_hardlink_is_rejected(workspace, synthetic_bundle):
    os.link(workspace.root / "catalog.json", workspace.root / "synthetic-catalog-copy")
    with pytest.raises(SyntheticPublicationError):
        workspace.publish(prepare(workspace, synthetic_bundle))


def test_catalog_limit_and_existing_object_locations_fail_safely(workspace, synthetic_bundle):
    plan = prepare(workspace, synthetic_bundle)
    location = workspace.root / "objects" / plan.metadata.reference.object_ref.hex
    location.mkdir()
    with pytest.raises(DuplicatePublication):
        workspace.publish(plan)
    assert workspace.publication_receipts() == ()
    (workspace.root / "catalog.json").write_bytes(b" " * (1024 * 1024 + 1))
    with pytest.raises(SyntheticPublicationError):
        workspace.publish(prepare(workspace, synthetic_bundle))


def test_atomic_catalog_replace_failure_retains_old_catalog(workspace, synthetic_bundle, monkeypatch):
    prior = prepare(workspace, synthetic_bundle)
    workspace.publish(prior)
    original = os.replace
    old_catalog = (workspace.root / "catalog.json").read_bytes()
    def fail_catalog(source, target):
        if Path(target).name == "catalog.json":
            raise OSError("ARTIFICIAL REPLACE FAILURE")
        return original(source, target)
    monkeypatch.setattr(os, "replace", fail_catalog)
    plan = prepare(workspace, synthetic_bundle)
    with pytest.raises(SyntheticPublicationError):
        workspace.publish(plan)
    assert (workspace.root / "catalog.json").read_bytes() == old_catalog
    assert workspace.resolver().verify(prior.metadata.reference, caller="synthetic-test")
    monkeypatch.setattr(os, "replace", original)
    workspace.reconcile(plan)


def test_directory_junction_escape_is_rejected(workspace, synthetic_bundle, tmp_path):
    external = tmp_path / "artificial-target"
    external.mkdir()
    marker = external / "synthetic-marker"
    marker.write_bytes(b"ARTIFICIAL SENTINEL")
    (workspace.root / "objects").rmdir()
    result = subprocess.run(["cmd", "/c", "mklink", "/J", str(workspace.root / "objects"), str(external)],
        capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
    assert result.returncode == 0
    with pytest.raises(SyntheticPublicationError):
        workspace.publish(prepare(workspace, synthetic_bundle))
    assert marker.read_bytes() == b"ARTIFICIAL SENTINEL"
