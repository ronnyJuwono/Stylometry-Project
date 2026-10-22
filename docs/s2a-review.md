# Approval Gate S2A: development handoff

Baseline: `fb90bca` on `main`. Working branch:
`feature/paper1-data-contracts`. The user has authorized one review commit named
`feat: define paper1 research data contracts` and a push of this feature branch
only. Main remains unchanged; no merge is authorized. Stop for ChatGPT review
after publishing the branch. This authorization does not approve scientific
methods, source access, or persistence implementation.

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

Fixtures contain only artificial metadata, dummy counts, synthetic digests,
zero/deterministic IDs and method references. They do not contain student text,
identities, actual samples, recomputed paper outcomes, or live source locators.
No source files were fetched from Drive, no database was contacted, and no
tables or analytical experiments were created/executed.

## Required review and next steps

1. Review contracts, manifest conventions, append-only lineage, proposed schema
   and database enforcement strategy. Metadata validation does not authenticate
   evidence, verify private object bytes or implement storage access controls.
2. Obtain the authoritative manuscript/supplements/protocol, redacted inventory
   codebook and private cohort/exclusion ledger, duplicate adjudication rules,
   extraction/cleaning/tokenizer specifications, complete feature registry and
   primary subset, versioned analysis code/environment, and ethics/access plan.
3. Resolve the register, especially corpus membership reconciliation, duplicate
   retention choices, selection order, sensitivity/balanced rules and exact
   statistical specifications. Do not infer these from reported totals.
4. Publish only the explicitly authorized review commit on the feature branch,
   after the complete tests and staged-content safety checks pass. Stop for
   ChatGPT review. Obtain a separate scope/approval for future private source
   access, persistence or scientific implementation. Do not merge into main.
