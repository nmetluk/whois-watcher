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
from alembic.migration import MigrationContext
from sqlalchemy import create_engine


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

    Configured for **synchronous** execution (alembic.command.* uses sync DBAPI),
    despite our runtime using asyncpg. This is correct: migration tests run
    in CI with a live Postgres, not in the async bot process.
    """
    # Use alembic.ini from repo root (tests run from project root via pytest)
    cfg = alembic.config.Config("alembic.ini")

    # Suppress alembic deprecation warning about path_separator
    # (alembic.ini uses version_path_separator; legacy warning not actionable)
    cfg.set_main_option("path_separator", "os")

    # Override sqlalchemy.url to the ephemeral CI Postgres (not production)
    db_url = _get_postgres_url()
    if db_url:
        # Strip asyncpg+ → postgresql+ for alembic (sync driver required)
        sync_url = db_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
        cfg.set_main_option("sqlalchemy.url", sync_url)

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
    - Exactly one alembic head (no branching).
    """

    # Helper to get current revision from DB (not filesystem)
    def get_db_revision() -> str | None:
        url = alembic_cfg.get_main_option("sqlalchemy.url")
        assert url is not None  # for mypy
        engine = create_engine(url)
        with engine.begin() as connection:
            context = MigrationContext.configure(connection)
            return context.get_current_revision()

    # Clean slate: stamp base (no actual tables yet)
    alembic.command.stamp(alembic_cfg, "base", purge=True)

    # Upgrade to latest
    alembic.command.upgrade(alembic_cfg, "head")

    # Verify we're at head (non-None revision in DB)
    current_rev = get_db_revision()
    assert current_rev is not None, "Expected a current revision after upgrade"

    # Downgrade back to base
    alembic.command.downgrade(alembic_cfg, "base")

    # Verify we're back at base (None in DB)
    current_rev = get_db_revision()
    assert current_rev is None, f"Expected None at base, got: {current_rev}"

    # Upgrade again (round-trip)
    alembic.command.upgrade(alembic_cfg, "head")
    current_rev = get_db_revision()
    assert current_rev is not None, "Round-trip failed: expected a revision after final upgrade"
