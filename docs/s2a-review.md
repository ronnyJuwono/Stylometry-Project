# Approval Gate S2A: development handoff

Baseline: `fb90bca` on `main`. Working branch: `feature/paper1-data-contracts`.
The S2A review commit is `d3166b964b66f8f5a16bb55feb690caf70b53c9d`
(`feat: define paper1 research data contracts`). The user has additionally
authorized S2A.1: a documentation-only correction commit and push on this branch.
Main remains unchanged; no merge is authorized. Stop for review after publishing
the correction. This authorization does not approve a final scientific protocol,
source access, or persistence implementation.

## S2A.1 documentation correction

Only `docs/paper1-methodology.md`, `docs/paper1-open-questions.md` and this handoff
are corrected. The existing manuscript draft is a project research source, not
an approved final protocol. The user's S2A.1 correction establishes that the
draft documents cleaning rules, exact-duplicate exclusion followed by reapplication
of the four-task rule, the 23 five-task / 12 four-task primary composition,
Spearman correlation, standardized PCA, random-intercept mixed-effects models,
writing task as a fixed effect in adjusted models, and sensitivity analyses.

Source reference: `P1-MANUSCRIPT-DRAFT`, **A Data Science Approach to Measuring
Stylometric Stability and Variability in EFL Student Writing**. Validated-copy
reference, version/date, SHA-256 and section/page citations: **TBD**. The actual
copy has not been independently inspected in this correction. The updated
specification separates documented draft methods, unresolved implementation
details, and evidence unavailable to this review. Reported counts remain
references, not application-computed results. No missing formulas, tokenization
rules, duplicate implementations or feature definitions are invented.

A future dissertation design note flags repeated submissions/authored drafts
as a possible extension to the one-writer/task/corpus logical sample model.
Processing derivations must not substitute for submission identity. Contracts,
the schema proposal and analysis code remain unchanged by S2A.1.

## File list

| File | Change |
|---|---|
| `src/stylometry/contracts.py` | New validated metadata contracts and closed-graph consistency checks |
| `src/stylometry/paper1.py` | New task mapping, separate thresholds and explicitly reported reference figures |
| `docs/paper1-methodology.md` | New specification separating supplied facts, unknown methods and engineering proposals |
| `docs/paper1-open-questions.md` | New discrepancy register and required source-material checklist |
| `docs/postgresql-schema-proposal.md` | New proposed tables, relationships and enforcement boundaries; not applied |
| `docs/s2a-review.md` | This handoff |
| `tests/conftest.py` | New deterministic artificial metadata-only graph fixture |
| `tests/test_contracts.py` | New positive/negative contract validation tests |
| `README.md` | Added S2A navigation, validation instructions and approval boundary |
| `pyproject.toml` | Added Pydantic runtime validation dependency |
| `uv.lock` | Locked Pydantic and its dependencies; existing dashboard dependencies retained |

## Proposed schema and tested contracts

Core entities: provenance, corpus, anonymized writer, task, source document,
logical text sample, extraction event, clean-text derivation, QC evaluation,
dataset snapshot and experiment run. Relational association tables hold QC
reasons, related duplicate samples, snapshot members and run outputs.
The full column/FK/CHECK proposal is in the schema document. No SQL migrations
or ORM table definitions were added.

Contracts are strict and frozen, reject unknown fields, use UUID references and
timezone-aware UTC timestamps, and validate digests and run lifecycle metadata.
Graph validation covers missing references, source/sample corpus consistency,
writer/task uniqueness, successful extraction lineage, sequential clean versions,
snapshot hashes and membership, matching analytical PASS receipts, configuration
consistency, writer task coverage and run snapshot pins. Unknown private methods
remain opaque references, not implied approved implementations.

QC supports missing text, below-threshold text, duplicate exclusions, and
insufficient-task writer exclusions, plus unresolved methods/extraction failures.
The inventory 100-word classification cannot substitute for primary 80-word QC.
No tokenizer, extractor, duplicate detector, feature formula, or statistical model
was implemented. Snapshot manifest hashing is metadata processing only.

## Validation

Environment: existing `.venv`, Python 3.13.14; Pydantic 2.14.1 installed with
`uv sync --extra dev`. No other direct dependency changed.

Full command: `.\.venv\Scripts\python.exe -m pytest`.
Result: **39 passed** (30 new contract cases plus 9 existing tests), including
all four navigation modules and all nine unchanged workflow stages.
Streamlit started on temporary loopback port 8502, health returned **HTTP 200**,
and that verification process was stopped. `git diff --check` passed.
For S2A.1, the existing complete suite was rerun: **39 passed**. Only the three
documentation files listed above are included in the correction.

Fixtures contain only artificial metadata, dummy counts, synthetic digests,
zero/deterministic IDs and method references. They do not contain student text,
identities, actual samples, recomputed paper outcomes, or live source locators.
No source files were fetched from Drive, no database was contacted, and no
tables or analytical experiments were created/executed.

## Required review and next steps

1. Review contracts, manifest conventions, append-only lineage, proposed schema
   and database enforcement strategy. Metadata validation does not authenticate
   evidence, verify private object bytes or implement storage access controls.
2. Validate the existing manuscript draft/supplements using the source-reference
   placeholders, without treating the draft as an approved final protocol. Check
   documented methods against versioned code and obtain the still-unresolved
   inventory/cohort/exclusion ledger, exact-duplicate implementation details,
   extraction/cleaning/tokenizer code mapping, complete feature registry/subset,
   analysis settings/environment and ethics/access evidence.
3. Resolve the register, especially corpus membership reconciliation, duplicate
   retention choices, remaining selection details, sensitivity/balanced rules and
   exact statistical settings. Preserve the documented post-duplicate four-task
   reapplication; do not infer membership or settings from reported totals.
4. Publish only the explicitly authorized S2A.1 documentation correction on the
   feature branch after tests and staged-content safety checks pass. Stop for
   review. Obtain a separate scope/approval for future private source
   access, persistence or scientific implementation. Do not merge into main.
