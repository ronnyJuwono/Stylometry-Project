# S2C-03C development migration preflight — compatibility blocker

Inspection date: **2026-10-28** (Asia/Bangkok). Approved application baseline:
`2cf0ffeec4eaf6db4ea1433b4443cb6fdc3eb828`. Local `main` and fetched
`origin/main` matched that commit, and the working tree was clean before creating
`feature/s2c03c-migration-preflight`.

**Status: development read-only preflight and private backup passed. The archive
restored successfully into disposable PostgreSQL, with metadata preserved, but
the restored constraint fingerprint differs. Migration rehearsal stopped before
any successor migration or COMMIT. Development is NOT ready for migration
approval on the strength of this report.**

The user explicitly approved retaining the private backup until they authorize
deletion. Its new local directory is outside Git, owned by the current Windows
account and protected by a DACL granting FullControl only to that account and
SYSTEM. Inheritance is disabled on the root; all retained descendants were
checked for those two access identities and absence of reparse points. The
backup, integrity manifest, source snapshot evidence and detailed diagnostic
records remain private. No backup path, credential, connection string, private
capability or metadata-row digest is published here.

## Read-only development inspection

The configured development target was checked in a **repeatable-read, read-only
transaction**. Only catalog metadata, counts and the five approved task tuples
were read. No writing contents, research storage or private source documents were
accessed. The inspection did not invoke the initialized-upgrade function on
development: that function takes ACCESS EXCLUSIVE table locks. Its read-only
identity and frozen schema-evidence components were used for inspection instead.

| Check | Observed result |
|---|---|
| Actual target identity | Database `stylometry_dev`; actual loopback address and port matched the private configuration |
| Port | 5432; observed only, no lifecycle control |
| PostgreSQL | 18.6, server version number `180006` |
| Cluster identity | Control-system identifier readable; value not published |
| Revision | Exactly one row, `s2b01_0001` |
| Tables | Exactly the 15 original research tables plus `alembic_version` |
| Task definitions | Exactly five approved tuples, T01–T05 |
| Frozen schema fingerprints | All 13 categories matched `initial_schema_evidence.EXPECTED`; zero mismatches |
| Catalog columns / constraints / indexes | 123 columns, 225 constraints, 20 indexes, including Alembic objects |
| Namespace / extensions | One application namespace; one extension; matched frozen evidence |
| Extra executable/schema behavior | Zero public routines, user triggers, policies, rules or event triggers |
| Role flags | No superuser, CREATEDB, CREATEROLE, replication or BYPASSRLS flags |
| Ownership privileges | Ownership-role privileges for all 16 tables; database-owner membership; public-schema CREATE privilege |
| Other client sessions | Zero visible at the observation time |
| Active / idle-in-transaction clients | Zero / zero; zero client sessions with unobservable state |
| Potentially conflicting write locks | Zero observed |
| Approximate database size | 8,828,607 bytes at initial inspection; retained logical archive size reported below |

The fingerprints cover ordered catalog definitions for relations, columns,
constraints, indexes, schemas, extensions, types, routines, triggers, rules,
policies, event triggers and namespace dependencies. No fingerprint was changed
or regenerated. Owners, role membership and grants are operational checks outside
those fingerprints. Observed ownership capability is not an approved production
role/grant policy or evidence that future sessions cannot appear.

Aggregate metadata counts were also inspected: `task` contained five rows; each
of the other 14 original research tables contained zero rows. No row contents
from those tables were read. The five task tuples were compared with the approved
P1 definitions, not inferred from counts. The version table contained the single
revision row noted above.

The existing PostgreSQL Windows service was observed running. No service-control,
server-stop, server-start, migration, INSERT, UPDATE, DELETE or DDL command targeted
the original development instance.

## Consistent private backup

Installed `pg_dump`, `pg_restore`, `initdb`, `pg_ctl`, `postgres` and
`pg_controldata` utilities all reported **18.6**. Version queries do not constitute
a backup or a cluster lifecycle operation.

`pg_dump` 18.6 created a **48,522-byte custom-format archive** using an exported
snapshot from the same repeatable-read, read-only source transaction used to
capture revision, schema, task and per-table metadata evidence. The dump returned
success; the archive had the expected custom-format signature, and `pg_restore
--list` completed successfully. SHA-256, byte size, opaque backup identifier,
timestamps, baseline commit and snapshot evidence were recorded privately.
The retained archive's checksum was rechecked before restoration and at final
verification. It has not been overwritten or deleted.

This is a logical database backup. It does not include cluster-wide role
definitions, server/service configuration, external writing objects or a private
research storage root. No such root was accessed. Source research tables were
empty except for the five approved task rows, but the backup remains private.

## Isolated restoration and compatibility refusal

Two newly allocated disposable PostgreSQL 18.6 clusters were used: the first
restore attempt and a second diagnostic restore needed to identify its refused
comparison. Each had an exclusive random ownership marker, allocated directory
identity, pinned data-directory identity, a different PostgreSQL system
identifier from development, loopback-only networking and a non-5432 port. No
existing cluster, database or Windows service was reused or reset.

Each restoration used the same retained checksum-verified archive, PostgreSQL
18.6 `pg_restore`, `--exit-on-error` and `--single-transaction`. The target was a
new database named `stylometry_test` inside its separately verified disposable
cluster, not the original test database. No `--clean` or existing-database
overwrite was used. Original database object ownership and privileges remained
in the private archive; restore used `--no-owner --no-privileges` and a dedicated
disposable database owner without superuser/CREATEDB/CREATEROLE privileges. Thus
this does not rehearse restoration of the original role/ACL policy.

An independent Python process verified the actual target database/address/port,
cluster system identifier and private directory/ownership capability before
reading restored catalog/metadata evidence. It then observed:

| Required stage | Observed result |
|---|---|
| Backup retention / protected destination | Approved and verified; retained until explicit deletion authorization |
| Backup checksum / archive listing | Passed; private integrity manifest retained |
| Full archive restoration | Both disposable restores returned success |
| Restored revision | Exactly `s2b01_0001` |
| Restored tables | All 15 original research tables plus Alembic |
| Five task definitions | Exact match |
| Original metadata rows | Counts and SHA-256 row-set digests matched every original table |
| Non-constraint schema evidence | All 12 other frozen categories matched |
| Constraint schema evidence | **Mismatch in nine CHECK definition renderings** |
| Exact initialized migration guard call | Not executed: its prerequisite frozen-evidence comparison failed |
| Actual successor migration / COMMIT | **Not executed** |
| Seven new tables / independent upgraded revision | Not created or observed |
| Reapplication / unknown revision / drift tests on restored target | Not executed after compatibility stop |
| Upgraded-server restart verification | Not executed; no upgraded target existed |
| Disposable cleanup | Both newly owned servers stopped and both owned cluster trees removed |

Source and restored original research constraints each numbered 223, plus two
Alembic constraints. The nine differences were confined to the deparsed CHECK
definition text: an array-level `::text[]` coercion in the source appeared as
per-element `::text` coercions after the logical restore. Names, constraint kinds,
validation flags, deferrability and initially-deferred flags matched for these
entries. The affected reviewed constraints were:

- `dataset_snapshot.ck_dataset_snapshot_context`
- `experiment_run.ck_experiment_run_lifecycle`
- `experiment_run.ck_experiment_run_status`
- `extraction_event.ck_extraction_event_status`
- `qc_evaluation.ck_qc_evaluation_context`
- `qc_evaluation.ck_qc_evaluation_context_threshold`
- `qc_evaluation.ck_qc_evaluation_status`
- `qc_reason.ck_qc_reason_reason_code`
- `source_document.ck_source_document_media_type`

These are observed catalog-text differences, **not a proof of semantic
equivalence**. The exact constraint digest differs, so the restored environment
does not meet the unchanged migration guard's frozen schema requirement. No
schema evidence was regenerated, normalized or replaced; no constraint, migration,
contract or guard was edited to make this pass. Restoration utility success and
matching rows do not establish exact guarded-schema recovery compatibility.

The task's stop condition therefore prevented the successor migration. A real
`s2c03_0001` transaction, successful COMMIT, seven-table verification, duplicate
application refusal and post-upgrade restart are **unexecuted in S2C-03C**.

## Setup and cleanup observations

Initial protected-directory setup stopped before any backup was written.
Windows Store Python redirected a nominal AppData allocation away from the
native ACL process; a subsequent owner-setting ACL operation required an
unavailable privilege. The operator procedure was corrected to use a shared
canonical location and a native DACL-only update while preserving the verified
current-account owner. Protection was independently checked before backup data
was written. No source database setting or approved project module was changed.

One native setup diagnostic emitted an attempted empty allocation's local path;
subsequent diagnostics were sanitized. No such path is included in this report.
One early allocation contains only an ACL-failure traceback and lacks an
original durable ownership marker/identity record; it was left untouched rather
than subjected to uncertain deletion. Its location and this limitation were
recorded privately. It contains no backup, database credentials or source data.
Other marked no-data setup infrastructure was removed only after matching its
canonical directory/device/inode, marker and recorded allocation identity.

Each disposable server was checked for exact ownership and system identity
before `pg_ctl -m fast -w` shutdown. Stopped-server evidence and absence of the
postmaster file were checked before deletion; the first attempt also checked
the postmaster PID/creation-time incarnation had exited. Only exact owned trees
were removed, and both disposable lifecycle pointers are absent. No unknown
directory, original database or existing service was deleted or stopped.

Before backup, recheck the source identity, fingerprints, counts and session
state. Allocate a new local private destination outside Git; restrict and verify
its access controls before writing sensitive artifacts. Never overwrite a backup.
Use a consistent PostgreSQL 18.6 logical backup and retain the source snapshot
identity and metadata comparison evidence privately. Record the artifact's opaque
identifier, completion status, byte size, SHA-256 and timestamps privately. An
archive listing or checksum alone does not establish a usable backup: complete
restoration and comparison of the restored schema and metadata are required.

The restored rehearsal must use freshly allocated, exclusively owned storage,
loopback-only networking and a non-5432 port. Pin the ownership marker, directory
identity, postmaster evidence and unique cluster system identifier. Refuse
identity mismatches; never fall back to the original development/test database.
Restore only into a new empty database in that new cluster. Any owner/ACL mapping
to disposable roles must be explicit and assessed separately from schema
fingerprint compatibility; it must not silently change the development role plan.

The existing injected migration entry point accepts only an owned
`stylometry_test` transaction, exact initialized-mode flags and destination
`s2c03_0001`. Any rehearsal using that name must be distinguished from the
original test database by the independently verified disposable cluster identity,
data directory and non-5432 port. Database name alone is insufficient isolation.

## Requirements immediately before a future development migration

These are requirements, not execution authorization:

1. Obtain separate development-migration approval after completing backup,
   restoration and migration rehearsal and resolving their findings.
2. Reverify the exact approved code, PostgreSQL 18.6 cluster identity, configured
   loopback database/address/port and `s2b01_0001` revision. Keep numeric instance
   identifiers, configuration and paths private.
3. Verify all frozen predecessor fingerprints and five approved task definitions;
   any difference stops execution. Do not regenerate evidence to obtain a pass.
4. Verify a usable retained backup, its integrity and the approved retention and
   recovery arrangements. A backup does not include an external research root;
   this task does not authorize accessing or backing up one.
5. Review migration ownership and grants, reserve a maintenance window, and
   exclude other writers and schema creators. Session/lock checks are snapshots;
   advisory locks do not exclude hostile or uncooperative DDL.
6. Preserve private configuration. Use exact target `stylometry_dev`, mode
   `initialized` and revision/destination `s2c03_0001`; do not substitute `head`,
   disable guards or stamp the version table.
7. Use a real PostgreSQL transaction with autocommit disabled. The unchanged
   initialized-upgrade guard must retain its advisory lock and exclusive locks
   through DDL, the Alembic revision update and actual COMMIT.
8. Independently verify `s2c03_0001`, 22 metadata/journal tables plus Alembic,
   preserved original definitions, all original metadata rows and all five
   task tuples. Verify the seven new table constraints against reviewed evidence.

## Failure, uncertainty and recovery assessment

Successful return from a savepoint is not a successful outer COMMIT. A confirmed
migration requires the real COMMIT plus independent revision/schema/data
verification on the exact expected instance. If acknowledgement is lost, treat
the result as uncertain rather than assuming rollback or success.

For a failure before COMMIT, PostgreSQL transactional DDL and the revision update
should roll back together; establish the actual state using a fresh read-only
connection. If state is uncertain, quiesce writers, preserve private evidence and
inspect exact identity, revision and schema. Do not rerun blindly, edit seeds,
stamp revisions or drop tables. The predecessor guard intentionally refuses an
already upgraded database; downgrade is intentionally disabled.

After a separately authorized server restart, recheck the same cluster system
identifier, revision, all original and new table definitions/constraints, task
tuples and privately retained metadata comparison evidence using independent
connections. An orderly restart is not a crash or power-loss experiment.

Recovery using the verified backup requires a separate reviewed recovery
procedure and explicit authorization. First prove the backup can be restored to
a new isolated target, verify its integrity and compare the expected schema and
metadata. Assess any data/journal entries created after that backup before
choosing forward repair or restoration. Never restore over, reset or delete the
original development database under this preflight authorization.

## Regression and preservation

After disposable cleanup, the full existing suite ran with private PostgreSQL
integration configuration:
**304 passed, 0 failed, 2 skipped**, 306 collected, in **25.23 seconds**. The two
skips are the existing Windows synthetic file-symlink privilege cases at
`tests/test_private_storage.py:59`; they are not passes. No regression tests or
approved application code were changed.

A fresh read-only post-rehearsal check confirmed development's original cluster
identity and server startup time, `s2b01_0001`, all frozen schema fingerprints,
all original table definitions, task tuples and metadata-row digests remained
unchanged. The original Windows PostgreSQL service was running with the same
PID. The original `stylometry_test` passed the empty-target guard with zero
public tables.
Streamlit startup returned **HTTP 200**, four modules and nine not-started stages
were verified, and AppTest navigation passed in the full suite. Only the
temporary Streamlit process was stopped. `git diff --check` and a no-index
whitespace check of this untracked report passed at handoff.

The earlier S2C-03B **25 live validation check groups remain historical evidence**.
That live durability harness was not rerun. The ordinary test suite's temporary
ownership-evidence fixtures do not allocate a PostgreSQL cluster.

Approved migrations, S2A contracts, scientific methods, ORM mappings and dependency
files remain unchanged. No student writing, private research root or scientific
execution was accessed or introduced. Nothing is staged, committed, pushed or
merged for S2C-03C.

## Blockers and next gate

The blocker is the logical restore's CHECK-definition catalog-text mismatch
against the reviewed exact constraint fingerprint. Resolve that incompatibility
through a separately approved backup/recovery and compatibility review. Do not
modify frozen evidence, loosen the guard, rewrite constraints or migrate
development under this task to obtain a pass. A checksum-valid, row-preserving
archive is retained, but exact guarded-schema restoration has not passed.

Only after that review can a separately authorized continuation complete the
guarded migration COMMIT, independent preservation verification, negative checks
and post-upgrade restart on a fresh isolated restoration. Repeat time-sensitive
source identity, writer/session, role/grant and backup-integrity checks first.

Other limits remain: trusted same-account Windows processes, role/grant policy
requiring operational review, future session races, no power-loss/crash proof,
no filesystem/database distributed atomicity, and no approved production
authentication, immutable storage or research-data backup plan.

**Stopped at Approval Gate S2C-03C with a compatibility blocker. Development is
not ready for approval to apply `s2c03_0001`.** Backup retention is approved;
development migration, restore over development and guard changes are not.
Commit, push, merge and S2C-04 remain unauthorized.
