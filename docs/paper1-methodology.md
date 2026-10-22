# DASET Paper 1 specification -- S2A review draft

Study: **A Data Science Approach to Measuring Stylometric Stability and
Variability in EFL Student Writing**. Purpose: investigate stylometric stability
and variability across EFL writing tasks. Formal research questions and exact
statistical estimands require the approved paper/protocol.

## Evidence and authority

The facts below are confirmed **as supplied in the user's S2A task context**,
not independently checked against the paper, archive, code, or source documents.
No source Drive files were opened or loaded. All counts are reported reference
values, not application results, acceptance tests for an invented dataset, or
evidence of completed stages. The machine-readable references are in
`src/stylometry/paper1.py`. This document records the supplied methodology; it
does not revise or fill gaps in the approved scientific methodology.

## Task definitions

| Code | Genre | Form |
|---|---|---|
| T01 | Narrative | Paragraph |
| T02 | Descriptive | Paragraph |
| T03 | Expository | Paragraph |
| T04 | Persuasive | Paragraph |
| T05 | Persuasive | Essay |

Task prompts, timing, collection conditions, ordering, scaffolding, and permitted
resources are not supplied. These genres/forms do not substitute for prompt texts.

## Corpus layers and reported values

| Layer | Reported students | Reported texts | Supplied selection information |
|---|---:|---:|---|
| Archived source inventory | 46 pseudonymous profiles | 200 nonempty | 230 potential task slots; inventory PASS uses 100 words |
| Primary analytical corpus | 35 | 163 | Minimum 80 words; at least four eligible tasks per student; duplicate screening |
| 100-word sensitivity corpus | 24 | 110 | Minimum 100 words; remaining construction details unresolved |
| Balanced five-task corpus | 23 | 115 | Five tasks per student; relationship to other thresholds/cohorts unresolved |

The source inventory and analytical corpus are different populations of records.
Inventory PASS at 100 words is not primary eligibility at 80 words. A text of
80--99 words could meet the reported primary length criterion even if it does
not receive inventory PASS; other eligibility decisions still apply. Do not
infer that all 30 remaining source slots are one specific kind of missingness.
The denominators alone cannot explain every exclusion or reconstruct membership.

Four cross-student duplicate task pairs involving two anonymized profiles were
reported, with duplicated texts excluded. Pair identities, whether pairs share
members, and which side(s) were removed are unresolved. Do not infer eight
distinct excluded samples or remove entire profiles from this statement.

There are 43 reported engineered features and 24 primary analysis features.
Neither names, formulas, feature families, units, nor the primary subset have
been supplied. The feature registry remains empty and incomplete.

## Process specification and unresolved boundaries

The nine existing stages remain unchanged. No stage is executed by S2A.

| Stage | Confirmed scope | Required before reproducible execution |
|---|---|---|
| 1 Data preparation | Source and analytical layers must be distinguished | Authorized inventory, slot mapping, collection/consent documentation, corpus versions |
| 2 Text extraction and cleaning | Source provenance and versioned clean text are needed | Approved extractor, segmentation, normalization, encoding, cleaning order and rules |
| 3 QC and selection | Primary 80 words / four tasks; duplicate exclusions; separate inventory 100 PASS | Exact tokenizer, duplicate definition and adjudication, missingness codes, operation order, cohort memberships |
| 4 Feature engineering and transformation | 43 engineered / 24 primary features reported | Authoritative registry, formulas, implementations, resources, transforms, missing/zero rules |
| 5 Exploratory data analysis | Planned workflow stage | Approved summaries/plots, groups, transformations, handling of missing data |
| 6 Statistical stability modeling | Planned stability investigation | Exact models/estimands, ICC formulation if used, effects, intervals, assumptions, software |
| 7 Robustness and sensitivity analysis | 100-word and balanced five-task corpora reported | Exact construction rules, comparison plan, robustness model settings |
| 8 Results interpretation | Planned workflow stage | Approved interpretive framework, uncertainty and multiplicity conventions |
| 9 Conclusions | Planned workflow stage | Validated outputs and supported claims |

No tokenization, duplicate similarity threshold, extractor, cleaning procedure,
feature formula, transformation, model, seed, or analysis result is selected here.
Order of duplicate removal, word counting, and writer eligibility must be obtained;
these operations need not commute. Do not infer sensitivity membership from the
primary corpus or balanced membership from the 100-word corpus.

## Proposed application metadata behavior (not scientific rules)

Use immutable validated contracts, UUID pseudonyms, timezone-aware timestamps
normalized to UTC, explicit configuration versions/hashes, full Git commit IDs,
dirty-tree indicators, and environment lock hashes. UUIDs are opaque references;
they do not prove that an object has been anonymized. Real metadata and hashes
can still be sensitive and belong in approved private storage.

Raw source bytes, extracted bytes, and each clean-text version have separate
SHA-256 hashes. These byte hashes do not normalize text, define equality for
scientific duplicate screening, or prove semantic equivalence. The digest covers
the exact externally stored bytes. Encoding and canonical text rules remain
unresolved until the approved extraction/cleaning specification is obtained.

Each logical sample represents one corpus/writer/task slot, including missing
writing. Repeated extraction attempts append events. Clean versions form a
linear, append-only chain per successful extraction/sample, with versions starting
at one. Re-extraction creates a separate chain; snapshots pin the exact derivation
UUID and never implicitly select a latest version. The S2A proposal deliberately
does not overwrite history. See the schema proposal for the design to review.

QC receipts record context, target, exact text version, supplied count, tokenizer
reference, reasons, private evidence, configuration, and timestamps. They do not
perform counting or duplicate detection. `not_evaluated` means no decision;
`review_required` means unresolved evidence/method; `excluded` needs reasons;
`pass` means the supplied decision passes that named context only. Reason codes:
`missing_text`, `below_word_threshold`, `duplicate_text`,
`insufficient_eligible_tasks`, `extraction_failed`, `unresolved_method`.
Sample and writer decisions are separate. These are proposed application codes,
not claims about the archive's original classification vocabulary.

Analytical snapshots pin exact sample membership, clean versions/hashes, and both
sample and writer PASS receipts under the same cohort/configuration. Inventory
PASS receipts cannot admit analytical samples. Snapshots do not auto-fill to the
reported counts or automatically turn a reference value into a measurement.
Per-writer member counts must match the supplied eligible-task receipt: this is
an internal consistency check, not an implementation of the selection procedure.
The contract checks referential and internal consistency; it cannot validate the
underlying private evidence or establish that a scientific decision is correct.

Snapshot manifest encoding is an application proposal: JSON from the contract's
JSON serializer excluding only `manifest_sha256`, UTF-8, sorted object keys,
compact separators, ASCII escaping, no NaN, members sorted by sample UUID string.
It covers snapshot ID/version/corpus/context, creation time, reproducibility
metadata, and member references/hashes/QC IDs. Immutable QC/extraction/provenance
records and referenced configuration bytes must be archived alongside a snapshot;
the manifest does not embed or cryptographically seal those complete records.
Configuration hashes refer to exact archived configuration bytes; their format
must be versioned. A full snapshot export and its byte hash should be archived
privately before execution. A later schema must prevent updates to sealed records.

Runs pin snapshot ID/hash, experiment version, stage, configuration, code commit,
environment lock hash, creation/start/finish times, lifecycle status, and output
provenance references. A planned run has no execution timestamps or outputs.
S2A supplies contracts and synthetic fixtures only; no real run or snapshot exists.

## Approval Gate S2A

Review contracts, proposed persistence constraints, and the missing-information
register before importing or implementing scientific methods. The user has
authorized one review commit and push of `feature/paper1-data-contracts` only;
publication of this review branch does not approve the scientific specification.
No database tables, migrations, ETL, feature extraction, or analytical experiments
are created or run by this task. Scientific execution remains blocked on sources
and approval; contract development/testing does not assert methodological approval.
