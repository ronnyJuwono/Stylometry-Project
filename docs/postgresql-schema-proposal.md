# PostgreSQL relational schema proposal -- not applied

S2A review artifact only. No DDL, ORM mappings, database connection, migration,
table creation, extension, or production database is included. Implement the
schema only after review and a separate authorization. UUID generation strategy
is an implementation choice; fixtures use deterministic artificial UUIDs.

All IDs are UUID primary keys. Required columns are NOT NULL unless marked `?`.
Timestamps use `timestamptz`; byte digests use `char(64)` with lowercase hexadecimal
CHECKs; code commits use checked 40/64-character lowercase hexadecimal text.
Opaque private references are UUIDs, never URLs, paths, credentials or identities.
Delete behavior should be RESTRICT for referenced research records; no cascaded
deletion of evidence. No raw text or identity mapping is stored in these tables.
The private object store is separately governed and not part of the public repo.

## Tables and relationships

| Proposed table | Principal columns | Relationships and constraints |
|---|---|---|
| `provenance` | id, recorded_at, evidence_ref, evidence_sha256 | Immutable evidence locator/hash; private object bytes verified by future storage service |
| `corpus` | id, version text, created_at, provenance_id | FK provenance; a versioned source collection, not a claim of analytical inclusion |
| `writer` | id, corpus_id | FK corpus; UUID pseudonym only; UNIQUE(id, corpus_id) supports composite FKs |
| `task` | code text PK, genre text, form text | Exactly T01--T05 with the supplied genre/form mapping; no invented prompts |
| `source_document` | id, corpus_id, private_object_ref, byte_sha256, media_type text, provenance_id, acquired_at | FK corpus/provenance; UNIQUE(id, corpus_id); multiple documents per corpus; no unique hash constraint (identical sources may exist) |
| `text_sample` | id, corpus_id, writer_id, task_code, provenance_id | FK corpus/task/provenance; composite FK writer_id/corpus_id; UNIQUE(corpus_id, writer_id, task_code); missing slot is still a row |
| `extraction_event` | id, sample_id, source_document_id, source_span_ref, method_ref, provenance_id, started_at, finished_at, status text, extracted_object_ref?, extracted_byte_sha256?, reproducibility columns | FK sample/document/provenance; source and sample in same corpus; end >= start >= source acquisition; success requires both output fields, failure requires neither |
| `clean_text_derivation` | id, sample_id, extraction_event_id, parent_derivation_id?, version integer, private_object_ref, byte_sha256, method_ref, provenance_id, created_at, reproducibility columns | FK sample/extraction/provenance/parent; UNIQUE(sample_id, extraction_event_id, version); positive version; v1 has no parent, subsequent versions reference immediately previous version of same sample/extraction; successful source event only; timestamp >= input |
| `qc_evaluation` | id, sample_id?, writer_id?, context text, status text, derivation_id?, word_count?, word_threshold?, tokenizer_method_ref?, eligible_task_count?, minimum_eligible_tasks?, evidence_ref?, provenance_id, evaluated_at, reproducibility columns | Exactly one sample/writer FK; maps contract target_kind/target_id to XOR columns; count >= 0; task count 0--5, minimum 1--5; FK derivation must match sample; timestamp >= derivation |
| `qc_reason` | qc_id, reason_code text | Composite PK(qc_id, reason_code); FK QC; checked vocabulary in contracts; no duplicate reasons |
| `qc_related_sample` | qc_id, related_sample_id | Composite PK; FK QC/sample; counterpart differs from target and shares corpus; duplicate evidence requires counterparts plus evidence_ref; no assumed similarity formula |
| `dataset_snapshot` | id, corpus_id, version text, context text, created_at, manifest_sha256, reproducibility columns | FK corpus; analytical contexts only; immutable membership; reported totals are not CHECK constraints |
| `snapshot_member` | snapshot_id, sample_id, derivation_id, clean_byte_sha256, sample_qc_id, writer_qc_id | PK(snapshot_id, sample_id); FK snapshot/sample/derivation/QC; exact clean hash and correct sample/writer PASS receipts under same context/config; sample corpus must match snapshot |
| `experiment_run` | id, experiment_version text, snapshot_id, snapshot_manifest_sha256, stage_number integer, status text, created_at, started_at?, finished_at?, reproducibility columns | FK snapshot; hash pinned; creation >= snapshot; stage 1--9; lifecycle timestamp constraints from contracts |
| `run_output` | run_id, provenance_id | Composite PK; FK run/provenance; planned runs have no outputs |

The embedded **reproducibility columns** are: contract_version,
configuration_version, configuration_ref, configuration_sha256, code_commit,
working_tree_dirty boolean, environment_lock_sha256. Private configuration and
method references intentionally do not require local database rows; future
storage access must verify their existence and bytes. This is a boundary of the
proposal, not an implemented resolver.

## QC and snapshot constraints

Context CHECK vocabulary: `source_inventory_100`, `primary_80`, `sensitivity_100`,
`balanced_five_task`. Status vocabulary: `not_evaluated`, `pass`, `excluded`,
`review_required`. Reason vocabulary and validation semantics are documented in
the methodology and `QCEvaluation`. Primary threshold is 80, inventory/sensitivity
threshold is 100; balanced threshold is unresolved and must be explicitly supplied
from an approved configuration before a balanced sample can pass. Primary writer
minimum is four; balanced writer minimum is five. Sensitivity writer minimum is
not inferred. Do not infer an eligible writer from a length-only sample PASS.

Pass/unassessed receipts have no exclusion reasons; excluded/review receipts need
reasons. Word counts require exact derivation and tokenizer reference; below-word
reason requires count < threshold. Missing-text receipts have no count/derivation.
Writer-only task counts and sample-only measurements cannot be interchanged.
Duplicate decisions need private evidence; the database does not infer duplicates
from content hashes. Keep missing, failed extraction, and short text distinct.

Every included snapshot sample references both a sample PASS and writer PASS.
Inventory context is prohibited for analytical snapshots. All members of one
writer use the same writer decision; membership satisfies its recorded task
minimum and matches its recorded eligible-task count. A snapshot hash covers the
ordered manifest described in the methodology.
No live file reads or analytical selection algorithms are used by the contracts.

## Enforcement plan and limitations

Use ordinary FKs/composite FKs, UNIQUEs and CHECKs for local invariants. Cross-row
checks (parent version increment, source corpus consistency, status/reason joins,
receipt context/version consistency, writer task coverage and lifecycle outputs)
need transaction-level application validation plus deferred constraint triggers
or a reviewed transactional sealing operation. PostgreSQL CHECK expressions alone
cannot enforce these joins. `ResearchBundle` is the current in-memory closed-graph
validation boundary; it does not replace database integrity or object verification.
It also rejects UUID reuse across record types. If retained after review, enforce
that namespace rule through a shared record-ID registry or transactional validation;
independent table primary keys alone do not guarantee cross-table uniqueness.

At sealing, lock the snapshot/membership transaction, validate the entire graph,
archive the canonical manifest, and freeze referenced receipts/derivations/config
evidence. Use append-only versioning and restricted update/delete privileges.
Revocation/correction should create new records and snapshots rather than mutate
sealed history. These persistence controls are proposed, not implemented.

Indexes recommended after review: sample(corpus_id, writer_id, task_code),
source_document(corpus_id), extraction_event(sample_id, started_at),
clean_text_derivation(sample_id, extraction_event_id, version),
QC(target/context/evaluated_at), snapshot(corpus_id, context, created_at),
experiment_run(snapshot_id, created_at). Add only those supported by actual
queries. Real record UUIDs, digests and membership can still be sensitive; neither
metadata nor database backups are automatically safe for public Git.
