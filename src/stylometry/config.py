"""Load optional configuration without connecting to external services."""

import os
from pathlib import Path

from dotenv import load_dotenv


def database_url() -> str | None:
    # Resolve the project-local .env explicitly; do not search parent directories.
    load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)
    return os.getenv("DATABASE_URL", "").strip() or None
