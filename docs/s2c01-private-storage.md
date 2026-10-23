# S2C-01 private research filesystem foundation

Base: `main` / `origin/main` at
`034b6c73e4cbf1493658166cdb47784360e02a17`, verified synchronized with a clean
working tree before creating `feature/s2c01-private-storage`. Runtime inputs for
validation are entirely artificial bytes/catalogs created in pytest temporary
directories. No private root was provisioned, no real research directory was
scanned and no student documents, identifiers or writing were read.

## Architecture and public interfaces

PostgreSQL remains the unchanged S2B metadata store. S2A contracts, all 15 ORM
tables, migrations, scientific methods and the four-module/nine-stage dashboard
are unchanged. No content/path columns, database writes or connections are added
by storage. Original documents, extracted bytes, cleaned bytes and artifacts use
the same opaque storage abstraction; this does not implement their production.

| Component | Responsibility |
|---|---|
| `StorageReference` | Existing UUID, exact SHA-256, provenance UUID, optional media type and processing-version label; unchanged fields |
| `ReadAuthorizer` | External trusted policy seam; checks the supplied caller/reference before filesystem access |
| `PrivateCatalog`, `CatalogEntry` | Frozen, strict private mapping from UUID to one canonical relative location and exact reference metadata |
| `_lookup` | Locate the UUID and compare all pinned metadata; never select a latest version |
| `private_filesystem.read_private_file` | Internal handle/descriptor-based bounded read, rejecting unsafe filesystem entries |
| `FilesystemObjectResolver.read` | Authorize, validate configuration/catalog/reference, read and SHA-256-check all bytes before returning a verified copy |
| `FilesystemObjectResolver.verify` | Same authorized read/hash check; False on denial, unavailable object, invalid configuration or integrity error |
| `configured_resolver` | Explicit local configuration factory; does not open the root, catalog or object |
| `FutureObjectWriter` | Protocol only for a later reviewed import/publish service; no implementation |

There is no public physical-path lookup, unverified stream or default allow policy.
The supported application boundary is the resolver; callers must not bypass it
by using internal file helpers. File-category semantics and conversion from
individual S2A event/derivation versions must be reviewed in S2C-02 rather than
guessed here. This stage does not count words, clean text or execute QC.

## Private configuration and catalog convention

Set `STYLOMETRY_PRIVATE_ROOT` through the existing local ignored `.env` or process
environment. Environment values win. Configuration reads only the project-local
`.env`, never a parent file. The root must be an absolute local directory outside
the repository; roots overlapping/containing the repository, relative paths,
parent components and UNC/device network locations are rejected. Canonical root
comparison also handles filesystem aliases; no directory is created. An unset
root remains unconfigured. No actual storage root value is recorded in this report.

The root contains one UTF-8 JSON `catalog.json` and an `objects` directory. The
catalog schema is `private-storage.v1`, with `entries` containing:

| Field | Rule |
|---|---|
| `reference` | Full validated `StorageReference`; UUID, digest and provenance required, optional media/version preserved exactly |
| `relative_path` | Exactly `objects/<object_ref.hex>/payload`, with 32 lowercase UUID hex digits |

No original filename, student identifier, text content, absolute path or URL is
part of that convention. JSON duplicate keys, repeated UUIDs, unknown fields or
schema versions and arbitrary paths are rejected. Catalog size is capped at
1 MiB. Catalog bytes are structurally validated, not cryptographically signed;
the trusted caller's reference independently pins object bytes and metadata.
UUIDs do not prove anonymization. Catalog metadata itself remains private.

Each version has a separate UUID/directory/reference. Two supplied versions can
be retrieved independently; a catalog cannot silently remap the same UUID to a
new hash, version, provenance or media type for an existing trusted reference.
Version labels do not constitute a scientific cleaning method, and no automatic
mapping or latest-version lookup is introduced. Underlying files are not made
immutable by this read-only code: external changes are detected at the next
verified read. Actual append-only publishing/catalog transactions remain future work.

## Containment and integrity controls

All path components are checked, not just a string prefix. Catalog paths have
the fixed UUID layout and cannot contain traversal, drive overrides, alternate
data streams, separators, absolute paths or percent-encoded escape components.

On Windows the reader opens each ancestor directory and final file using native
`CreateFileW` handles with `OPEN_REPARSE_POINT`, checks attributes and file type,
and rejects every reparse point (including symlinks, junctions and other link-like
providers). Ancestor/file handles remain open without write/delete sharing while
the bytes are read, preventing replacement and ordinary concurrent writers.
The target must be a regular disk file with exactly one hardlink. Existing writers
cause a safe read failure rather than bypassing sharing protection.
Windows roots must use a fixed local drive; mapped remote/removable/unknown drive
types are refused. This is not a guarantee about a privileged administrator's
virtual disk or mount configuration.

The POSIX implementation walks directory descriptors with `O_NOFOLLOW` and
`O_DIRECTORY`, opens nonblocking before checking file type, and rejects symlinks,
nonregular files and multiple hardlinks. It compares file metadata before/after
read. POSIX directory renames/mount manipulation by privileged or filesystem-write
actors are outside this layer's isolation guarantee; private root ACLs remain
essential. The POSIX branch has not been executed on this Windows validation host.

All payloads are bounded (default 32 MiB per object, explicitly configurable by
trusted constructor callers), read completely, checked with SHA-256 against the
caller-pinned digest, and returned as a bytes copy. Changes after return cannot
change that copy; a subsequent read checks again. No normalization/decoding or
scientific duplicate comparison is performed. Larger files/streaming require a
later reviewed design, not an unverified stream or silent truncation.

## Access and failure boundaries

The default is deny. A non-None caller and explicit external policy result of
the boolean `True` are required; false/truthy nonboolean results and policy errors
deny. Policy execution precedes root/catalog lookup, and `verify` also enforces
it. The policy seam is not authentication or an implemented production access
system: caller identity/session validation and entitlement logic must be supplied
and reviewed by the host application. A malicious supplied policy is trusted code,
not something this library can independently authenticate or secure.

Public errors identify denial, unconfigured storage, unavailable/invalid objects
or integrity mismatch using fixed messages. Filesystem paths, catalog/parser
payloads, credentials and internal exception chains are suppressed. No logging
is added. Do not log private arguments, catalog entries, tracebacks with captured
locals, or returned bytes. Authorized callers can retain/disclose bytes; the
resolver does not implement memory zeroization, encryption or downstream privacy.

## Future write/import and operational requirements

`FutureObjectWriter.publish_new(reference, source)` is a protocol, not callable
ingestion. A later authorized implementation must verify exact bytes, allocate
new UUIDs/versions, refuse overwrites, publish catalog/data atomically, preserve
provenance and coordinate database references, recovery and audit records. None
of those writes, catalog updates or actual file imports are implemented here.

Before real data: approve anonymization, consent/access, root ownership and ACLs,
authenticated caller policy, allowed media/size limits, encryption/retention and
operational logging rules. Keep filesystem/catalog writers separate from reader
roles. Administrative actors, malicious mount changes, broken OS semantics and
untrusted executables on the same machine are not defeated by a Python library.
No cloud, network-share, synchronized/reparse-backed root or production deployment
is approved by this stage. Failures can reduce availability rather than weaken checks.

Back up the private catalog, every UUID payload/version, referenced configurations
and database metadata as a coordinated private checkpoint. Preserve exact bytes,
UUIDs, versions, provenance and digests; do not rename objects to student names or
reuse identifiers. Encrypt backups, apply equivalent restricted access/retention
and keep keys separately. Restore to an approved isolated root, restore metadata
consistently, verify every referenced digest and missing object before enabling
reads, and test recovery with synthetic data first. Never place archives, catalogs,
database dumps or research files in Git. No backup/restore machinery is implemented.

## Files and validation

| File | Change |
|---|---|
| `src/stylometry/storage.py` | Extended resolver/protocol, private catalog validation, default-deny policy seam, integrity/version checks and safe public failures |
| `src/stylometry/private_filesystem.py` | New internal Windows/POSIX bounded no-link reader |
| `src/stylometry/config.py` | Lazy private-root environment setting |
| `tests/test_private_storage.py` | Temporary synthetic object/catalog security and configuration tests |
| `.env.example` | Blank optional storage-root setting; no real configuration |
| `.gitignore` | Additional catalog/object-tree safeguards |
| `README.md`, this report | Configuration, architecture, access, limits and review handoff |

Full test command loads the existing ignored test configuration into the process
then runs `python -m pytest`. Result: **143 passed, 2 skipped, 0 failed** out of
145 cases. All **93 pre-existing tests pass**, including **33 live PostgreSQL
integration cases**. Of 52 new storage cases, 50 pass and two file-symlink cases
(catalog and payload symlinks) are skipped because this Windows account cannot
create file symbolic links. Directory symlink/junction escape scenarios, root
and ancestor links, a link swap between catalog and payload, hardlinks and native
Windows writer-sharing conflicts executed successfully. Symlink creation failure
uses junctions for directory-link tests rather than skipping those tests. The
untested file-symlink cases must run on a suitably permitted host before actual
research ingestion; no global privilege or Developer Mode setting was changed.

The new dashboard regression passes with a synthetic private-root setting and
fails if startup attempts a private file read. Existing navigation tests cover
all four modules and nine not-started stages. A separate hidden temporary
loopback Streamlit server returned **HTTP 200** and was stopped. After the suite,
a fresh isolated test database connection passed the empty-target guard and
confirmed zero public tables. `git diff --check` passes. No dependencies changed.

The new tests never use a configured research root: they use only temporary
directories and artificial binary contents. Existing PostgreSQL tests use only
the isolated `stylometry_test` database; their test-only schema/rows roll back.
No Alembic migration command is applied to the development database and no
migration source is altered. The existing database schema remains metadata-only.

The user has separately authorized one review commit and publication of only
`feature/s2c01-private-storage` after full tests and explicit staged-content
safety checks. Stop at **Approval Gate S2C-01** after publication; no merge,
live research-root configuration or real-data ingestion is authorized.
The next stage is review of this foundation and separate
S2C-02 scope for identity/policy integration, catalog provisioning and a controlled
synthetic publish/import workflow before any actual research-data authorization.
