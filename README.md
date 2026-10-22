# Stylometry Research Platform

An experiment process dashboard for DASET Paper 1, **A Data Science Approach to
Measuring Stylometric Stability and Variability in EFL Student Writing**.
This initialization contains UI scaffolding only. No datasets, student text,
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
connection test is performed in initialization. Never log URLs or engine exceptions
that might include credentials. Database schema and migrations are deferred.

## Structure and reproducibility

```text
app.py                       Streamlit launcher
src/stylometry/
  stages.py                  immutable stage metadata
  features.py                empty authoritative-feature registry contract
  config.py                  local environment configuration
  database.py                optional lazy SQLAlchemy engine factory
  ui/dashboard.py            four-module Streamlit presentation layer
tests/                       metadata, configuration, and navigation tests
AGENTS.md                    scientific rules and approval gates
.env.example                 credential-free configuration template
pyproject.toml               package, dependency ranges, pytest configuration
uv.lock                      resolved dependency versions
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
