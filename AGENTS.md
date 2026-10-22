# Project rules

This repository hosts the Stylometry Research Platform for reproducible EFL
student-writing experiments. Keep research logic in `src/stylometry/` and UI
code in `src/stylometry/ui/`. The root `app.py` is only a launcher.

## Scientific integrity
- Preserve the approved DASET methodology. Obtain explicit approval before
  changing methodology, feature definitions, selection rules, or statistical plans.
- Never fabricate outcomes, stage completion, feature definitions, or sample values.
- Mark unknown metadata, incomplete registries, and prototype placeholders clearly.
- Initialization does not authorize ETL, feature extraction, ICC, or verification models.
- Record future runs with input provenance, parameters, timestamps, code version,
  and output references. A configured stage is not an executed stage.

## Data protection and approval gates
- Never put student writing, identifiers, datasets, credentials, `.env` files,
  database exports, or backups in Git. Use approved private storage outside the repo.
- Do not import real student documents without explicit authorization and an
  approved anonymization/storage plan. Do not send research data to external services.
- Inspect existing work first. Get approval before overwriting, deleting, or
  reorganizing existing user work, creating production databases, or destructive migrations.
- Before every commit, inspect tracked/staged paths and staged content for sensitive
  material. Stage explicit paths. Stop before commit/push if safety, authentication,
  remote history, or repository identity is uncertain. Never force-push.
- Commit/push only when authorized by the user. The initialization request authorizes
  the initial safe commit and push to origin/main after checks pass.
- Never print database URLs or secrets in logs or UI. Database connectivity is opt-in.

## Development
- Use `.venv`, `pyproject.toml`, and the Windows commands in README.md.
- Test metadata invariants and UI navigation with pytest/Streamlit AppTest.
- Run `python -m pytest` and verify Streamlit starts before delivery.
- Keep dependencies minimal; add SQL persistence incrementally. Do not connect to
  PostgreSQL or create tables during import or dashboard startup.
