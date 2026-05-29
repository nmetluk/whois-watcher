"""Smoke-test Alembic migrations on ephemeral PostgreSQL.

This test actually connects to Postgres and runs alembic upgrade/downgrade
to catch DDL/backfill defects before they reach production (see TASK-0008).

Local run without Postgres: gracefully skipped via pytest.skip.
CI run: Postgres service is always available (see .github/workflows/ci.yml).
"""

from __future__ import annotations

import os
from urllib.parse import quote_plus

import alembic.command
import alembic.config
import pytest


def _get_postgres_url() -> str | None:
    """Build DATABASE_URL from POSTGRES_* env vars (mirrors src/config/settings.py).

    Returns None if critical env vars are missing → local run without Postgres.
    """
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    user = os.getenv("POSTGRES_USER", "whoiswatcher")
    password = os.getenv("POSTGRES_PASSWORD")
    db = os.getenv("POSTGRES_DB", "whoiswatcher")

    if not password:
        # Likely local run without POSTGRES_PASSWORD set → skip
        return None

    # URL-encode password (may contain special chars)
    encoded_password = quote_plus(password)
    return f"postgresql+asyncpg://{user}:{encoded_password}@{host}:{port}/{db}"


@pytest.fixture(scope="module")
def alembic_cfg() -> alembic.config.Config:
    """Alembic config pointing to the migrations directory.

    Configured for async execution (env.py uses async_engine_from_config),
    matching our runtime stack. sqlalchemy.url set here gets overridden
    by env.py → settings.postgres_dsn, but this ensures the config object
    isn't empty before alembic loads env.py.
    """
    # Use alembic.ini from repo root (tests run from project root via pytest)
    cfg = alembic.config.Config("alembic.ini")

    # Suppress alembic deprecation warning about path_separator
    # (alembic.ini uses version_path_separator; legacy warning not actionable)
    cfg.set_main_option("path_separator", "os")

    # Override sqlalchemy.url to the ephemeral CI Postgres (not production)
    db_url = _get_postgres_url()
    if db_url:
        cfg.set_main_option("sqlalchemy.url", db_url)

    return cfg


@pytest.fixture(scope="module")
def postgres_available(alembic_cfg: alembic.config.Config) -> bool:
    """Check if Postgres is available (CI yes, local maybe no).

    Used to skip the entire test module gracefully without failing imports.
    """
    db_url = _get_postgres_url()
    if db_url:
        return True
    return False


@pytest.mark.skipif(
    # Skip unless we're in CI (GitHub Actions sets CI=true) or explicitly enabled
    not os.getenv("CI"),
    reason="Postgres smoke-test only runs in CI (set CI=1 to enable)",
)
def test_migrations_roundtrip(alembic_cfg: alembic.config.Config) -> None:
    """Run full migration roundtrip: upgrade head → downgrade base → upgrade head.

    Ensures:
    - All revisions apply cleanly on a fresh DB.
    - downgrade is reversible (no orphan objects).
    """
    # Clean slate: stamp base (no actual tables yet)
    alembic.command.stamp(alembic_cfg, "base", purge=True)

    # Upgrade to latest
    alembic.command.upgrade(alembic_cfg, "head")

    # Downgrade back to base
    alembic.command.downgrade(alembic_cfg, "base")

    # Upgrade again (round-trip)
    alembic.command.upgrade(alembic_cfg, "head")
