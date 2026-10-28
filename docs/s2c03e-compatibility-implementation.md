# S2C-03E strict restored-schema compatibility

Date: **2026-10-28** (Asia/Bangkok). Branch:
`feature/s2c03c-migration-preflight`. Application baseline:
`2cf0ffeec4eaf6db4ea1433b4443cb6fdc3eb828`.

**Ready for independent code/security review; no migration approval implied.**
The patch accepts the unchanged original schema or the exact complete restored
CHECK representation diagnosed in S2C-03D. Unknown forms and mixed states are
refused. Nothing has been staged, committed, pushed or merged.

## Evidence verified before implementation

Reviewed the S2C-03C preflight, S2C-03D diagnosis, initialized-upgrade guard,
original frozen fingerprints, Alembic environment and both migrations. All nine
pairs have complete definitions, exact table/constraint identities and identical
CHECK kind, validation and deferral properties. Their column types, binary
varchar-to-text cast, built-in operators, deterministic default collation and
three-valued NULL behavior are documented in S2C-03D. No compatibility value was
inferred from a current development fingerprint.

Rechecked PostgreSQL's pinned `REL_18_6` parser source. The original `IN` path and
the explicit array-cast path are distinct: the latter passes its target element
type down to the array constructor, which coerces the elements individually.
The diagnosis's single link at the IN transformation did not locate that second
path. Only its citations were corrected to link separately to
[IN transformation](https://github.com/postgres/postgres/blob/REL_18_6/src/backend/parser/parse_expr.c#L1066),
[explicit array casts](https://github.com/postgres/postgres/blob/REL_18_6/src/backend/parser/parse_expr.c#L2578)
and [element coercion](https://github.com/postgres/postgres/blob/REL_18_6/src/backend/parser/parse_expr.c#L2020).
Its historical statements, definitions and observations remain intact.

## Exact permitted variants

The immutable tuple ledger in
`src/stylometry/restored_schema_compatibility.py:CONSTRAINT_VARIANTS` contains
**both complete seven-field catalog rows** for each entry below. The linked
O/R definitions are the full, unabridged permitted SQL strings, including C6's
newlines; the tests verify all eighteen strings against that historical report.

| ID and full constraint identity | Exact original/restored definitions |
|---|---|
| C1 `dataset_snapshot.ck_dataset_snapshot_context` | [O1/R1](s2c03d-constraint-compatibility.md#c1) |
| C2 `experiment_run.ck_experiment_run_lifecycle` | [O2/R2](s2c03d-constraint-compatibility.md#c2) |
| C3 `experiment_run.ck_experiment_run_status` | [O3/R3](s2c03d-constraint-compatibility.md#c3) |
| C4 `extraction_event.ck_extraction_event_status` | [O4/R4](s2c03d-constraint-compatibility.md#c4) |
| C5 `qc_evaluation.ck_qc_evaluation_context` | [O5/R5](s2c03d-constraint-compatibility.md#c5) |
| C6 `qc_evaluation.ck_qc_evaluation_context_threshold` | [O6/R6](s2c03d-constraint-compatibility.md#c6) |
| C7 `qc_evaluation.ck_qc_evaluation_status` | [O7/R7](s2c03d-constraint-compatibility.md#c7) |
| C8 `qc_reason.ck_qc_reason_reason_code` | [O8/R8](s2c03d-constraint-compatibility.md#c8) |
| C9 `source_document.ck_source_document_media_type` | [O9/R9](s2c03d-constraint-compatibility.md#c9) |

Every row requires `contype='c'`, `convalidated=true`, `condeferrable=false`,
`condeferred=false`. Each restored string has the documented per-literal
`::character varying::text` casts in place of its original array-wide
`::text[]` cast. Literal bytes/order, operators and all surrounding expression
bytes are fixed. This description is explanatory: acceptance compares literal
complete rows, without cast stripping, regex transformations or SQL rebuilding.

The selected global policy is deliberately narrower than the per-entry
combination option discussed in S2C-03D: **only all-original or all-restored**.
All 510 nonuniform combinations of the nine forms are refused. No broader
combination set is enrolled by this patch.

## Effect on the guard

`initial_schema_evidence.EXPECTED` is unchanged. Exact equality across its
thirteen categories remains the original acceptance path. On a mismatch only:

1. Require exactly the original category keys and exact equality for the other
   twelve categories, including columns/types/lengths/defaults/collations,
   indexes, relations, namespaces and executable objects.
2. Read the complete ordered public constraint inventory, including Alembic
   constraints. Each of the nine restored rows must appear exactly once with
   all seven fields equal to its fixed ledger entry. Originals mixed into this
   branch, duplicates and mismatched properties are refused.
3. Substitute only these nine **complete frozen original rows** into an
   in-memory comparison copy. Leave every other row untouched. Hash the entire
   inventory with the existing canonical serialization and require the original
   frozen constraint digest. Missing, extra, renamed or changed unrelated
   constraints therefore fail, even when every allowed restored row is present.
4. Independently check the restored branch's semantic context: built-in
   int4/varchar/text/array identities, binary implicit varchar-to-text cast with
   no conversion function, exact equality/inequality operator and internal
   function signatures, strictness/immutability, and deterministic built-in
   default collation. Catalog reads are qualified to `pg_catalog`.

This comparison performs no DDL or catalog writes. It does not create a second
expected fingerprint from development. PostgreSQL `180006`, exact target and
connection identity, real transaction/autocommit requirements, advisory lock,
exclusive table locks, predecessor revision and exact five task tuples remain
unchanged. The original fast path is unchanged; the extra semantic-context
check applies to restored acceptance. The Alembic entry point and migrations
are unchanged, including the rollback-only provided test connection path.

## Executed tests

The configured full suite collected **364 cases: 362 passed, 0 failed,
2 skipped in 31.20 seconds**. All 304 previously passing cases remain passing;
there are 58 new passing cases. The two skips are the existing Windows synthetic
file-symlink privilege cases at `tests/test_private_storage.py:59`, reported as
`Host cannot create this synthetic symbolic link`.

The new tests use the existing explicitly configured `stylometry_test` rollback
fixture. It builds the frozen initial migration and Alembic predecessor inside
an enclosing transaction, verifies the original full 225-constraint digest,
then reparses the nine documented emitted **original** CHECK definitions as
restore would. PostgreSQL produces precisely the nine documented alternatives;
all twelve other categories still match. This independently validates the
literal ledger against actual PostgreSQL parsing rather than trusting mocked
alternative strings. The fixture rolls back its DDL and rows.

| Test area | Observed result |
|---|---|
| Original full schema | All thirteen frozen categories equal; initialized guard accepts |
| Exact reparsed restored schema | Constraint digest differs; twelve other categories equal; semantic-context check and full guard accept |
| Guarded Alembic entry on restored fixture | Adds seven tables and updates revision inside a savepoint; second application refused; enclosing transaction remains active and rolls back |
| Guarded Alembic entry with extra CHECK | Refused, with revision, schema and sixteen-table inventory unchanged |
| Cast/operator/expression changes | Truncating `character(7)` cast, changed comparison operator and unknown literal refused |
| Constraint inventory | Missing, extra, renamed, duplicated, reordered and unrelated-constraint changes refused |
| Every row field | Wrong table/name/kind, validation, deferrability, initial deferral and definition refused |
| Combined attack | All nine approved restored expressions plus an unrelated CHECK changed to TRUE refused |
| Other schema drift | Actual column length, index and namespace changes refused; each of all twelve other fingerprint categories separately exercised |
| Version/revision/seeds | Wrong/missing version evidence, unknown/absent/already-upgraded revisions and altered values for each T01-T05 refused |
| Semantic context | Contradictory type/cast/operator/strictness/volatility/determinism expectations fail against real built-in catalogs and fail the guard |
| Combination policy | Every one of the 510 unreviewed mixed catalogs refused |

Synthetic catalog mutations exercise properties PostgreSQL does not expose as
valid CHECK DDL, such as deferrable CHECKs. Built-in mismatch tests evaluate
contradictory expectations against the actual catalogs and inject that false
result into the guard; they do not modify protected system catalogs. Existing
identity, locking, migration mode/destination, autocommit and rollback safety
tests also passed in the complete suite.

## Preservation and operational verification

Development was inspected only in repeatable-read, read-only transactions,
without calling its exclusive-locking upgrade guard. Before/after verification
confirmed unchanged cluster identity and server startup time, predecessor
`s2b01_0001`, all thirteen original fingerprints, all original table counts and
all five exact task tuples. Fourteen research tables remain empty. No
development migration or research metadata write occurred.

After all tests, the original `stylometry_test` passed the empty-target guard
with **zero public tables**. No existing database was recreated and no
PostgreSQL server/service was started, stopped or restarted. The retained
private backup, its directory/manifests and the unmarked allocation were not
accessed or changed in S2C-03E.

Streamlit startup returned **HTTP 200**; four modules and nine not-started stages
were verified, and AppTest navigation passed in the full suite. Only the
temporary loopback Streamlit process was terminated. Whitespace and sensitive
material inspection cover the implementation, tests and reports. No private
path, connection URL, credential, backup, capability or research content is
included in the patch. Initial/successor migrations, frozen fingerprints, S2A
contracts, P1 ORM models, scientific methods and dependency files are unchanged.

## Remaining limits and next gate

These are rollback fixture results, **not a new backup/restore rehearsal or
durability run**. The earlier 25 live durability check groups and S2C-03D's
702 paired truth results / 306 paired INSERT attempts remain historical
observations. They were not rerun or relabeled as new pytest results.

Independent review must assess the nine literal exceptions, full-inventory
digest anchor, pinned context and intentionally restricted combination policy.
Future PostgreSQL versions or deparser forms, nondeterministic/custom
collations, other casts/operators and unknown catalog changes remain refused.
This guard does not establish malicious-superuser resistance, role/ACL recovery,
writer exclusion outside its existing lock model, crash/power-loss durability
or database/filesystem distributed atomicity.

After separate approval, rehearse the reviewed migration on a fresh explicitly
owned restore of the retained checksum-verified archive. Reverify ownership,
directory and system identities, private capability, non-5432 loopback port,
predecessor revision, complete compatible schema, metadata and task evidence.
Only that isolated target may receive a genuine outer COMMIT. Verify from an
independent connection the new revision, seven added tables and preservation
of original definitions/rows/tasks; exercise repeat/drift refusals and an owned
orderly restart, then clean up only positively owned infrastructure. A later
development-migration decision is separate.

**Stopped at Approval Gate S2C-03E. No commit, push, merge, development migration,
new live restoration or S2C-04 was performed.**
