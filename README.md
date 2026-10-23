# Stylometry Research Platform

An experiment process dashboard for DASET Paper 1, **A Data Science Approach to
Measuring Stylometric Stability and Variability in EFL Student Writing**.
The dashboard contains UI scaffolding with an optional metadata persistence foundation. No datasets, student text,
feature measurements, statistical outcomes, or completed research runs are bundled.

## Windows PowerShell setup

From the repository root (`F:\Stylometry Project`):

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e '.[dev]'
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501 --browser.gatherUsageStats false
```

If `py` is unavailable, substitute the full path to a working Python 3.11–3.14
executable. With `uv` installed, `uv venv --python 3.13 .venv` and
`uv pip install --python .venv\Scripts\python.exe -e '.[dev]'` are alternatives.
Activation is optional; the explicit executable paths avoid PowerShell execution
policy changes. Open **http://localhost:8501**. Stop the server with Ctrl+C.

## Dashboard

- **Experiment Process** (default): nine numbered planned stages, each with
  inputs, method/parameters, processing history, outputs, and visualization areas.
  All stages are explicitly not started.
- **Overview**: known experiment context and unknown/unverified research and
  publication metadata. Venue, dates, and publication status are not verified.
- **Features**: registry-driven search, family filter, individual selection, and
  comparison controls. The target is 43 engineered / 24 primary features; the
  registry is empty and incomplete pending authoritative definitions.
- **Sample**: empty anonymized selection and original/cleaned comparison, with
  provenance, word count, QC, feature values, and processing history placeholders.

No ETL, feature extraction, ICC calculations, or verification models are implemented.
Plotly, pandas, and NumPy are available for later approved work. SciPy,
statsmodels, and scikit-learn will be introduced when analysis work is authorized.

## Optional PostgreSQL

No database is required to start the dashboard. To configure a separately approved
development database:

```powershell
Copy-Item .env.example .env
# Edit .env locally and set DATABASE_URL; never paste credentials into Git.
```

Use `postgresql+psycopg://USER:PASSWORD@localhost:5432/DATABASE` and a least-privilege
development role. URL-encode special characters in credentials. Configuration is
loaded from the project-local `.env` or environment variables (environment wins).
The SQLAlchemy factory is lazy; startup never connects, creates tables, or runs
migrations. A configured URL is **untested**, not proof of connectivity. No live
connection is performed at startup. Never log URLs or engine exceptions
that might include credentials. S2B-01 adds the schema and explicit migrations
described below; no migration has been applied by this implementation task.

## Structure and reproducibility

```text
app.py                       Streamlit launcher
src/stylometry/
  stages.py                  immutable stage metadata
  features.py                empty authoritative-feature registry contract
  config.py                  local environment configuration
  database.py                optional lazy SQLAlchemy engine factory
  models.py                  PostgreSQL metadata ORM (15 tables)
  persistence.py             explicit validated contract/ORM conversion
  storage.py                 opaque private object reference contract
  migration_safety.py        empty local development target checks
  ui/dashboard.py            four-module Streamlit presentation layer
tests/                       metadata, configuration, and navigation tests
AGENTS.md                    scientific rules and approval gates
.env.example                 credential-free configuration template
pyproject.toml               package, dependency ranges, pytest configuration
uv.lock                      resolved dependency versions
migrations/                  frozen Alembic initial schema and task definitions
```

Use `uv sync --extra dev --locked` to reproduce the locked environment. The pip
setup above respects declared version ranges but may resolve newer releases.
Future processing records must capture input provenance, approved parameters,
timestamps, code version, and output references. No run records exist yet.

## Public repository safety

Keep research datasets, student writing, identifiers, backups, and generated
artifacts in approved private storage outside this repository. `.gitignore` is a
guardrail, not a data protection guarantee. Do not force-add ignored files.
Inspect `git status`, `git ls-files`, `git diff --cached --name-only`, and
`git diff --cached` before every commit. Never commit `.env` or credentials.
Do not import real documents or change approved methodology without authorization.

## S2A: data contracts and Paper 1 specification (review draft)

- [S2A development handoff and validation results](docs/s2a-review.md)
- [Research methodology and reported references](docs/paper1-methodology.md)
- [Discrepancy register and required source materials](docs/paper1-open-questions.md)
- [PostgreSQL schema proposal (not applied)](docs/postgresql-schema-proposal.md)
- `src/stylometry/contracts.py`: strict, frozen Pydantic metadata records and a
  closed-graph `ResearchBundle` validation boundary. Use constructors,
  `model_validate`, or `model_validate_json` to validate; Pydantic's
  `model_construct` and unvalidated `model_copy(update=...)` are not ingestion paths.
- `src/stylometry/paper1.py`: task definitions and explicitly reported reference
  counts supplied in S2A; no results have been recomputed.
- `tests/conftest.py` and `tests/test_contracts.py`: artificial metadata-only
  fixtures and validation tests; counts/digests/method refs are synthetic stubs,
  not extracted writing or approved scientific algorithms.

Run `uv sync --extra dev --locked` after checking out this branch, then
`.\.venv\Scripts\python.exe -m pytest`. No real source documents, database tables,
or analytical experiments are loaded or created. The nine-stage UI is unchanged.
The historical S2A authorization allowed one S2A review commit and a push of
`feature/paper1-data-contracts` only. Stop at **Approval Gate S2A** for ChatGPT
review after publishing that branch. S2B-01 separately authorizes persistence
development on `feature/s2b01-postgres-persistence`; stop before commit/push at
Approval Gate S2B-01. Source access and scientific implementation remain gated.

## S2B-01 PostgreSQL metadata persistence

See [implementation report and enforcement matrix](docs/s2b01-implementation.md)
for all tables, relationships, test results, storage design and limitations.
The S2A schema and scientific contracts are unchanged. The database stores UUID
references, hashes, metadata and receipts; private source, extracted and cleaned
writing bytes stay outside PostgreSQL and Git. ORM import and dashboard startup
perform no connections, DDL or migrations.

Update the local environment and inspect the migration without connecting:

```powershell
uv sync --extra dev --locked
.\.venv\Scripts\python.exe -m alembic history
# Review SQL on screen only; this does not execute it or check a target database.
.\.venv\Scripts\python.exe -m alembic upgrade head --sql
.\.venv\Scripts\python.exe -c "from stylometry.database import probe_postgresql; print(probe_postgresql())"
```

Provision a **new, empty, local** `stylometry_dev` database through your approved
PostgreSQL administration workflow, owned by a dedicated development role.
No PostgreSQL installer, database, role, password or grant is created by the app.
Use a private administration interface to select `template0` for a fresh database
and ensure no other clients can create objects during migration. Configure
`DATABASE_URL` locally as above (database name `stylometry_dev`, host `localhost`,
`127.0.0.1` or `::1`, no URL query overrides). Never paste a real URL into tracked
files, shell history or a review report. The connection probe uses psycopg through
SQLAlchemy; PostgreSQL command-line utilities are unnecessary.

Only after independently confirming the empty development target:

```powershell
$env:STYLOMETRY_MIGRATION_TARGET = 'stylometry_dev'
.\.venv\Scripts\python.exe -m alembic upgrade head
Remove-Item Env:STYLOMETRY_MIGRATION_TARGET
```

The initial migration verifies actual database/server identity, rejects existing
objects, custom schemas/extensions and event triggers, and uses a cooperative
transaction advisory lock. DDL and task seeding run in one explicit transaction.
An occupied database, including an already migrated database, is refused. This
initial-only policy must be reviewed before later migrations. Destructive
downgrade is disabled. Offline SQL bypasses target checks if executed manually;
it is for review only. Never run it manually against an unverified target.

Run synthetic tests with:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

To enable integration tests, separately provision an empty local database named
`stylometry_test`, with a dedicated test role. Set
`STYLOMETRY_TEST_DATABASE_URL` privately in the process environment using the same
driver/host rules. Tests do **not** fall back to `DATABASE_URL`. They verify the
empty test target, execute the frozen migration inside a transaction, run
synthetic constraint/relationship checks with savepoints, and roll back all
test DDL/data. An explicitly configured unavailable/unsafe target fails; an unset
test URL skips integration tests. Never point this variable at research storage.

Cross-row integrity is checked when explicitly reconstructing a complete
`ResearchBundle`, but database triggers, concurrent snapshot sealing and immutable
database privileges are deferred. This foundation is not yet a production
ingestion service. No ETL, feature extraction or statistical execution is added.
