# S2C-03 migration safety — proposed, not applied to development

The proposed successor `s2c03_0001` adds exactly seven operation-related tables to
`s2b01_0001`. It does not alter, rename or drop any existing table/column, change
task seeds or rewrite research rows. The frozen initial migration and original
empty-target guard are unchanged. Development was not connected to or modified.

## Distinct entry paths

Initial creation still requires an explicitly designated empty local
`stylometry_dev`. It now requires the literal revision `s2b01_0001`, so `head`
cannot accidentally apply the successor through the initial empty-target policy.
Only that frozen initial revision can be rendered offline. Successor offline
execution is refused rather than emitting an unguarded upgrade script.

An initialized upgrade requires all of:

- Target database designation `stylometry_dev`, mode `initialized` and exact
  revision designation `s2c03_0001`, plus the literal Alembic destination of that
  same revision. `head` is refused even if it currently resolves to the successor.
- A `postgresql+psycopg` URL with loopback host, exact database name, no URL query
  overrides; actual server database, loopback address and port match that URL.
- PostgreSQL **18.6** (server version number 180006), the reviewed catalog version;
  an unambiguous `public` search namespace with no session temporary schema.
- A transaction-scoped advisory migration lock; refuse if already held elsewhere.
  Driver autocommit must be disabled: a SQLAlchemy transaction flag alone does
  not establish a real PostgreSQL transaction or retained transaction lock.
  A two-second local table lock timeout, followed by exclusive locks on all 15
  predecessor tables and the Alembic version table through the upgrade transaction.
- Exactly one Alembic revision row, `s2b01_0001`. Already-upgraded, unknown, missing
  or multiple revisions are refused; no silent reapplication or stamping.
- Exact predecessor schema-only evidence and the five approved task tuples.

Frozen SHA-256 evidence in `initial_schema_evidence.py` was generated from the
unchanged initial revision plus Alembic's normal version table inside an isolated
rolled-back test transaction. Digests cover ordered catalog definitions for
schemas, extensions, event triggers, relations/options/RLS, columns/defaults/types,
CHECK/FK/PK/unique constraints, index definitions/validity, triggers, policies,
routines, types, rules and namespace dependency-object counts. No data rows,
owners, credentials or filesystem paths are included. Task rows are checked
separately against approved P1 definitions.

Changed/missing/weakened constraints, extra tables/views/functions/indexes,
unexpected schemas, RLS drift, wrong revision or changed task seeds stop the
upgrade. Server/catalog differences require review: **never regenerate digests
from the development target to make a refusal disappear**. Owners, role membership,
grants and external writers are a separate private operational preflight. The
guard cannot prevent a hostile superuser or an uncooperative concurrent actor from
creating new namespace objects; exclude other sessions/DDL operationally.

Alembic applies the successor and version-table update within the same enclosing
transaction. Driver/parser errors are replaced with a fixed public-safe failure;
do not expose private exception logs. There is no application import/startup
migration, database creation, automatic reset or downgrade path.

The test-only injected connection path accepts only an active caller-owned
`stylometry_test` transaction with the same exact mode/revision flags. It runs the
same initialized guard and Alembic revision inside a savepoint, never committing
the fixture's transaction. It rejects development connections. The CLI does not
automatically accept a test target or an arbitrary injected URL.

## Preflight before separately approved development execution

1. Review the exact code, frozen revision and predecessor fingerprints. Confirm
   the intended PostgreSQL 18.6 instance privately, the existing revision and
   expected 15-table schema/five tasks. Do not inspect writing contents.
2. Take an approved private backup and rehearse restoration on a separately
   authorized isolated environment. Protect catalog/object/manifest/descriptor
   backups consistently. No backup/export was created in this task.
3. Confirm least-privilege migration ownership and private role/grant policy.
   Quiesce application sessions and exclude all other schema writers. Reserve a
   maintenance window; advisory locks alone do not exclude uncooperative DDL.
4. Preserve the ignored local configuration. Do not paste URLs/passwords into
   shell commands, logs, reports or Git. Ensure the URL selects the intended
   maintenance operation's development role, not the administrator or test role.
5. Run the exact command below only after separate migration authorization. The
   command itself repeats preflight and holds locks through transaction completion.
   Any refusal means stop and investigate privately; do not drop objects, edit
   seed data, stamp a revision or weaken checks to force it through.
6. After confirmed commit, privately verify the revision, 22 metadata/journal
   tables plus version table, unchanged task tuples and no unexpected row changes.
   Do not treat successful synthetic tests as scientific run completion.

Proposed command — **NOT executed; do not run at this review gate**:

```powershell
$env:STYLOMETRY_MIGRATION_TARGET = 'stylometry_dev'
$env:STYLOMETRY_MIGRATION_MODE = 'initialized'
$env:STYLOMETRY_MIGRATION_REVISION = 's2c03_0001'
.\.venv\Scripts\python.exe -c "from dotenv import load_dotenv; from alembic import command; from alembic.config import Config; load_dotenv('.env', override=False); command.upgrade(Config('alembic.ini'), 's2c03_0001')"
Remove-Item Env:STYLOMETRY_MIGRATION_TARGET
Remove-Item Env:STYLOMETRY_MIGRATION_MODE
Remove-Item Env:STYLOMETRY_MIGRATION_REVISION
```

## Failure and recovery

A pre-commit error rolls back transactional DDL and revision updates. If the
client loses the commit acknowledgement, treat the outcome as unknown. Reconnect
read-only after separate authorization and inspect the exact revision/schema;
do not rerun or manually stamp blindly. An already-upgraded revision intentionally
fails the predecessor guard. Prepare a separately reviewed repair/forward migration
for any unexpected state. The successor `downgrade()` always refuses destructive
rollback. Once new operations exist, restoration/forward repair must preserve
their evidence; deleting journal tables is not a safe rollback strategy.

Tests verify the exact Alembic upgrade entry point, schema/ORM equivalence, existing
tables/task preservation, populated synthetic predecessor metadata, revision/drift/
namespace refusal and cooperative advisory-lock exclusion. All test DDL/rows are
rolled back in `stylometry_test`; no persistent development upgrade, downgrade,
database reset or actual COMMIT-survives-restart demonstration was performed.

Stop at **Approval Gate S2C-03**. This document proposes a command and preflight;
it does not authorize executing them on development.
