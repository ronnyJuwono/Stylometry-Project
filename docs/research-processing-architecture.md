# Research processing architecture — S2C-02

Research operations are Python modules. Streamlit remains the unchanged interface;
it does not import/run the new workflow on startup. No scientific stage is
implemented, selected, measured or marked complete by this foundation.

## Module boundaries

| Package/module | Implemented here | Future work |
|---|---|---|
| `pipeline/inventory.py` | Strict synthetic planning graph, completeness and logical-slot validation, counts, representable P1 adapter | Separately authorized real inventory/import and generic SQL mapping |
| `synthetic_publishing.py` | Owned temporary Windows workspace, bounded artificial-byte publication, locking, receipts, verified reads and retry | Persistent root provisioning, process-restart recovery, production write/import and other platforms |
| `pipeline/registration.py` | Synthetic P1 SQL registration/reconciliation in an existing isolated test transaction | Reviewed durable coordination/outbox and new study/unit schema |
| `pipeline/interfaces.py` | Typed scientific input/output and unavailable extraction/cleaning/QC/feature entry points | Actual validated methods in dedicated modules after source and protocol approval |
| `analysis/interfaces.py` | Unavailable descriptive/correlation/PCA/mixed-effects/ICC/sensitivity families | Approved formulas, settings, resources and numerical validation |
| `experiments/configurations.py` | Versioned execution plan, input/configuration references and dependencies | Approved parameter schemas and durable pre-snapshot run representation |
| `experiments/runner.py`, `results.py` | Synchronous synthetic inventory lifecycle and append-only in-memory receipt history | Real stage execution, durable run history and comparisons |
| `pipeline/demo.py` | Independent artificial-byte/inventory demonstration; no SQL or Streamlit | CLI/product flows only after review |
| Existing `storage.py`, `private_filesystem.py`, `persistence.py`, `models.py` | Reused unchanged | No relocation or schema changes in S2C-02 |

Family interfaces are consolidated instead of adding many empty modules with
pretend implementations. Later scientific modules can implement `ResearchStage`
and return `StageOutput`; today every scientific dispatcher raises
`StageUnavailable`. There are no zero-filled feature vectors, placeholder model
results, tokenizers, word counters, duplicate-text screens or statistical calls.

## Dependencies and evidence

The future dependency chain is explicit: source inventory/provenance → successful
extraction/span mapping → versioned cleaning → supplied/approved QC receipts and
dataset selection → authoritative feature definitions and measurements → pinned
analysis inputs → approved statistical/sensitivity runs → generated artifacts and
interpretation. Selection details remain those in the existing methodology and
open-question register; this sequence does not introduce an algorithm or parameter.

`StageInput` carries study/corpus/snapshot IDs, exact object references, method
and parameter references, a version and existing `Reproducibility`. `StageOutput`
specifies external output/provenance/receipt references. Actual method approval,
parameter-byte integrity and dependency availability must be checked by future
implementations; typed UUIDs alone do not establish those facts.

`ExecutionPlan` uses an explicit operation, UUID, dependency-run IDs, timestamps
and reproducibility evidence. Only `synthetic_inventory` executes. Its input
study/corpus/version must match the validated inventory; object/snapshot inputs
are refused because this operation does not consume them. Dependencies must be
successful runs in the current runner history. A future durable dependency graph
needs authenticated receipts and cycle/revocation policy; no scheduler or queue
is added. A real scientific operation fails as unavailable, not as a fake success.

Receipt lifecycle is planned → running → succeeded/failed; planned synchronous
runs can also be cancelled. Start/finish chronology is validated. Results exist
only for a successfully hashed synthetic inventory operation. Failure codes are
fixed engineering labels, not captured OS errors or scientific results. Earlier
receipts are preserved in memory; a rerun needs a new run UUID. History is not
automatically saved in PostgreSQL or claimed to survive process exit.

Archive exact inputs/configuration bytes and hashes, provenance, approved method
versions, code commit and dirty flag, lock/environment digest, timestamps and
outputs for future real runs. S2C-02 publication/registration receipts pin their
supplied reproducibility metadata and input manifests. The demo records actual
repository/lock version and timestamps; configuration/evidence UUIDs are clearly
synthetic stubs, not resolved research evidence or approved protocols.

## Independent Python execution

```powershell
.\.venv\Scripts\python.exe -m stylometry.pipeline.demo
```

This command creates a fresh temporary synthetic workspace, constructs a complete
five-slot P1 inventory, publishes artificial bytes, verifies retrieval, executes
only the synthetic inventory summary and disposes its scratch files. It prints
metadata/counts only, never file contents or absolute storage paths. It does not
read a real private root or contact PostgreSQL. The test suite also exercises
P2 group/section and D1 repeated-unit/reference planning; the demo is not a P1
dataset, eligibility calculation or reproduction of reported paper totals.

For explicit synthetic SQL orchestration, pass a validated `RegistrationRequest`,
matching `PublicationPlan` objects and a `SyntheticWorkspace` to
`register_synthetic_inventory` with an active `stylometry_test` Connection
transaction. Use the approved test fixture so schema and rows are rolled back.
Do not run migrations on `stylometry_dev` or point this API at it. Registration
returns `staged_in_caller_transaction`; it does not commit the caller's transaction.
Roll back the synthetic SQL transaction before disposing its temporary workspace.

## Future UI, reprocessing and comparison

Streamlit should submit a validated immutable execution request to a Python
service/runner, render returned receipts and show unavailable methods explicitly.
Database/file access remains opt-in per operation; a dashboard navigation event
must not execute a stage. Authentication and entitlements need a separately
reviewed host policy. The UI must not convert a configured method into an executed
run or infer approved algorithms from a stage name.

Real reruns append new object/version/run identities and pin dependencies rather
than updating previous receipts. An experiment comparison must first establish
compatible study, corpus/snapshot membership, input hashes, feature definitions,
transforms and model/configuration versions. Record differences and comparability
limitations; no numerical comparison metric or statistical plan is chosen here.
Use S2A `ExperimentRun` only with a real pinned snapshot satisfying its contract.
Pre-snapshot operation histories need a future reviewed representation, not a
fabricated dataset. Multi-study ownership/migration details are in the separate
[data architecture proposal](multi-study-data-architecture.md).
