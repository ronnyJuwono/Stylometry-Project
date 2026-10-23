# S2C-02 implementation — Approval Gate

Baseline `main` and `origin/main` were clean and synchronized at
`9113e21606438dbee965721be5a5a33515e52326` before creating
`feature/s2c02-research-pipeline`. The subsequent publication request authorizes
one reviewed feature-branch commit and push for independent ChatGPT code review.
Merge, live-root configuration and real-data access remain unauthorized.

## Implemented versus designed

Functional: separate strict synthetic inventory planning; summaries/completeness;
controlled temporary publication/retrieval; append-only version identity checks;
recoverable artificial P1 metadata staging in isolated PostgreSQL; independent
synthetic demo; and synchronous synthetic inventory runner/history.

Interfaces/design only: scientific processing, analysis, production identity and
authorization, persistent research importing, multi-study SQL ownership/migrations,
durable experiment management/comparison and permanent filesystem/SQL coordination.
There are no new ORM models, migrations, statistics, feature values or completed
scientific stages. Existing 15-table schema, S2A contracts, method documentation,
four dashboard modules and nine stages remain unchanged.

New source files: `pipeline/__init__.py`, `inventory.py`, `interfaces.py`,
`registration.py`, `demo.py`; `analysis/__init__.py`, `interfaces.py`;
`experiments/__init__.py`, `configurations.py`, `results.py`, `runner.py`; and
`synthetic_publishing.py`. New tests: `test_research_pipeline.py`,
`test_synthetic_publishing.py`, `test_research_registration.py`. Documentation:
this report, [multi-study proposal](multi-study-data-architecture.md),
[processing design](research-processing-architecture.md), plus README updates.
Approved modules remain in their existing locations; no dependencies are added.

## Synthetic inventory

The independent planning model records explicit study/corpus/version, provenance,
individual/group pseudonyms, writing units, supplied slot definitions, source
document metadata and present/missing/unresolved declarations. Completeness means
all declared unit/slot combinations have an explicit receipt; undeclared slots
are reported separately and never invented as missing submissions.

Duplicate `(unit_id, slot_code)` keys are rejected. Equal hashes, a source shared
by several task mappings, and two different documents with equal byte hashes are
not scientific duplicate-text decisions. No word counting or QC selection occurs.
P1 retains T01–T05 and individual writer/task semantics; P2 and D1 retain their
own section/submission/reference planning structures. Only a complete explicit
P1 inventory can adapt to current S2A/SQL records. Missingness, study/unit ownership
and source-slot links have no corresponding current SQL columns and remain in
the private registration receipt, pending an additive reviewed migration.

## Controlled temporary publisher

`SyntheticWorkspace` allocates its own NEW OS temporary directory. There is no
caller path, environment root, attach/resume-existing-root or file-import API.
Only explicitly supplied in-memory artificial bytes are accepted; a label cannot
mathematically prove they are synthetic, so trusted test/development use is an
essential boundary. It never scans existing research directories. The synthetic
policy/capability used by tests/demo is confined to that fresh scratch workspace;
the approved resolver still defaults to deny, and production authorization is
not implemented or bypassed.

`prepare` generates opaque object/operation UUIDs, exact SHA-256, supplied series,
provenance/version and full reproducibility evidence. Plans hold bytes only in
memory. The catalog retains the approved UUID layout. A private bounded ledger
stores metadata/states, not payloads; `(series_ref, processing_version)`, operation
and object identities must be unique. A new version receives a new object UUID.
Neither a retry nor a failed hash check overwrites existing payloads.

Publishing is Windows fixed-local-drive only. Other platforms fail before root
creation, pending review rather than using an untested writable path. Native
handles pin ancestors and reject links/reparse points; exclusive-create files,
regular-file/single-hardlink checks, fixed control filenames and UUID locations
avoid traversal and replacement through unsafe entries. The S2C-01 reader verifies
the final published object. Size limits: configurable 32 MiB default payload,
1 MiB catalog, 4 MiB publication ledger/registration receipt. These are engineering
resource limits, not scientific parameters.

Cooperating writers acquire an exclusive-create lock; simultaneous/stale-lock
attempts fail without stealing the lock. A second registration lock serializes
the workspace's single registration operation while using the publication lock
for individual catalog/receipt updates. A different registration manifest cannot
reuse that workspace. Root identity/marker/containment are checked before writes
and before recursive cleanup of the exact allocated scratch tree. No user work
is deleted or reorganized.

Publication order:

1. Validate/authorize the request and size/identity constraints under the lock.
2. Atomically record a prepared metadata receipt.
3. Exclusive-create a temporary payload, flush/fsync it, rename without replacing
   an existing payload, and verify exact bytes through no-link reads.
4. Record object-ready; build a catalog retaining all prior entries and atomically
   replace its control file using a flushed same-directory temporary file.
5. Read/hash-verify through the existing authorized resolver; record committed.

Faults leave prior catalog entries readable. Known staging files are cleaned on
handled failures; completed new payloads/receipts remain for explicit reconciliation.
Uncataloged payloads are not a success. Retry requires the identical operation,
metadata and bytes; it verifies existing payloads and either finishes the pending
catalog/receipt or confirms a historical committed reference without rewriting it.
Unexpected/corrupt objects, changed identities and unrelated pending operations
fail closed. Receipt states describe publication history, not ongoing immunity
from external file corruption; every read verifies integrity again.

Windows atomic replace and fsync do not establish a portable power-loss guarantee
or distributed transaction. No directory durability, OS-crash recovery, malicious
same-account writer isolation or network-filesystem semantics are claimed. An
abrupt process death can leave a stale lock, orphan or control file requiring
private inspection; the API does not silently break locks, attach to arbitrary
roots or repair corrupt objects. Reconciliation is supported within the owned
workspace lifetime; process-restart recovery requires separate design. Context
exit safely deletes this synthetic scratch tree, so it is not durable research
storage. POSIX read support remains as reviewed previously; publishing is not
enabled there. No global privilege/authentication/server configuration is changed.

## PostgreSQL/filesystem coordination

`RegistrationRequest` pins the complete validated inventory, publication metadata,
operation/configuration/code/environment evidence and a canonical manifest hash.
Only active caller-owned Connections to loopback `stylometry_test` are accepted;
Engine autocommit/durable registration and all development/production targets are
refused. No SQL/file operation occurs at import or Streamlit startup.

The coordinator stores a planned private receipt, publishes/verifies all source
objects, records files-ready, then stages SQL metadata under a database advisory
transaction lock and savepoint. Existing records must match exactly; the complete
merged `ResearchBundle` validates references, global IDs and logical slot uniqueness
before inserting missing records. Only current P1 provenance/corpus/writer/source/
sample columns are used. No text, fake study column, extraction, QC or experiment
run row is inserted. Supplied source status/link/unit data remains in the receipt.

Return state is **staged_in_caller_transaction**, never a durable registered claim.
The caller owns final rollback and must roll back before workspace disposal; this
foundation deliberately does not provide a permanent ingestion service. A SQL
failure rolls back the savepoint but leaves verified temporary artifacts and a
needs-reconciliation receipt. Receipt failure after SQL staging has an uncertain
outcome; the method raises and does not report success. Retry always re-verifies
files and compares actual database rows, even if an earlier receipt said staged.
If the caller rolled back, rows are restaged; identical rows are reused, different
records/slots are refused. The reserved registered state is not emitted here.

There is no two-resource atomic commit. Tests exercise SQL rollback, publication
interruptions, atomic catalog replacement failure, post-savepoint/receipt failures,
and exact-request retries. No test inventory is inserted into `stylometry_dev`.
The existing fixture creates test-only schema inside its transaction and rolls
back all tables/rows; no persistent migration is applied or migration source changed.

## Validation and next gate

Validation completed **2026-10-23 12:40 Asia/Bangkok (05:40 UTC)**. Full pytest:
**197 passed, 0 failed, 2 skipped** out of 199 collected. All 143 baseline passing
cases remain passing; all **54 new cases pass**. Both skips are the original
Windows file-symlink privilege cases (catalog and payload); no new skip was added.
All 33 existing PostgreSQL cases and the new transaction/recovery tests executed
against the isolated test fixture; two of the ten new registration-module cases
are intentionally pre-database validation checks. No skipped test is counted as
passed. Directory-junction escape, exclusive writer rejection, atomic catalog
replace failure, orphan recovery, no-overwrite/version conflicts, SQL savepoint
rollback and uncertain receipt retries passed with artificial data.

Independent `python -m stylometry.pipeline.demo` produced an artificial P1 summary:
5 expected/declared slots, 1 present, 2 missing, 2 unresolved, no undeclared slots;
publication verified; synthetic inventory execution succeeded; **0 scientific
stages executed and no PostgreSQL access**. These are demonstration inputs/counts,
not paper outcomes or actual writing measurements. The scratch root was disposed.

After the full suite a new connection passed the `stylometry_test` empty-target
guard and confirmed zero public tables, so fixture DDL and synthetic rows were
rolled back. A separate hidden temporary loopback Streamlit server returned
**HTTP 200** and was stopped. AppTest retained all four modules and nine planned
stages; the additional regression forbids new publisher/database execution at
startup. `git diff --check` passes. No live private root is configured. Approved
contracts/models/migrations/storage/persistence/UI and dependencies remain
unchanged. At the local implementation gate, the only modified tracked file was
README; new files were those listed above, and nothing had been staged, committed,
pushed or merged. Publication is a separate test- and safety-gated review step.

Synthetic P2/D1 planning and scientific
unavailability tests do not execute the proposed study methods or reproduce paper
results. No real student information, private URL/path, catalog or payload belongs
in the repository or this report.

Before S2C-03: review this synthetic-only foundation and the ownership/migration
proposal; decide durable operation/registration representation and recovery policy;
run skipped file-symlink and future publishing-platform tests on suitable hosts;
review authenticated policy, ACLs, immutable publication, audit/backup/retention
and actual method/source evidence. A reasonable next scope is a reviewed synthetic
durable-operation design and controlled catalog recovery, not real-data ingestion
or scientific calculation. Obtain separate approval for schema changes, real
access or any method implementation. Stop for independent code review at
**Approval Gate S2C-02** after the authorized feature-branch publication. No merge
or further stage is authorized.
