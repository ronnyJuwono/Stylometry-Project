# S2C-03D restored constraint compatibility diagnosis

Date: **2026-10-28** (Asia/Bangkok). Branch:
`feature/s2c03c-migration-preflight`. Approved HEAD, local `main`, `origin/main`
and remote `main`: `2cf0ffeec4eaf6db4ea1433b4443cb6fdc3eb828`.

**Conclusion: all nine differing CHECK expressions are verified equivalent in
the precisely scoped PostgreSQL 18.6 context below.** Their stored expression
trees and rendered definitions are different. This conclusion rests on a
compositional argument about fixed literal arrays and unchanged operators and
surrounding expressions, supported by catalog inspection and synthetic tests;
functional examples alone are not treated as proof.

**The approved guard remains unchanged and does not accept the restored
constraint fingerprint.** No successor migration, development migration or
compatibility implementation was performed. Approval of this diagnosis is not
approval to migrate. The S2C-03C report remains the historical record of the
earlier stop before migration.

## Evidence and scope

Reviewed sources: `docs/s2c03c-development-migration-preflight.md`,
`docs/s2c03-migration-safety.md`, `src/stylometry/upgrade_safety.py`,
`src/stylometry/initial_schema_evidence.py`, both frozen Alembic migrations, and
the related `CheckConstraint`/column declarations in `src/stylometry/models.py`.
The nine ORM expressions exactly matched their initial migration expressions.

Existing private S2C-03C schema-only comparisons supplied the exact original and
restored renderings. Because those records lacked expression trees and complete
cast/operator/collation details, an additional **repeatable-read, read-only**
catalog inspection of development collected only those details. The original
revision and all 13 approved fingerprint categories still matched. No original
writing or research-row contents were read for this diagnosis.

One new, explicitly owned PostgreSQL 18.6 cluster was restored from the retained
private archive. Its system identifier differed from development; it used fresh
storage, a marker and directory identity, loopback networking and a non-5432
port. No existing database/service or unmarked allocation was reused. The
restored revision/metadata matched the retained evidence; only the same
constraint category differed. Synthetic probes ran in temporary objects within
a transaction that was rolled back. The exact owned server was stopped, its
process incarnation was checked to have exited, and its owned infrastructure
was removed. There was no successor migration or new approved fingerprint.

## Exact nine-constraint comparison

O1–O9 and R1–R9 below are **complete, unabridged** values of
`pg_get_constraintdef(oid, true)`, not reconstructed scientific rules. For every
row, both sides have `contype='c'`, `convalidated=true`,
`condeferrable=false`, `condeferred=false`. Related string columns are NOT NULL;
their type modifiers and default deterministic collation match. The timestamp
columns in C2 and integer column in C6 remain nullable as in the initial schema.

The exact delta in each row is the same bounded operation on its one displayed
literal array: its final `::text[]` disappears, and `::text` is appended to each
existing literal's `::character varying` cast. The order and bytes of the
literals do not change. Offline comparison confirmed **all expression bytes
outside that one array are identical** for each pair. This observation is not a
regex-based acceptance policy or permission to transform other SQL.

| ID / table / constraint | Related column types | Affected expression / exact delta | Assessment |
|---|---|---|---|
| [C1: O1/R1](#c1) - `dataset_snapshot.ck_dataset_snapshot_context` | `context character varying(32)` | IN to `= ANY`; fixed array-wide text cast becomes per-element text casts | Verified equivalent under pinned context |
| [C2: O2/R2](#c2) - `experiment_run.ck_experiment_run_lifecycle` | `status character varying(16)`; `started_at timestamp with time zone`; `finished_at timestamp with time zone` | succeeded/failed `= ANY` subexpression only; same cast delta | Verified equivalent under pinned context |
| [C3: O3/R3](#c3) - `experiment_run.ck_experiment_run_status` | `status character varying(16)` | IN to `= ANY`; fixed array-wide text cast becomes per-element text casts | Verified equivalent under pinned context |
| [C4: O4/R4](#c4) - `extraction_event.ck_extraction_event_status` | `status character varying(16)` | IN to `= ANY`; fixed array-wide text cast becomes per-element text casts | Verified equivalent under pinned context |
| [C5: O5/R5](#c5) - `qc_evaluation.ck_qc_evaluation_context` | `context character varying(32)` | IN to `= ANY`; fixed array-wide text cast becomes per-element text casts | Verified equivalent under pinned context |
| [C6: O6/R6](#c6) - `qc_evaluation.ck_qc_evaluation_context_threshold` | `context character varying(32)`; `word_threshold integer` | NOT IN to `<> ALL`; fixed array-wide text cast becomes per-element text casts | Verified equivalent under pinned context |
| [C7: O7/R7](#c7) - `qc_evaluation.ck_qc_evaluation_status` | `status character varying(24)` | IN to `= ANY`; fixed array-wide text cast becomes per-element text casts | Verified equivalent under pinned context |
| [C8: O8/R8](#c8) - `qc_reason.ck_qc_reason_reason_code` | `reason_code character varying(40)` | IN to `= ANY`; fixed array-wide text cast becomes per-element text casts | Verified equivalent under pinned context |
| [C9: O9/R9](#c9) - `source_document.ck_source_document_media_type` | `media_type character varying(100)` | IN to `= ANY`; fixed array-wide text cast becomes per-element text casts | Verified equivalent under pinned context |

### C1

`dataset_snapshot.ck_dataset_snapshot_context`

O1 - original:

```sql
CHECK (context::text = ANY (ARRAY['primary_80'::character varying, 'sensitivity_100'::character varying, 'balanced_five_task'::character varying]::text[]))
```

R1 - restored:

```sql
CHECK (context::text = ANY (ARRAY['primary_80'::character varying::text, 'sensitivity_100'::character varying::text, 'balanced_five_task'::character varying::text]))
```

### C2

`experiment_run.ck_experiment_run_lifecycle`

O2 - original:

```sql
CHECK (status::text = 'planned'::text AND started_at IS NULL AND finished_at IS NULL OR status::text = 'running'::text AND started_at IS NOT NULL AND finished_at IS NULL OR (status::text = ANY (ARRAY['succeeded'::character varying, 'failed'::character varying]::text[])) AND started_at IS NOT NULL AND finished_at IS NOT NULL OR status::text = 'cancelled'::text AND finished_at IS NOT NULL)
```

R2 - restored:

```sql
CHECK (status::text = 'planned'::text AND started_at IS NULL AND finished_at IS NULL OR status::text = 'running'::text AND started_at IS NOT NULL AND finished_at IS NULL OR (status::text = ANY (ARRAY['succeeded'::character varying::text, 'failed'::character varying::text])) AND started_at IS NOT NULL AND finished_at IS NOT NULL OR status::text = 'cancelled'::text AND finished_at IS NOT NULL)
```

### C3

`experiment_run.ck_experiment_run_status`

O3 - original:

```sql
CHECK (status::text = ANY (ARRAY['planned'::character varying, 'running'::character varying, 'succeeded'::character varying, 'failed'::character varying, 'cancelled'::character varying]::text[]))
```

R3 - restored:

```sql
CHECK (status::text = ANY (ARRAY['planned'::character varying::text, 'running'::character varying::text, 'succeeded'::character varying::text, 'failed'::character varying::text, 'cancelled'::character varying::text]))
```

### C4

`extraction_event.ck_extraction_event_status`

O4 - original:

```sql
CHECK (status::text = ANY (ARRAY['succeeded'::character varying, 'failed'::character varying]::text[]))
```

R4 - restored:

```sql
CHECK (status::text = ANY (ARRAY['succeeded'::character varying::text, 'failed'::character varying::text]))
```

### C5

`qc_evaluation.ck_qc_evaluation_context`

O5 - original:

```sql
CHECK (context::text = ANY (ARRAY['source_inventory_100'::character varying, 'primary_80'::character varying, 'sensitivity_100'::character varying, 'balanced_five_task'::character varying]::text[]))
```

R5 - restored:

```sql
CHECK (context::text = ANY (ARRAY['source_inventory_100'::character varying::text, 'primary_80'::character varying::text, 'sensitivity_100'::character varying::text, 'balanced_five_task'::character varying::text]))
```

### C6

`qc_evaluation.ck_qc_evaluation_context_threshold`

O6 - original:

```sql
CHECK ((context::text <> ALL (ARRAY['source_inventory_100'::character varying, 'primary_80'::character varying, 'sensitivity_100'::character varying]::text[])) OR word_threshold IS NOT NULL AND word_threshold =
CASE
    WHEN context::text = 'primary_80'::text THEN 80
    ELSE 100
END)
```

R6 - restored:

```sql
CHECK ((context::text <> ALL (ARRAY['source_inventory_100'::character varying::text, 'primary_80'::character varying::text, 'sensitivity_100'::character varying::text])) OR word_threshold IS NOT NULL AND word_threshold =
CASE
    WHEN context::text = 'primary_80'::text THEN 80
    ELSE 100
END)
```

### C7

`qc_evaluation.ck_qc_evaluation_status`

O7 - original:

```sql
CHECK (status::text = ANY (ARRAY['not_evaluated'::character varying, 'pass'::character varying, 'excluded'::character varying, 'review_required'::character varying]::text[]))
```

R7 - restored:

```sql
CHECK (status::text = ANY (ARRAY['not_evaluated'::character varying::text, 'pass'::character varying::text, 'excluded'::character varying::text, 'review_required'::character varying::text]))
```

### C8

`qc_reason.ck_qc_reason_reason_code`

O8 - original:

```sql
CHECK (reason_code::text = ANY (ARRAY['missing_text'::character varying, 'below_word_threshold'::character varying, 'duplicate_text'::character varying, 'insufficient_eligible_tasks'::character varying, 'extraction_failed'::character varying, 'unresolved_method'::character varying]::text[]))
```

R8 - restored:

```sql
CHECK (reason_code::text = ANY (ARRAY['missing_text'::character varying::text, 'below_word_threshold'::character varying::text, 'duplicate_text'::character varying::text, 'insufficient_eligible_tasks'::character varying::text, 'extraction_failed'::character varying::text, 'unresolved_method'::character varying::text]))
```

### C9

`source_document.ck_source_document_media_type`

O9 - original:

```sql
CHECK (media_type::text = ANY (ARRAY['application/pdf'::character varying, 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'::character varying, 'text/plain'::character varying, 'application/octet-stream'::character varying]::text[]))
```

R9 - restored:

```sql
CHECK (media_type::text = ANY (ARRAY['application/pdf'::character varying::text, 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'::character varying::text, 'text/plain'::character varying::text, 'application/octet-stream'::character varying::text]))
```


## Why the trees and renderings differ

PostgreSQL 18.6's `pg_dump` obtains table CHECK definitions with
`pg_get_constraintdef`. That function deparses the stored tree, rather than
returning the original Alembic text. Its `ArrayCoerceExpr` and `RelabelType`
branches render explicit type coercions. These source paths explain the emitted
array cast in the archive. [pg_dump table CHECK query](https://github.com/postgres/postgres/blob/REL_18_6/src/bin/pg_dump/pg_dump.c#L9039),
[constraint deparser](https://github.com/postgres/postgres/blob/REL_18_6/src/backend/utils/adt/ruleutils.c#L2349),
[array coercion rendering](https://github.com/postgres/postgres/blob/REL_18_6/src/backend/utils/adt/ruleutils.c#L9148).

The original migration uses `IN`/`NOT IN` with untyped string literals. The
parser prefers the varchar left operand when choosing a common type, then
resolves the comparison through text operators. In the observed original trees,
this produces a varchar array wrapped in an array-wide text coercion. When the
dump's explicit `ARRAY[...]::text[]` is parsed, `transformTypeCast` passes the
target element type into `transformArrayExpr`, which coerces each element to
text. It therefore stores a text array with individual relabels. This is a
parse/deparse/reparse structural change, not merely pretty-print whitespace.
[PostgreSQL 18.6 IN transformation](https://github.com/postgres/postgres/blob/REL_18_6/src/backend/parser/parse_expr.c#L1066),
[explicit-array cast handling](https://github.com/postgres/postgres/blob/REL_18_6/src/backend/parser/parse_expr.c#L2578),
[per-element coercion](https://github.com/postgres/postgres/blob/REL_18_6/src/backend/parser/parse_expr.c#L2020).

For **each of C1–C9**, the source and original synthetic probe had one
`ArrayCoerceExpr`, one varchar `ArrayExpr` and one `CaseTestExpr` used for its
element relabel. The restored synthetic probe had no `ArrayCoerceExpr` or
`CaseTestExpr`; its single text `ArrayExpr` held one extra `RelabelType` per
literal. All other node classes, literal payloads, operator/function sequences,
ANY/ALL flags and input-collation sequences matched. C2's surrounding lifecycle
branches and C6's NOT-IN/CASE/threshold branches were unchanged. Original probes
used the frozen migration's actual `IN` syntax: reparsing O1–O9 as the original
probe would itself take the restore path and would be an invalid control.

## Semantic-equivalence argument

The following conditions are part of the conclusion's scope, not assumed for
arbitrary casts, types, SQL expressions or future PostgreSQL versions.

1. **Value-preserving element conversion.** Source and disposable catalogs
   showed `varchar -> text` has `castmethod='b'`, `castfunc=0`,
   `castcontext='i'`. The affected literals have varchar typmod `-1`; the new text
   values have no length restriction. No truncating typmod, domain check,
   collation change or user conversion function is introduced. PostgreSQL's
   catalog marks that conversion binary compatible; its executor can treat the
   array's per-element relabel as trivial. [18.6 cast catalog](https://github.com/postgres/postgres/blob/REL_18_6/src/include/catalog/pg_cast.dat#L279),
   [array coercion construction](https://github.com/postgres/postgres/blob/REL_18_6/src/backend/parser/parse_coerce.c#L870),
   [array coercion execution](https://github.com/postgres/postgres/blob/REL_18_6/src/backend/executor/execExpr.c#L1573).
2. **Identical constant vectors.** Each changed array contains only its displayed
   fixed, non-NULL scalar literals. Constructing the varchar array and applying
   that binary element conversion yields exactly the same text vector as
   converting those same elements before array construction. In the database,
   all nine resulting vectors compared equal, had type `text[]`, one dimension
   and lower bound 1. The argument also preserves element order and NULL bitmap;
   none of these particular vectors contains a NULL element.
3. **Identical predicates for every column value.** Both trees retain built-in
   `pg_catalog.=(text,text)` / `texteq` (operator 98, function 67), or for C6's
   NOT IN, `pg_catalog.<>(text,text)` / `textne` (531, 157). C6's integer equality
   remains `int4eq` (96, 65). These functions were observed strict and immutable.
   String comparisons retained input collation 100, the deterministic default;
   the integer comparison retained collation 0. PostgreSQL's deterministic text
   equality/inequality compares bytes, so a different locale name in the
   disposable cluster does not change these equality predicates. This does not
   authorize nondeterministic collations or different operators.
   [18.6 text equality and inequality](https://github.com/postgres/postgres/blob/REL_18_6/src/backend/utils/adt/varlena.c#L1632).
4. **Same three-valued result.** For any admissible non-NULL varchar value,
   identical text vector, operator and collation give the same ANY or ALL
   result. For a NULL left operand, strict operators over these nonempty arrays
   give UNKNOWN on both sides. This accounts for every scalar input, not just
   the examples tested. [IN, NOT IN, ANY and ALL NULL semantics](https://www.postgresql.org/docs/18/functions-comparisons.html).
5. **Unchanged expression context.** The identical predicate can be substituted
   into C2's unchanged AND/OR/IS-NULL branches and C6's unchanged OR/AND/CASE
   structure without changing their three-valued results. C2 depends only on the
   status predicates and timestamp NULLness, not timestamp magnitudes. C6 keeps
   the entire integer threshold expression, including the 80/100 constants,
   unchanged. This covers the full int4 domain and all admissible timestamps.
6. **Same constraint acceptance.** CHECK rejects FALSE and accepts TRUE or
   UNKNOWN. Separate original NOT NULL constraints continue to reject NULL
   required columns; they were not removed to establish equivalence. Hence equal
   three-valued expressions imply equal CHECK behavior in the same original
   schema. [CHECK and NULL behavior](https://www.postgresql.org/docs/18/ddl-constraints.html#DDL-CONSTRAINTS-CHECK-CONSTRAINTS).

The outcome for **every one of C1–C9 is verified equivalent under these pinned
conditions**. No differing or unresolved expression remains within that scope.
This is not a general SQL equivalence checker and does not approve acceptance of
other rendered forms. Outer-expression identity, constant-vector equality and
the binary-cast/operator facts are necessary to the argument; the samples alone
would not justify the conclusion.

### Per-expression behavior retained

C1, C3, C4, C5, C7, C8 and C9 retain exact membership in their displayed sets.
Case changes, extra whitespace, accents and unlisted values do not become new
allowed values under the observed deterministic collation.

C2 retains: planned requires neither timestamp; running requires start only;
succeeded/failed require both; cancelled requires finish and permits either start
NULLness. Other non-NULL status strings fail this isolated lifecycle expression. Other
original lifecycle/time-order constraints remain separate and unchanged.

C6 retains: the three inventory/primary/sensitivity contexts require a non-NULL
threshold equal to 80 for `primary_80`, otherwise 100. Other non-NULL contexts
make this isolated threshold expression TRUE; the separate context-membership
CHECK still limits allowed contexts. With NULL context, threshold 100 makes this
expression TRUE and the other tested thresholds produce UNKNOWN; the original
context NOT NULL independently rejects such rows. Equivalence does not change
the approved QC methodology or implement scientific processing.

## Executed synthetic checks

The private operator diagnostic used a fresh owned restore and temporary input,
original-CHECK and restored-CHECK tables. Relevant column types and NOT NULL
flags were copied from verified catalog metadata; unrelated required columns
and foreign keys were deliberately absent so each named CHECK could be observed
in isolation. Its original expressions came from the unchanged initial migration
and exactly reproduced O1–O9. The alternatives exactly reproduced R1–R9.

**702 paired truth evaluations and 306 paired INSERT attempts (612 inserts)
matched**, with no mismatch. These are diagnostic counts, not new pytest cases.

| Constraint | Truth pairs (TRUE / FALSE / UNKNOWN) | Paired INSERT attempts | Result |
|---|---:|---:|---|
| C1 | 23 (3 / 19 / 1) | 25 | Matching truth and SQLSTATE/acceptance |
| C2 | 198 (12 / 180 / 6) | 49 | Matching truth and SQLSTATE/acceptance |
| C3 | 33 (5 / 27 / 1) | 35 | Matching truth and SQLSTATE/acceptance |
| C4 | 18 (2 / 15 / 1) | 20 | Matching truth and SQLSTATE/acceptance |
| C5 | 28 (4 / 23 / 1) | 30 | Matching truth and SQLSTATE/acceptance |
| C6 | 308 (268 / 30 / 10) | 49 | Matching truth and SQLSTATE/acceptance |
| C7 | 28 (4 / 23 / 1) | 30 | Matching truth and SQLSTATE/acceptance |
| C8 | 38 (6 / 31 / 1) | 38 | Matching truth and SQLSTATE/acceptance |
| C9 | 28 (4 / 23 / 1) | 30 | Matching truth and SQLSTATE/acceptance |

The input partitions included every allowed literal, unlisted/empty/whitespace
strings, case variants, leading/trailing spaces, Unicode and combining marks,
NULLs and overlength strings. Lifecycle inputs covered all timestamp NULLness
combinations and +/-infinity values. Threshold inputs included NULL, int4 minimum
and maximum, -1, 0, 79, 80, 81, 99, 100 and 101. Paired inserts checked matching
acceptance or SQLSTATE `23514` (CHECK), `23502` (NOT NULL), `22001` (length).
The insert sample is bounded and includes repeated cases; the counts do not
claim exhaustive row enumeration.

A separate behavior-changing control compared text equality with equality after
`character(7)` truncation: artificial input `plannedX` failed the original
`planned` comparison but passed the altered one. This confirms why arbitrary
cast stripping/normalization is unacceptable. All temporary diagnostic changes
were rolled back. The restored cluster itself was subsequently disposed.

## Proposed strict compatibility design — not implemented

Recommend a **versioned per-constraint exact allowlist anchored to the existing
whole constraint-catalog hash**. Preserve `initial_schema_evidence.EXPECTED`
unchanged; no expected digest is to be regenerated from development.

1. Keep every existing literal target/mode/revision requirement, real-transaction
   and autocommit check, actual database/address/port check, PostgreSQL version,
   namespace/temp-schema checks, advisory lock, exclusive table locks and task
   seed comparison. Compatibility does not choose a database or bypass a lock.
2. Require the other **12 fingerprint categories** to equal the current frozen
   values, including types/lengths/defaults/collations, indexes and namespaces.
3. Independently pin the type/cast/operator/deterministic-collation properties
   used in this proof. Require built-in varchar/text/array identities, binary
   varchar-to-text conversion with no function, reviewed operator signatures,
   implementations, strictness and volatility. Do not generalize to domains,
   bpchar/char(n), custom functions or nondeterministic collations.
4. Freeze a small reviewed ledger keyed by exact public-schema table and
   constraint name for **only C1–C9**. Each entry contains the complete original
   and one verified alternative definition, required CHECK kind, validation and
   deferrability properties and related column types. Both allowed strings are
   literal reviewed values, not expressions rebuilt from a live target.
5. Require each key exactly once. Reject any entry with wrong association,
   property or definition. For a matching alternative only, substitute that
   entry's **complete frozen original row** in an in-memory comparison copy.
   No database DDL, catalog write or SQL-expression transformation is involved.
   Keep all other constraint rows byte-for-byte unchanged.
6. Hash the entire ordered comparison result with the **existing** canonical
   serialization and require the **original** `EXPECTED['constraints']` value.
   This retains exact comparison for every non-allowlisted CHECK, PK, FK,
   unique and NOT NULL entry and detects missing/extra rows. Do not omit rows,
   drop casts, collapse whitespace, reorder literals or ignore unknown CHECKs.
7. Preserve a fixed sanitized refusal on anything outside those literal forms.
   A newly emitted render form is a new review event, not automatic enrollment.

Before an implementation review, reproduce the full original catalog from the
frozen initial migration in isolated PostgreSQL 18.6 and verify it against the
existing digest. Derive the alternative ledger by an isolated **synthetic**
dump/restore and require exact agreement with the nine forms diagnosed here.
That is the provenance for proposed constants; development is not an oracle for
creating a newly approved expected fingerprint.

| Design | Security boundary | Review and maintenance cost |
|---|---|---|
| Versioned complete alternative constraint fingerprint | Accepts only the original and explicitly frozen full restored states; a mixed state is refused | Small implementation, but a digest alone hides which forms were approved; requires complete isolated provenance and a reviewed nine-row difference manifest |
| Exact nine-row allowlist plus original full-catalog hash | Accepts only individually verified literal alternatives; every remaining row is pinned by the original hash | Explicit names/properties/definitions expose the exception surface; more code and stronger mutation tests required |

The complete-alternative-hash approach has the narrower global-state policy.
The recommended allowlist is easier to audit per constraint and maintain without
adding opaque whole-catalog exceptions. Its deliberate trade-off is accepting
any combination of the nine independently verified forms (at most 2^9), not only
the two complete snapshots. Such combinations contain no unverified expression,
but this broader **known** set must be explicitly approved and tested. If review
requires only the single observed all-restored state, choose the versioned whole
alternative fingerprint plus its nine-row manifest instead. Neither option is
implemented or approved by this report.

## Required implementation tests — planned, not executed acceptance claims

The current guard still refuses the restored constraint digest. The following
acceptance expectations apply **only to a future separately approved design**;
the 702/306 semantic diagnostics did not run that implementation.

| Future test | Expected result / reason |
|---|---|
| Original isolated baseline, then read-only original development preflight | Accepted by original frozen evidence; no schema rewrite |
| Exact verified restored schema | Accepted only by the reviewed alternative path with all context checks |
| One changed CHECK predicate (`80` to `81`, added literal or widened OR) | Refused; exact definition mismatch |
| One missing CHECK | Refused; key/count or final original-catalog digest mismatch |
| One extra CHECK, including an otherwise TRUE CHECK | Refused; full-catalog digest mismatch |
| Different behavior-affecting cast, including character(7) truncation | Refused; not an exact ledger alternative |
| Changed varchar length/type, integer type, collation or NOT NULL | Refused by unchanged column fingerprint/context checks |
| Unknown, absent, multiple or already-upgraded Alembic revision | Refused by existing predecessor check |
| Drift in any of the other 12 fingerprint categories | Refused before compatibility can authorize a schema |
| Changed task seed value/count | Refused by unchanged exact task comparison |
| Invalidated or differently deferred CHECK, wrong name or table association | Refused by complete entry identity/properties |
| Changed PK/FK/unique/NOT NULL or a non-allowlisted CHECK | Refused by unchanged whole-catalog comparison |
| Any one of the nine entries present in both unexpected variants/duplicate keys | Refused; exactly one catalog entry per expected key |
| All permitted original/alternative combinations | Test the documented combination policy; no silent expansion |
| Real-transaction/autocommit, namespace, URL-query, actual address/port or version mismatch | Existing refusal remains active |
| Busy advisory/table lock, wrong literal destination or unsafe provided connection | Existing refusal remains active |
| Altered builtin cast/operator or nondeterministic collation | Refused by pinned semantic-context checks |
| Import/startup and absent explicit opt-in | No connection, DDL or migration |

Use mutations against complete baseline and restored fixtures. Exercise the
actual Alembic entry path and assert no persistent changes on refusal. Test
ordering/canonical serialization and the exact key/property comparisons, not
just a helper that returns True for a prepared string. No new scientific feature
or statistical test plan is authorized.

## Safe continuation and remaining limitations

After independent S2C-03D review, a separately authorized change can implement
the selected strategy and tests. Then repeat S2C-03C on a **fresh owned restore**
of the checksum-verified retained archive. Independently verify cluster identity,
marker and directory, non-5432 loopback port, predecessor revision, all 13 schema
categories under the reviewed policy, original metadata and five tasks. Exclude
other writers and verify the private migration role/grant plan.

Only the restored disposable target may then receive the exact reviewed
`s2c03_0001` transaction. Verify a genuine outer COMMIT, independent connection
visibility, 22 research/journal tables plus Alembic, preservation of all original
definitions/rows/tasks, seven new table constraints, repeat-application refusal,
unknown revision/schema drift refusal and an owned orderly restart. Recheck that
development remains `s2b01_0001`, the original test database is empty and its
service was unchanged; clean up only positively owned disposable infrastructure.
Return for a separate development-migration decision afterward.

The equivalence conclusion does not prove unrestricted SQL semantic equivalence,
future-version compatibility, nondeterministic/custom collation behavior,
role/ACL recovery, malicious-superuser resistance, crash/power-loss durability
or distributed database/filesystem atomicity. The proposed compatibility path
still needs implementation, mutation tests and independent security review.
The diagnostic leaves the approved guard, original 12 categories and frozen
constraint hash unchanged on disk.

## Retention, allocation and final verification

The retained backup was read only; its SHA-256 matched the private integrity
manifest before and after this task. Its approved retention remains **until
explicit user deletion authorization**. No archive, manifest or private backup
directory was rewritten, and no path or capability is included here.

The existing private setup record reports one unmarked no-data allocation from
S2C-03C. It lacks the original durable marker and allocation identity needed for
safe cleanup. **Ownership cannot be established to that standard from the
existing record.** This task did not attach to, inspect, delete or reset it.
Retain it for a separate operator-approved cleanup procedure; filenames and an
old traceback alone must not become deletion authority.

The ordinary configured PostgreSQL regression suite passed **304 tests, 0
failed, 2 skipped**, 306 collected, in **24.67 seconds**. The two skips remain the
Windows file-symlink privilege cases at `tests/test_private_storage.py:59`.
These are distinct from the semantic-diagnostic counts above.

Final read-only verification confirmed development remains at `s2b01_0001` on
the original cluster/startup identity with all frozen schema fingerprints
unchanged. The original PostgreSQL service was running with the same PID.
`stylometry_test` passed the empty-target guard with zero public tables after
regression. Streamlit startup returned HTTP 200; four modules, nine planned
stages and AppTest navigation were preserved. Only the temporary Streamlit
process was stopped. Working-tree and no-index report whitespace checks passed.

Only this new report is added by S2C-03D; the pre-existing untracked S2C-03C
report is preserved. Approved application modules, initial/successor migrations,
contracts, methods, dependencies and guard/evidence files remain unchanged.
No commit, push, merge, development migration, S2C-04 work or rerun of the
historical 25-check S2C-03B live harness occurred.

**Stop at Approval Gate S2C-03D. Review this diagnosis and design before any
compatibility implementation or renewed restored-database migration rehearsal.**
