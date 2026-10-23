# Multi-study data architecture — proposal only

S2C-02 design artifact. No ORM table, migration, schema, task mapping or S2A
contract is changed. Baseline: `9113e21606438dbee965721be5a5a33515e52326`.
Use one database per environment (`stylometry_dev`, isolated `stylometry_test`,
future production separately approved), not a database per paper. This proposal
is not a claim that a study registry or analytical result store exists today.

## Recommended ownership model

Introduce a future UUID `study` registry with a stable code (P1/P2/D1), versioned
protocol/evidence references, provenance and approval status. A study is not a
corpus, configuration or execution. Bind corpora to studies; datasets/snapshots
pin exact corpus/unit/derivation/receipt versions. Unresolved protocol details
remain explicit, not inferred from a study code or reported publication totals.

| Proposed common entity | Relationships and version boundary |
|---|---|
| Study | Owns corpora, study-local slot definitions, configurations, experiments and feature-set memberships |
| Corpus / corpus version | Study FK; immutable collection versions with provenance; no reported total as a CHECK |
| Authorship entity | Individual or collective pseudonym; study-scoped relationships; identity mappings remain external |
| Authorship membership / contribution | Explicit group membership and document contribution receipts, not an assumption that every author wrote every section |
| Document / source object | Versioned physical source reference, exact byte digest, media type and provenance; contents external |
| Writing unit / submission | Logical authored submission/draft or document unit, separated from processing derivations |
| Writing sample / sample span | Supplied task or section/region mapping to a source unit; extraction/clean versions remain separate |
| Dataset version / snapshot membership | Pins exact samples, clean hashes and approved eligibility receipts; never an implicit latest selection |
| Processing configuration | Version/hash, private parameter reference, approved method specification and environment/code evidence |
| Experiment / operation run | Study/corpus and optional dataset inputs; dependency/output receipts, lifecycle and immutable rerun identity |
| Feature definition / feature set | Versioned authoritative definitions, units, resources and study-specific membership; no formulas invented here |
| Feature measurement | Definition/version + exact sample derivation/hash + run/configuration; later approved implementation only |
| Statistical model / result | Versioned approved model specification, input feature snapshot and execution; structured results plus external artifact refs |
| Artifact / provenance | Opaque external UUID/hash/type, generating run and complete evidence chain; no writing or paths stored as identifiers |

For new tables, use `study_id` FKs and composite ownership keys where an object
is directly study-owned; enforce same-study joins through composite FKs or a
reviewed transaction/sealing service. A corpus FK can convey ownership for
legacy P1 records until an additive migration supplies explicit study ownership.
Do not add inconsistent duplicate study columns without their matching constraints.
Cross-study reuse requires an explicit reviewed association/provenance policy,
not silent sharing or ID reuse. Schemas alone are not authorization boundaries;
roles, application policy and potentially reviewed RLS remain separate work.

## Study-specific semantics

| Study | Preserve / extend | Do not assume |
|---|---|---|
| P1 DASET | Existing individual writer, one logical writer/task/corpus slot, exact T01–T05 mapping; separate source/primary/sensitivity/balanced QC contexts | No repeated authored drafts squeezed into clean-text version chains; reported counts are not database constraints |
| P2 paper sections | Explicit document, section-definition/span and authorship/contribution relationships; group entities and multiple documents per author | No five-task grid, one-author-per-section rule, fixed section list, contribution weights or P1 thresholds |
| D1 dissertation | Explicit submission/attempt and authored-draft lineage, reference categories, many reference objects and target/reference associations | No single submission per task, automatic reference category, fixed number of references or unapproved personalization/verification metric |

The implemented `SyntheticInventory` is a separate planning representation:
explicit authorship entities, writing units and study-supplied slot codes. P1
uses exactly five tasks and one task collection per individual author. P2 uses
document-section units; D1 uses submission/reference units and supplied categories.
Repeated D1 units can reference earlier units without pretending they are
processing derivations. These relationships are not persisted as nonexistent
columns in the current P1 SQL schema. Missing/unresolved statuses and source-slot
links are retained in private synthetic registration receipts, not mapped to QC.

## Schema alternatives

1. **Recommended initially: shared tables in `public`.** Preserve S2B references,
   existing search paths, migration safety and contracts while introducing a
   reviewed additive study registry and generic-unit tables. `public` is a
   PostgreSQL namespace, not permission to expose private metadata publicly.
2. **Future `core` schema:** useful when generic entities and ownership rules
   stabilize. Requires qualified names, migration tooling, permissions and
   compatibility-view/API tests. Moving tables now creates risk without a proven
   query/security benefit. Treat a move as a separate reviewed migration.
3. **Per-study schemas:** justify only for actual study-specific structures,
   lifecycle/permission needs or distinct analysis types. Keep common ownership
   and evidence shared; do not duplicate the entire pipeline per study.
4. **Rejected as the primary design:** databases per paper or table-name prefixes.
   They duplicate common definitions, complicate cross-study provenance and
   migration/test administration, and do not themselves enforce authorization.

## Future migration strategy

Inventory real existing metadata privately before any migration; do not assume
all deployments are empty because this development target contains only tasks.
Use expand/backfill/validate/contract with backups and a tested rollback/recovery
plan. Add a study registry and nullable ownership links first; backfill existing
P1 ownership only from reviewed evidence. Validate references and ownership,
then enforce NOT NULL/composite FKs when justified. Add generic authorship/unit/
submission/section structures alongside legacy P1 records rather than widening
or reinterpreting `writer`/`text_sample` without approval.

Retain the S2A serialized contracts and P1 task lookup through explicit adapters
and, where useful, compatibility views. Do not rename T01–T05 or reinterpret
P1 clean derivations as student-authored drafts. Introduce new versioned generic
contracts for P2/D1 after review. Validate old JSON round trips, hashes, lineage,
snapshot pins and constraints against representative synthetic migrations.

An early pipeline operation can exist before an analytical dataset snapshot.
The current S2A `ExperimentRun` requires a snapshot, so do not manufacture one
to register inventory. A future operation-run representation must support
pre-snapshot inputs explicitly; use existing experiment runs only when their
snapshot/stage contract actually applies. S2C-02's synthetic runner receipts
are private/in-memory engineering records, not new SQL run rows.

Deferred decisions: group authorship/contribution semantics; P2 section spans;
D1 submission/reference ownership and privacy; feature registry and subsets;
protocol/method validation; cross-study reuse; sealing/revocation; retention;
and pre-snapshot run persistence. No scientific or migration approval is implied.

## S2C-03 review increment

The [durable-operation draft](s2c03-durable-operations.md) now proposes a narrow
seven-table journal with study/corpus ownership and pre-snapshot operation records.
It does not implement the wider P2/D1 schema above or change S2A/P1 semantics.
Its additive revision is prepared and tested only in isolated rollback fixtures;
it has not been applied to development. See the separate
[initialized-upgrade safeguards](s2c03-migration-safety.md).
