# S2C-03B genuine isolated durability validation

Validation date: **2026-10-23**. Reviewed application baseline:
`e298919059762f8883e297c584f134878114ab0e`, branch
`feature/s2c03-durable-operations`. The working tree was clean before this task.
The S2C-03 runtime, seven journal mappings, migration guards, frozen schema
fingerprints, migrations, scientific contracts and methods remain unchanged.

**Result: 25 live validation check groups passed. Existing pytest: 253 passed,
0 failed, 2 Windows file-symlink privilege skips.** These are separate counts;
the live check groups are not additional pytest cases.

## Isolation and ownership

The new `tools/validate_s2c03_durability.py` harness requires an explicit
`--run-owned-cluster` argument. Importing it does not connect to a database,
start a server or allocate scratch storage. It uses PostgreSQL **18.6** `initdb`, `pg_ctl` and server binaries,
not the existing PostgreSQL Windows service.

- A fresh OS-allocated temporary parent outside Git contained the disposable
  data directory, private instance record, server logs and artificial manifests.
  No caller-selected existing cluster or research directory was accepted.
- A new available TCP port was selected; port **5432 was explicitly refused**.
  The server listened only on `127.0.0.1`. No service was installed or modified.
- `initdb` created a random temporary administrator. A separate random login
  owned the new `stylometry_test` database and had NOSUPERUSER, NOCREATEDB and
  NOCREATEROLE attributes. The observer received permission to read the owned
  instance's control-system identity. No credentials or URLs were printed.
- Ownership evidence included the allocation marker, resolved absolute root,
  device/inode, private random token, exact data directory, postmaster file,
  actual server address/port/version and PostgreSQL cluster system identifier.
  Restart required the identical system identifier. Numeric instance details and
  paths were private lifecycle evidence, removed with the owned infrastructure.
- Genuine server settings were checked: `fsync=on`, `synchronous_commit=on` and
  `full_page_writes=on`. Resource settings were 32 MB shared buffers and a maximum
  of 12 connections. These are harness settings, not global server changes.

Credentials, recovery capabilities, manifests and detailed native/driver logs
remained private. A new ignored `.env.s2c03b-owned-location` pointer made an
interrupted harness discoverable without scanning directories or overwriting
existing configuration. It was deleted after verified cleanup. Existing `.env`
and `con.env` contents remained byte-for-byte unchanged.

The harness itself never connects to the original development or test database.
Only Phase F used them: the approved existing test rollback fixtures and a
separate **read-only metadata check** of the development revision. No research
records or writing contents were read from development.

## Real migration COMMITs

The disposable target was verified empty using the unchanged
`assert_empty_development_target(..., database='stylometry_test')` guard.
The frozen `s2b01_0001` migration and normal Alembic version table were created
inside a real SQLAlchemy Engine transaction and **committed**.

A new independent client process verified:

- revision `s2b01_0001`;
- 15 original research tables plus `alembic_version`;
- the exact five approved task-definition tuples.

Before the successor, separate fault transactions injected an unknown revision
and an unexpected public table. The reviewed initialized-upgrade guard refused
both. Fault transactions were rolled back. No fingerprint was regenerated or
guard weakened.

The successor ran through the reviewed Alembic initialized connection entry
point, exact target/revision flags and `assert_initialized_upgrade`. Its savepoint
was enclosed by a genuine Engine transaction that **committed**; it was not a
rollback fixture. A fresh independent process verified `s2c03_0001`, all 22
metadata/journal tables plus `alembic_version`, and unchanged task values.
Original relation, column, constraint, index, trigger and rule definitions were
compared before and after and matched.

Actual revision sequence: **empty → s2b01_0001 COMMIT → s2c03_0001 COMMIT**.
Neither migration was executed against `stylometry_dev` during this task.

## Application-process exits after genuine COMMIT

Artificial bytes and metadata were generated explicitly. Each operation had
unique operation/idempotency UUIDs, a complete canonical request, publication
metadata and a privately retained recovery descriptor. Workers used the actual
`DurableSyntheticRunner.execute()` with real SQLAlchemy Engines and psycopg
connections. There was **no RollbackBoundaryEngine or enclosing rollback fixture**.

| Forced child exit | Fresh-process observation before recovery | Recovery result |
|---|---|---|
| `after_plan_commit` | planned/publishing journal events persisted; no source-document registration yet | Explicit dead registration-lock release; identical request completed |
| `after_stage_commit` | staged event and source metadata persisted | Independent verification completed; no duplicate records |
| `after_verified_commit` | committed_verified event and metadata persisted | Identical retry preserved history, rows and hashes |

Each checkpoint was reached only after the relevant real transaction context
returned from COMMIT. The child then used `os._exit`, so Python cleanup/finally
blocks did not simulate a rollback or release its lock. Independent processes
observed the actual committed journal and research rows. Recovery compared exact
requests, object UUIDs, digests and database rows, not a status label alone.
Repeated successful execution preserved the observed event history and metadata.

## Catalog interruption and acknowledgement faults

A two-object operation was terminated after the second payload was published
but before its catalog transition. The first catalog entry remained readable
and hash-valid; the second reference was not prematurely reported readable.
The SQL journal retained its committed publishing state. The dead worker's
writer/registration locks required explicit ownership-checked release. A new
process resumed the complete identical manifest and verified both objects.

Three separate acknowledgement-fault cases used a psycopg Connection subclass
whose `commit()` first called the **real psycopg COMMIT**, then raised a controlled
OperationalError after COMMIT number 1, 2 or 3. No transaction or savepoint was
substituted for COMMIT. The service reported an uncertain outcome and persisted
a reconciliation indicator when possible. Fresh independent processes found the
expected committed journal/source rows; normal real-Engine retries completed
without duplicates or payload overwrites.

This is controlled driver-boundary acknowledgement fault injection. It is
distinct from the three process-exit tests and does **not** establish arbitrary
network failure timing, TCP proxy behavior or recovery from every ambiguous
server/driver condition.

## Orderly restart of the owned PostgreSQL server

Seven completed positive-case operations referenced eight artificial objects.
Fresh-process observations captured each operation's event history, registered
source counts and hash verification before restart.

Only the owned disposable instance was stopped with `pg_ctl -m fast -w` and
restarted using the same validated private data directory. The harness checked
the same cluster system identifier and actual server/database/port identity.
New independent client processes verified:

- `s2c03_0001`, 22 metadata/journal tables plus the version table and exact seeds;
- all seven positive-case operation histories and source metadata unchanged;
- all eight published object hashes still valid;
- repeated post-restart reconciliation remained idempotent.

This proves the observed real COMMITs survived independent application clients
and an **orderly restart of this disposable PostgreSQL 18.6 instance**. It does
not prove power-loss durability or filesystem/database atomicity.

## Negative checks

The live run verified refusal of:

- a conflicting manifest, reused idempotency identity with a new request,
  conflicting publication version and conflicting object hash; the original
  completed operation remained unchanged;
- a missing completed payload and a deliberately corrupted completed payload,
  each injected only into a separate owned artificial case after real COMMIT;
- a reader without an allow policy;
- a live competing process holding the writer lock, and an attempted live-owner
  lock release; after that owned child was terminated, explicit dead-owner
  release and an identical retry succeeded;
- orphan partial control evidence, detected without automatic promotion/deletion;
  only the exact artificial fault-injection file was removed by the harness;
- an unknown current Alembic revision in a disposable fault transaction, rolled
  back after refusal;
- an incorrect unbound loopback port, with no fallback to another instance;
- a deliberately wrong cluster system identifier at the harness identity check.

Unknown **predecessor** schema drift was tested at the initialized migration
guard before applying the successor. This is not a claim that the operation
service fingerprints every live successor-schema change. Exact cluster-system
identity pinning belongs to this validation harness; the reviewed service itself
checks its configured local database/address/port, transaction and revision.

## Regression, corrections and cleanup

The existing full pytest suite ran with the original isolated PostgreSQL test
URL enabled: **253 passed, 0 failed, 2 skipped**, 255 collected, 14.57 seconds.
Both skips are the pre-existing Windows file-symlink privilege cases in
`tests/test_private_storage.py:59`; they were not counted as passing. All
configured PostgreSQL tests executed. A fresh read-only connection then passed
the empty-target guard and confirmed zero public tables in the original
`stylometry_test`, with no persistent synthetic records.

The original `stylometry_dev` was checked in a read-only transaction: revision
`s2b01_0001`, 15 original tables plus version and five task rows. No successor
migration, schema changes, inserts or data import occurred there. The existing
Windows service stayed running with the same service PID; no lifecycle command
targeted it or port 5432. Streamlit returned **HTTP 200** on a temporary loopback
server, which was stopped. Four modules and nine planned stages remained intact,
and AppTest's startup/no-workflow-connection checks passed.

The first harness initialization attempt encountered a Windows inherited-output
pipe wait after its new server became ready. No migration or operation had run
at that point. After exact private ownership/data-directory/port verification,
only that disposable server was stopped; its allocated infrastructure was
cleaned. The harness changed lifecycle command output from captured pipes to
private log files and reran successfully. This was a harness correction, not a
failure or modification of reviewed S2C-03 application code. Public prerequisite
errors are also sanitized. The final harness source compiled successfully.

After verification the successful run stopped its owned instance and checked
that its postmaster file was absent. It validated the exact allocated absolute
root, identity and marker again before deleting only that owned tree, all owned
synthetic workspaces and its lifecycle pointer. No unknown directory, service,
existing database or research storage was deleted, recreated or reset.

New local files only:

- `tools/validate_s2c03_durability.py`: explicit live harness and independent workers;
- `docs/s2c03-live-durability-validation.md`: this sanitized report.

No reviewed runtime correction was required. No credential, connection URL,
actual storage path, private catalog, descriptor, database export or artificial
payload file is included in Git. No real student files or scientific stages
were accessed/executed. Nothing was committed, pushed or merged.

## Decision and remaining limits

**Recommend S2C-03 for merge approval as a synthetic-only foundation**, subject
to review of this validation evidence and the new harness. The previous lack of
genuine COMMIT/independent-client/orderly-server-restart evidence is addressed
for the tested cases. Publication/merge is not performed or authorized here.

**A subsequent development migration is safe to propose, not to execute now.**
It still needs separate approval, an approved private backup/restore rehearsal,
reviewed role/grant ownership, a maintenance window excluding other writers and
the unchanged exact initialized-upgrade preflight. The guard remains pinned to
PostgreSQL 18.6 and the reviewed predecessor schema; drift is a stop condition.

Remaining limits: no power-loss or abrupt server-crash tests; no distributed
atomic transaction; Windows-only fixed-drive publishing; trusted same-account
processes; temporary synthetic capabilities rather than production authentication;
service-level append-only behavior rather than full database immutability;
production ACLs, long-term retention, encrypted backup/restore and audit policy
still need design/review. Controlled driver acknowledgement exceptions do not
cover every network/driver uncertainty. Successful synthetic engineering checks
do not approve extraction, QC, feature computation or statistical methods.

Stop at **S2C-03B Approval Gate**. Do not commit, push, merge, migrate development
or begin S2C-04 without separate authorization.
