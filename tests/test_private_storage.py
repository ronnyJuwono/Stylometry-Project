"""Artificial bytes/private catalogs in pytest temporary directories only."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
from uuid import UUID

import pytest

from stylometry import config, storage
from stylometry.storage import (
    CatalogEntry, FilesystemObjectResolver, ObjectIntegrityError, ObjectUnavailable,
    PrivateCatalog, PrivateStorageError, StorageAccessDenied, StorageNotConfigured,
    StorageReference,
)


class SyntheticPolicy:
    def allows_read(self, caller, reference):
        return caller == "synthetic-authorized-caller"


CALLER = "synthetic-authorized-caller"
CONTENT = b"SYNTHETIC OBJECT BYTES ONLY\x00\xff"


@pytest.fixture
def private_object(tmp_path):
    root = tmp_path / "private-root"
    root.mkdir()
    reference = StorageReference(object_ref=UUID(int=101),
        byte_sha256=hashlib.sha256(CONTENT).hexdigest(), provenance_id=UUID(int=102),
        media_type="application/octet-stream", processing_version="synthetic.v1")
    entry = CatalogEntry(reference=reference, relative_path=f"objects/{reference.object_ref.hex}/payload")
    path = root / entry.relative_path
    path.parent.mkdir(parents=True)
    path.write_bytes(CONTENT)
    catalog = PrivateCatalog(schema_version="private-storage.v1", entries=(entry,))
    (root / "catalog.json").write_text(catalog.model_dump_json(), encoding="utf-8")
    return root, reference, path


def resolver(root, **kwargs):
    return FilesystemObjectResolver(root, authorizer=SyntheticPolicy(), **kwargs)


def link_to(link, target, *, directory):
    try:
        link.symlink_to(target, target_is_directory=directory)
        return "symlink"
    except OSError:
        if os.name == "nt" and directory:
            result = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)],
                                    capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
            if result.returncode == 0:
                return "junction"
        pytest.skip("Host cannot create this synthetic symbolic link")


def test_verified_read_and_boolean_verify(private_object, monkeypatch):
    from sqlalchemy.engine import Engine
    monkeypatch.setattr(Engine, "connect", lambda *a, **k: pytest.fail("Storage contacted PostgreSQL"))
    root, reference, _ = private_object
    store = resolver(root)
    assert store.read(reference, caller=CALLER) == CONTENT
    assert store.verify(reference, caller=CALLER)
    assert not store.verify(reference)
    assert "SYNTHETIC OBJECT BYTES" not in (root / "catalog.json").read_text()


@pytest.mark.parametrize("caller", [None, "untrusted-synthetic-caller"])
def test_denial_happens_before_any_filesystem_access(private_object, monkeypatch, caller):
    root, reference, _ = private_object
    monkeypatch.setattr(storage, "read_private_file", lambda *a, **k: pytest.fail("Denied lookup touched disk"))
    with pytest.raises(StorageAccessDenied):
        resolver(root).read(reference, caller=caller)


def test_no_default_authorization_or_authentication(private_object):
    root, reference, _ = private_object
    with pytest.raises(StorageAccessDenied):
        FilesystemObjectResolver(root).read(reference, caller=CALLER)


def test_truthy_policy_result_does_not_authorize(private_object):
    class InvalidPolicy:
        def allows_read(self, *args):
            return "yes"
    root, reference, _ = private_object
    with pytest.raises(StorageAccessDenied):
        FilesystemObjectResolver(root, authorizer=InvalidPolicy()).read(reference, caller=CALLER)


def test_policy_errors_are_denied_and_sanitized(private_object):
    class BrokenPolicy:
        def allows_read(self, *args):
            raise RuntimeError("SYNTHETIC-SECRET /synthetic/private/locator")
    root, reference, _ = private_object
    with pytest.raises(StorageAccessDenied) as error:
        FilesystemObjectResolver(root, authorizer=BrokenPolicy()).read(reference, caller=CALLER)
    assert "SECRET" not in str(error.value) and "locator" not in str(error.value)


def test_unconfigured_and_invalid_roots(private_object):
    _, reference, _ = private_object
    repo = Path(__file__).resolve().parents[1]
    for root in (None, "relative-private-root", "\\\\synthetic-server\\share\\private", repo, repo / "private", repo.parent):
        with pytest.raises(StorageNotConfigured):
            resolver(root).read(reference, caller=CALLER)


@pytest.mark.parametrize("reference", [None, {}, "../synthetic-escape", UUID(int=101)])
def test_invalid_reference_is_safe(reference, tmp_path):
    with pytest.raises(ObjectUnavailable, match="Invalid private object reference"):
        resolver(tmp_path).read(reference, caller=CALLER)


@pytest.mark.parametrize("update", [{"byte_sha256": "invalid"}, {"object_ref": "invalid-private-identifier"}])
def test_bypassed_contract_is_revalidated(private_object, update, recwarn):
    root, reference, _ = private_object
    invalid = StorageReference.model_construct(**{**reference.model_dump(), **update})
    with pytest.raises(ObjectUnavailable):
        resolver(root).read(invalid, caller=CALLER)
    assert not recwarn


@pytest.mark.parametrize("missing", ["root", "catalog", "object", "uuid"])
def test_missing_objects(private_object, missing):
    root, reference, path = private_object
    if missing == "root":
        root = root / "nonexistent"
    elif missing == "catalog":
        (root / "catalog.json").unlink()
    elif missing == "object":
        path.unlink()
    else:
        reference = StorageReference(**{**reference.model_dump(), "object_ref": UUID(int=999)})
    with pytest.raises(ObjectUnavailable):
        resolver(root).read(reference, caller=CALLER)


def test_changed_file_and_verified_copy(private_object):
    root, reference, path = private_object
    store = resolver(root)
    copy = store.read(reference, caller=CALLER)
    path.write_bytes(b"CHANGED SYNTHETIC BYTES")
    assert copy == CONTENT
    with pytest.raises(ObjectIntegrityError):
        store.read(reference, caller=CALLER)
    assert not store.verify(reference, caller=CALLER)


@pytest.mark.parametrize("field,value", [
    ("processing_version", "synthetic.v2"), ("provenance_id", UUID(int=999)),
    ("media_type", "text/plain"), ("byte_sha256", "0" * 64),
])
def test_exact_reference_metadata_is_pinned(private_object, field, value):
    root, reference, _ = private_object
    changed = StorageReference(**{**reference.model_dump(), field: value})
    with pytest.raises(ObjectIntegrityError):
        resolver(root).read(changed, caller=CALLER)


def test_versions_use_distinct_uuids_and_keep_old_reference(private_object):
    root, original, _ = private_object
    newer = StorageReference(**{**original.model_dump(), "object_ref": UUID(int=201),
                               "processing_version": "synthetic.v2"})
    path = root / "objects" / newer.object_ref.hex / "payload"
    path.parent.mkdir()
    path.write_bytes(CONTENT)
    old_entry = CatalogEntry(reference=original, relative_path=f"objects/{original.object_ref.hex}/payload")
    new_entry = CatalogEntry(reference=newer, relative_path=f"objects/{newer.object_ref.hex}/payload")
    (root / "catalog.json").write_text(PrivateCatalog(schema_version="private-storage.v1",
        entries=(old_entry, new_entry)).model_dump_json(), encoding="utf-8")
    assert resolver(root).read(original, caller=CALLER) == CONTENT
    assert resolver(root).read(newer, caller=CALLER) == CONTENT


@pytest.mark.parametrize("location", [
    "../escape", "/synthetic/absolute", "C:/synthetic/absolute", "objects/../escape",
    "objects\\escape", "objects/payload:stream", "objects/%2e%2e/payload",
])
def test_catalog_traversal_is_rejected(private_object, location):
    root, reference, _ = private_object
    data = {"schema_version": "private-storage.v1", "entries": [
        {"reference": reference.model_dump(mode="json"), "relative_path": location}]}
    (root / "catalog.json").write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ObjectUnavailable) as error:
        resolver(root).read(reference, caller=CALLER)
    assert location not in str(error.value)


@pytest.mark.parametrize("malformation", ["invalid_json", "duplicate_key", "duplicate_uuid", "unknown_schema", "extra_field"])
def test_malformed_catalogs_fail_closed(private_object, malformation):
    root, reference, _ = private_object
    data = json.loads((root / "catalog.json").read_text())
    if malformation == "duplicate_uuid":
        data["entries"] *= 2
    elif malformation == "unknown_schema":
        data["schema_version"] = "unapproved.v2"
    elif malformation == "extra_field":
        data["text_content"] = "FORBIDDEN SYNTHETIC FIELD"
    content = json.dumps(data)
    if malformation == "invalid_json":
        content = "not-json"
    elif malformation == "duplicate_key":
        content = '{"entries": [], "entries": []}'
    (root / "catalog.json").write_text(content, encoding="utf-8")
    with pytest.raises(ObjectUnavailable):
        resolver(root).read(reference, caller=CALLER)


@pytest.mark.parametrize("kind", ["root", "ancestor", "directory", "catalog", "file"])
def test_link_escapes_are_rejected_even_with_matching_bytes(private_object, tmp_path, kind):
    root, reference, path = private_object
    if kind in ("catalog", "file"):
        source = root / "catalog.json" if kind == "catalog" else path
        target = tmp_path / ("synthetic-catalog" if kind == "catalog" else "synthetic-bytes")
        source.rename(target)
        link_to(source, target, directory=False)
    elif kind == "directory":
        source = path.parent
        target = tmp_path / "synthetic-object-dir"
        source.rename(target)
        link_to(source, target, directory=True)
    elif kind == "root":
        alias = tmp_path / "linked-root"
        link_to(alias, root, directory=True)
        root = alias
    else:
        alias = tmp_path / "linked-ancestor"
        link_to(alias, tmp_path, directory=True)
        root = alias / root.name
    with pytest.raises(ObjectUnavailable):
        resolver(root).read(reference, caller=CALLER)


def test_link_swap_between_catalog_and_payload_is_rejected(private_object, tmp_path, monkeypatch):
    root, reference, path = private_object
    reader = storage.read_private_file
    def swap_after_catalog(base, parts, limit):
        content = reader(base, parts, limit)
        if parts == ("catalog.json",):
            target = tmp_path / "synthetic-moved-object"
            path.parent.rename(target)
            link_to(path.parent, target, directory=True)
        return content
    monkeypatch.setattr(storage, "read_private_file", swap_after_catalog)
    with pytest.raises(ObjectUnavailable):
        resolver(root).read(reference, caller=CALLER)


def test_hardlinks_are_rejected(private_object, tmp_path):
    root, reference, path = private_object
    os.link(path, tmp_path / "synthetic-other-link")
    with pytest.raises(ObjectUnavailable):
        resolver(root).read(reference, caller=CALLER)


def test_limits_and_nonregular_objects(private_object):
    root, reference, path = private_object
    with pytest.raises(ObjectUnavailable):
        resolver(root, max_object_bytes=1).read(reference, caller=CALLER)
    path.unlink()
    path.mkdir()
    with pytest.raises(ObjectUnavailable):
        resolver(root).read(reference, caller=CALLER)
    for limit in (0, -1, True, "100"):
        with pytest.raises(PrivateStorageError):
            resolver(root, max_object_bytes=limit)


def test_catalog_size_limit(private_object):
    root, reference, _ = private_object
    (root / "catalog.json").write_bytes(b" " * (1024 * 1024 + 1))
    with pytest.raises(ObjectUnavailable):
        resolver(root).read(reference, caller=CALLER)


def test_catalog_requires_utf8(private_object):
    root, reference, _ = private_object
    catalog = root / "catalog.json"
    catalog.write_bytes(catalog.read_text(encoding="utf-8").encode("utf-16"))
    with pytest.raises(ObjectUnavailable):
        resolver(root).read(reference, caller=CALLER)


@pytest.mark.skipif(os.name != "nt", reason="Windows sharing-mode protection")
@pytest.mark.parametrize("target", ["catalog", "object"])
def test_windows_existing_writers_prevent_verified_reads(private_object, target):
    root, reference, path = private_object
    target_path = root / "catalog.json" if target == "catalog" else path
    with target_path.open("r+b"):
        with pytest.raises(ObjectUnavailable):
            resolver(root).read(reference, caller=CALLER)


def test_filesystem_errors_are_sanitized(private_object, monkeypatch):
    root, reference, _ = private_object
    def fail(*args):
        raise OSError("SYNTHETIC_SECRET /synthetic/physical/path")
    monkeypatch.setattr(storage, "read_private_file", fail)
    with pytest.raises(ObjectUnavailable) as error:
        resolver(root).read(reference, caller=CALLER)
    assert "SECRET" not in str(error.value) and "physical" not in str(error.value)
    assert error.value.__suppress_context__


def test_configuration_is_opt_in_and_lazy(monkeypatch, private_object):
    root, reference, _ = private_object
    monkeypatch.setattr(config, "load_dotenv", lambda *a, **k: None)
    monkeypatch.delenv("STYLOMETRY_PRIVATE_ROOT", raising=False)
    assert config.private_storage_root() is None
    monkeypatch.setenv("STYLOMETRY_PRIVATE_ROOT", str(root))
    assert config.private_storage_root() == str(root)
    assert storage.configured_resolver(authorizer=SyntheticPolicy()).read(reference, caller=CALLER) == CONTENT
    monkeypatch.setattr(storage, "read_private_file", lambda *a, **k: pytest.fail("Construction touched disk"))
    storage.configured_resolver()


def test_configuration_errors_are_sanitized(monkeypatch):
    def fail():
        raise OSError("SYNTHETIC_SECRET /synthetic/private/config")
    monkeypatch.setattr(config, "private_storage_root", fail)
    with pytest.raises(StorageNotConfigured) as error:
        storage.configured_resolver()
    assert "SECRET" not in str(error.value) and "synthetic" not in str(error.value)
    assert error.value.__suppress_context__


def test_storage_has_no_database_or_content_columns():
    from stylometry.models import Base
    assert len(Base.metadata.tables) == 15
    assert all(column.name not in ("raw_text", "cleaned_text", "content", "relative_path")
               for table in Base.metadata.tables.values() for column in table.columns)


def test_dashboard_does_not_open_private_files(monkeypatch, private_object):
    from streamlit.testing.v1 import AppTest
    root, _, _ = private_object
    monkeypatch.setenv("STYLOMETRY_PRIVATE_ROOT", str(root))
    monkeypatch.setattr(storage, "read_private_file", lambda *a, **k: pytest.fail("Startup opened private files"))
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py").run()
    assert not app.exception
