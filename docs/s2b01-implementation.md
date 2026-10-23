# S2B-01 implementation report — approval gate

Prepared 2026-10-23 (Asia/Bangkok). Base `main`/`origin/main`:
`d158f3c`; fetch verified no divergence before creating
`feature/s2b01-postgres-persistence`. Initial working tree was clean. The S2B-01
implementation was subsequently committed and pushed with explicit authorization
as `0ca8894f1ff6b455676c7e24abc15da9744eb339` (`feat: implement s2b01 postgres
persistence foundation`). No merge or scientific execution was performed.
S2B-02 started from that reviewed commit. The user subsequently approved
publication of its safe documentation/ignore corrections and merge into `main`;
see the final approval status below.

## Architecture and source consistency

The source of truth is [the S2A schema proposal](postgresql-schema-proposal.md),
with unchanged `contracts.py`, `paper1.py`, methodology and discrepancy register.
S2B-01 authorizes this engineering foundation; it does not establish final
scientific protocol approval or validate manuscript/source evidence.

One wording inconsistency was resolved using the requested source-of-truth
precedence: the task requests UUID primary keys generally, while the proposal
requires `task.code` as the text primary key and composite association keys.
Those explicit schema exceptions are preserved. All entity IDs and external
object references are UUIDs. UUIDs are supplied by callers, with no extension or
server-side generation dependency. Approved task definitions are seeded by the
migration; CHECK constraints prevent other mappings but cannot require all five
rows to remain present under unrestricted DELETE privileges.

No reported corpus totals become database constraints, outcomes or synthetic
sample requirements. No prompt texts, feature formulas, tokenizer, duplicate
procedure, extraction method or cohort membership algorithm is introduced.

## Files

| File | Purpose |
|---|---|
| `src/stylometry/models.py` | SQLAlchemy 2 declarative mappings and local constraints |
| `src/stylometry/database.py` | Lazy factory, sanitized connection probe and transactional sessions |
| `src/stylometry/persistence.py` | Contract/ORM conversion and explicit whole-graph read validation |
| `src/stylometry/storage.py` | Validated private object descriptor and future resolver protocol |
| `src/stylometry/migration_safety.py` | Local empty development/test target verification |
| `alembic.ini`, `migrations/env.py`, `migrations/script.py.mako` | Explicit Alembic setup and guarded online entry point |
| `migrations/versions/s2b01_0001_initial.py` | Frozen initial DDL and five task definitions; does not import live models |
| `tests/test_persistence.py` | Offline compilation, conversions, safety guards and startup checks |
| `tests/test_postgresql.py` | Opt-in isolated PostgreSQL migration/constraint/relationship tests |
| `pyproject.toml`, `uv.lock` | Alembic dependency and reproducible environment resolution |
| `README.md`, `docs/s2b01-implementation.md` | Setup, commands, design, status and limitations |

Research logic stays under `src/stylometry/`. The launcher, UI, stage registry,
existing contracts and existing tests are unchanged.

## Tables and ORM relationships

All 15 proposed tables are implemented. Foreign keys use `ON DELETE RESTRICT`;
there are no evidence-deleting database cascades or ORM delete cascades.

| Table | Relationships / key purpose |
|---|---|
| `provenance` | Evidence object UUID/hash and timestamp |
| `corpus` | Provenance; versioned collection |
| `writer` | Corpus; internal pseudonym; unique `(id, corpus_id)` |
| `task` | Approved T01–T05 code/genre/form definitions |
| `source_document` | Corpus/provenance; opaque external object, media type/hash |
| `text_sample` | Corpus/provenance/task and composite writer/corpus FK; unique writer/task slot |
| `extraction_event` | Sample/source/provenance; reproducibility and status/output references |
| `clean_text_derivation` | Sample/extraction/parent/provenance; unique per-extraction sample version |
| `qc_evaluation` | XOR sample/writer target, exact derivation and provenance |
| `qc_reason` | QC reason vocabulary; composite QC/reason key |
| `qc_related_sample` | QC and counterpart sample; composite key |
| `dataset_snapshot` | Corpus; exact ordered contract manifest hash/configuration |
| `snapshot_member` | Snapshot/sample key; exact derivation/hash and sample/writer receipt FKs |
| `experiment_run` | Snapshot/hash, stage, lifecycle and reproducibility |
| `run_output` | Run and artifact provenance; composite key |

Embedded reproducibility columns retain contract/configuration versions,
configuration UUID/hash, full Git commit, dirty indicator and environment-lock
hash. All timestamps are `TIMESTAMP WITH TIME ZONE`; digests are checked lowercase
hex `CHAR(64)`. All required columns are NOT NULL. `to_record` flattens
reproducibility, maps task/target fields and creates association rows.
`to_contract` validates reconstructed JSON through the unchanged strict S2A
contracts. Set-like reasons, related IDs and output IDs are read in canonical
sorted order; their original insertion order is not stored. Snapshot members are
always sorted by sample UUID string to reproduce the manifest encoding.

## Enforcement matrix

| Rule | PostgreSQL implementation | Additional boundary / deferred work |
|---|---|---|
| PKs, required fields, references | PK / NOT NULL / explicit restrictive FKs | UUID reuse across different entity tables is checked only by `ResearchBundle` |
| Writer corpus and writer/task slot | Composite FK, UNIQUE | No assumption about repeated submissions beyond S2A slot model |
| Task mapping and media vocabulary | CHECK | Migration seeds all five tasks; ongoing presence needs privileges/service |
| Hash, commit and label syntax; contract version | CHECK | Cannot verify external bytes, Git existence or approved configuration |
| Time zones and local ordering | `timestamptz`; extraction and run ordering CHECKs | S2A rejects naive Python timestamps; PostgreSQL itself interprets naive inputs using session timezone |
| Extraction status/output pair | CHECK | Same source/sample corpus and acquisition chronology require graph validation |
| Clean version positive, parent shape, no self-parent; version uniqueness | CHECK / UNIQUE / parent FK | Same sample/extraction, prior version, successful extraction and input chronology require graph validation |
| QC contexts/statuses/reason vocabulary | CHECK / reason composite PK | Status/reason joins and duplicate counterpart semantics require graph validation |
| QC sample/writer XOR and field separation | CHECK | Derivation must belong to target sample and precede receipt: graph validation |
| Counts/tokenizer/derivation pairing and bounds | CHECK | Counts are supplied metadata, never computed here |
| Context thresholds and primary/balanced writer minima | CHECK, explicitly rejects NULL where required | Balanced word threshold required to PASS; sensitivity writer minimum never inferred |
| PASS qualifying measurements | CHECK | Writer-only related sample restrictions, reason-specific count/evidence rules: contracts/graph |
| Snapshot analytical context and membership references | CHECK / PK / FKs | Manifest hash recomputation, corpus/text/hash/receipt/configuration/time consistency and writer coverage: contracts/graph |
| Run stage/lifecycle/timestamp shape | CHECK | Snapshot hash/chronology, outputs requiring execution and planned-output prohibition: contracts/graph |
| Snapshot/history immutability | Restrictive deletion of referenced records only | No sealing, deferred triggers, immutable grants or update prohibition implemented |

`load_validated_bundle` explicitly reads the full graph and invokes the existing
`ResearchBundle` checks. This can detect invalid persisted metadata, but does not
prevent direct SQL, arbitrary ORM writes, concurrent changes, or post-validation
mutation. No write/sealing service or database deferred trigger is claimed.
Individual converters validate individual records, not the entire database.
Use of these helpers alone does not authorize research ingestion.

A future reviewed service must lock the snapshot/receipts/derivations and
configuration evidence, validate the complete graph within a suitable isolation
boundary, archive the manifest, and apply immutable privileges or triggers.
Operational control must also exclude noncooperating DDL during migrations;
the advisory lock coordinates only participating clients. Append-only history
and direct SQL enforcement remain explicit limitations, not completed features.
No speculative nonunique performance indexes are added without actual queries;
primary/unique constraints provide their normal PostgreSQL indexes.

## Migrations and connection status

Revision `s2b01_0001` creates the metadata schema and seeds only the five approved
task definitions. DDL is frozen in the revision; changing ORM classes later does
not silently alter migration history. Offline SQL generation is verified.
Online execution requires environment designation plus an empty, loopback-hosted
`stylometry_dev`, checked against the actual connected database/server and catalog.
URL query overrides are refused. Existing tables, schema-owned objects, custom
schemas/extensions and event triggers block the initial migration. Existing
Alembic state also blocks this initial-only policy. Destructive downgrade raises
a review-required error. A later migration needs a reviewed target-state policy.

At the S2B-01 handoff, `DATABASE_URL` was absent. A direct Python/psycopg
probe of loopback port 5432 / `stylometry_dev` returned an `OperationalError`;
driver details were suppressed. This does not establish whether PostgreSQL is
installed or whether another authorized endpoint exists. No server installation,
database/role creation, password guessing or configuration outside the workspace
was attempted. No target could be verified empty; **no development migration was
applied**. The connection blocker is an available, privately configured empty
development database. PowerShell provisioning/configuration/migration guidance
is in the README. No PostgreSQL CLI tools are required for verification.

## External file references and security

`StorageReference` carries an opaque object UUID, exact SHA-256, provenance UUID,
optional media type and processing version. The ORM stores source, extracted and
cleaned references in their respective event/version records, alongside method
and reproducibility evidence. Provenance and run outputs supply the evidence and
artifact reference chain. Private configuration/method UUIDs are intentionally
external references without database FK targets, as specified in S2A.

The future `PrivateObjectResolver` must map a UUID through an access-controlled
private catalog to a physical object outside this repository, restrict resolution
to an approved private root, authenticate authorization and verify exact bytes
against the supplied hash. The research identifier remains the UUID when private
files move. No physical path, locator, student identity, raw writing, extracted
writing or cleaned writing field exists in these tables. This task provides no
resolver implementation, file import, cloud service or content upload. Shape
validation alone cannot certify anonymization or prevent misuse of metadata fields.

Credentials are read from environment/project-local ignored `.env`, never from
tracked configuration. Engine creation is lazy, parameter logging is hidden and
echo is disabled. Public probe/session/migration failures suppress underlying
driver details. Callers must use the sanitized boundary and must not log arbitrary
engine/driver exceptions or URLs. No application logs or UI fields were added.
Real metadata and hashes remain private research records; backups are not Git-safe.

## Validation and handoff

Final validation: `.\.venv\Scripts\python.exe -m pytest` collected 93 tests:
**60 passed, 33 skipped** (all skips are PostgreSQL integration cases). The
original 39 tests pass unchanged. New offline checks include PostgreSQL DDL
compilation, credential-free offline Alembic SQL, strict contract round trips,
association conversions, connection/target safety, transaction commit/rollback,
and startup without database operations. The in-memory SQLite transaction test
checks generic session handling only; it is not a PostgreSQL constraint test.

`alembic history` reports `<base> -> s2b01_0001 (head)`. Offline generation emits
15 metadata tables plus Alembic's version table and only five task seed rows.
`uv sync --extra dev --locked` succeeds (54 resolved packages; installed
environment includes Alembic 1.20.1 and Mako 1.4.3). A hidden temporary loopback
Streamlit server returned **HTTP 200** from `/_stcore/health` and was stopped.
`git diff --check` passes. Tracked paths, staged paths (empty), changed content
and new-file inventory were reviewed; no research data or credentials are added.

PostgreSQL integration execution is blocked until a designated isolated `stylometry_test`
database is supplied privately; tests never use the development URL as fallback.
An explicit but unavailable/unsafe test URL is a failure, not a skipped success.
Test-only DDL and synthetic rows are enclosed in a transaction and rolled back;
per-test savepoints isolate mutations. The frozen revision itself is executed in
that test transaction when PostgreSQL is available.

The existing navigation tests cover all four dashboard modules and all nine
unchanged, not-started stages. Additional AppTest coverage forbids database
connections/table creation even with a configured URL. No scientific stages
were executed. No real source records or writing were read or introduced.

At the S2B-01 handoff the next steps were to review the foundation, provision isolated
development/test targets, execute the pending PostgreSQL tests, then review
transactional sealing/immutable storage and access controls before a separately
authorized metadata ingestion service. Methodology/source-validation questions
remain in the unchanged S2A discrepancy register. Do not commit, push or merge
until separately authorized. S2B-02 separately authorizes isolated local database
provisioning and live validation, but no new push or merge.

## S2B-02 initial attempt — historical authentication blocker

This initial attempt is retained as history. Authentication was subsequently
configured privately; the completed live validation is recorded in the next section.

Diagnostics on 2026-10-23 (Asia/Bangkok) confirmed the working branch
`feature/s2b01-postgres-persistence`, HEAD
`0ca8894f1ff6b455676c7e24abc15da9744eb339`, and a clean initial working tree.
The S2B-01 commit had already been pushed with authorization; the earlier
uncommitted-status wording above has been corrected. S2B-02 documentation
changes remain uncommitted and unpushed.

Windows service `postgresql-x64-18` is **Running**. Its registered PostgreSQL
installation's `postgres.exe --version` reports **PostgreSQL 18.6**. The service's
PostgreSQL process owns the listener on TCP **5432** (IPv4 and IPv6). This verifies
an installed binary/service/listener; the running server's SQL-reported version
and cluster identity still require authenticated verification.

A Python/psycopg TCP connection to the local `postgres` maintenance database
reached the server and failed with **password required / no password supplied**.
No SQL query was executed. The project had no `.env`, `DATABASE_URL`,
`STYLOMETRY_TEST_DATABASE_URL`, or configured PostgreSQL connection/authentication
environment variables at diagnosis. The earlier default connection probe cannot
succeed without appropriate authentication; its historical suppressed exception
did not establish that the server was absent. This attempt establishes the
current authentication blocker without guessing passwords or exposing the
underlying connection string.

An authorized local maintenance connection was requested through private
`STYLOMETRY_ADMIN_DATABASE_URL` configuration in the ignored project `.env`.
Do not send the password or private URL through chat or include it in Git.
No authentication changes, password resets, service restarts, global PostgreSQL
configuration changes or alternate unauthenticated access were attempted.

| Required check | Actual S2B-02 status |
|---|---|
| Local PostgreSQL availability | Service/listener available; authenticated SQL unavailable |
| Database-name availability | Unknown: `stylometry_dev` and `stylometry_test` have not been queried |
| Database/role provisioning | Not attempted; names/instance identity cannot yet be verified by SQL |
| Development migration | Not applied; revision remains `s2b01_0001` in source only |
| Development table/seed verification | Not executed; live schema and row counts unknown |
| Full pytest | **60 passed, 33 skipped, 0 failed**; all 33 integration cases remain skipped |
| Streamlit | Temporary loopback startup health **HTTP 200**; verification process stopped |
| Navigation/startup protection | Passing existing tests cover four modules/nine unchanged stages and forbid automatic database connection/table creation |
| Scientific contracts/methods | Unchanged |

The initial migration was reviewed: frozen metadata-only DDL, five approved task
definitions, no hardcoded credentials or machine-specific database locations.
The empty-target guard was not bypassed. No database or role was created, no
migration was executed against PostgreSQL, no existing database was inspected,
and no synthetic or real research rows were persisted by this attempt. Offline
SQL generation and in-memory SQLite session tests are not live PostgreSQL proof.

No integration failure is diagnosed because those tests did not execute. No
runtime correction is proposed until live evidence is available. Existing
cross-row enforcement, sealing and privilege limitations documented above remain.
Merge readiness is **not established**: obtain private authentication, verify
the local instance and both database names through the maintenance catalog, stop
if either name exists, then provision only unused isolated targets/roles, apply
the development migration once, execute all 93 tests with zero integration skips,
and verify test DDL/data rollback. Do not mark S2B-02 complete based on this attempt.
That attempt stopped at **Approval Gate S2B-02** with authentication/live validation
pending and no new commit, push or merge.

## S2B-02 completed live verification

Verification recorded **2026-10-23 09:22 Asia/Bangkok (02:22 UTC)**. Runtime source
is reviewed commit `0ca8894f1ff6b455676c7e24abc15da9744eb339`; only documentation
and the private-file ignore rule changed locally during S2B-02. The environment
lock SHA-256 is
`a8402d8fcab89fa81e4ff1238169de5062001f38e7dbaae28ca8c5effa0dd9a3`.
Inputs were the frozen initial revision, approved five-task definitions and the
existing artificial fixtures in `tests/conftest.py`; no research inputs were used.

The user supplied administrator configuration privately in `con.env`. It was
read without printing values. Since that filename was not previously ignored,
`.gitignore` now explicitly excludes it; `.env` remains ignored. No private
configuration is included in the review changes. Initial diagnostic identity
verification was conservative about the address format: PostgreSQL returns
loopback `inet` as `127.0.0.1/32`. The existing migration guard already accepts
that representation, and no migration/runtime code change was required.

Authenticated SQL verified the local maintenance database `postgres`, loopback
server address, port **5432** and running server version **PostgreSQL 18.6**,
matching the Windows service and installed binary. Queries against the maintenance
catalog checked only the two requested database names and dedicated role names;
none existed before provisioning. No existing research or production database
was connected to or inspected.

Created `stylometry_dev` and `stylometry_test` from `template0`, owned respectively
by new dedicated `stylometry_dev_owner` and `stylometry_test_owner` login roles.
Both roles have NOSUPERUSER, NOCREATEDB, NOCREATEROLE, NOINHERIT, NOREPLICATION,
NOBYPASSRLS and connection limit 5. PUBLIC database privileges were revoked on
these newly created databases. Random independent role passwords were generated
and saved only in the ignored `.env` as the development and test settings.
Database ownership permits DDL within each isolated target; these are development
roles, not a production application-role design. No global server configuration,
authentication policy, existing role or existing database was altered.

Both targets passed `assert_empty_development_target` before any DDL. The regular
Alembic entry point ran with explicit development designation and its original
safety checks; **`s2b01_0001` was applied exactly once to `stylometry_dev`**.
The isolated test database executed the revision only inside the test transaction,
which was rolled back. No safety check was bypassed or destructive downgrade used.

Live development table inventory (15 research metadata tables plus Alembic):

```text
alembic_version       clean_text_derivation  corpus           dataset_snapshot
experiment_run        extraction_event       provenance       qc_evaluation
qc_reason             qc_related_sample      run_output       snapshot_member
source_document       task                   text_sample      writer
```

The revision table contains exactly one row, `s2b01_0001`. The task table contains
exactly the five approved T01–T05 code/genre/form definitions, checked against
`paper1.TASKS`. All other **14 metadata tables contain zero rows**. A live
development schema/ORM comparison with type comparison enabled returned no
differences. No synthetic research records were inserted into development.

The full suite ran with `STYLOMETRY_TEST_DATABASE_URL` loaded privately into the
process environment: **93 passed, 0 failed, 0 skipped**. This comprises the
existing **60 non-PostgreSQL tests** and all **33 PostgreSQL integration tests**.
The PostgreSQL cases verified frozen migration/ORM equivalence, synthetic graph
round trips and relationships, PK/FK/uniqueness and CHECK rejection, QC contexts,
hashes/versions/timestamps, run outputs, transaction rollback and contract detection
of cross-row snapshot inconsistencies. All original 39 tests remain passing.
After the suite, a fresh connection confirmed **zero public tables** and the
empty-target guard passed for `stylometry_test`: test DDL and all artificial
records were rolled back. Live constraints passed; no corrective runtime changes
or scientific-contract changes were needed.

With the private configuration present, a temporary loopback Streamlit server
returned **HTTP 200** and was stopped. Passing AppTest coverage retained all four
dashboard modules and nine not-started stages and explicitly forbade automatic
database connections and table creation during startup. No ETL, writing import,
feature extraction, ICC or analytical execution was performed.

Outputs are the verified development schema/seed, empty post-test database and
the counts/verification receipts recorded here; credentials, raw connection
strings, database dumps, private locators and research content are excluded.
Existing limitations remain: cross-row direct-SQL enforcement, concurrent
snapshot sealing, immutable history privileges/triggers and private object
resolution are deferred. A passed suite does not implement those services.

The S2B-01 code review passed and S2B-02 supplied the live PostgreSQL evidence
above. The user explicitly approved finalization: rerun the full isolated suite,
verify Git safety/history, commit only `.gitignore`, README and this report on
the feature branch, publish it, then merge into `main` without force pushing.
That approval does not authorize research ingestion, production use or S2C.
The final commit and merge outcome are verifiable in Git history and the final
handoff; this report does not predict a commit hash before it exists. Cross-row
enforcement, concurrent sealing, immutable history controls and private storage
resolution remain deferred as documented above. Stop after the approved merge.
