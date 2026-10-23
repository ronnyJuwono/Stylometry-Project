# S2B-01 implementation report — approval gate

Prepared 2026-10-23 (Asia/Bangkok). Base `main`/`origin/main`:
`d158f3c`; fetch verified no divergence before creating
`feature/s2b01-postgres-persistence`. Initial working tree was clean. Changes are
uncommitted for review; no push, merge or scientific execution is authorized.

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

`DATABASE_URL` is absent in the current configuration. A direct Python/psycopg
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

Next: review this foundation at **Approval Gate S2B-01**, provision isolated
development/test targets, execute the pending PostgreSQL tests, then review
transactional sealing/immutable storage and access controls before a separately
authorized metadata ingestion service. Methodology/source-validation questions
remain in the unchanged S2A discrepancy register. Do not commit, push or merge
until separately authorized.
