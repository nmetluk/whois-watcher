"""Smoke-test Alembic migrations on ephemeral PostgreSQL.

This test actually connects to Postgres and runs alembic upgrade/downgrade
to catch DDL/backfill defects before they reach production (see TASK-0008).

Local run without Postgres: gracefully skipped via pytest.skip.
CI run: Postgres service is always available (see .github/workflows/ci.yml).

Migration runs are isolated in a subprocess to prevent resource leaks
(unclosed sockets/event loops) from affecting other tests. See TASK-0009.
"""

from __future__ import annotations

import os
import subprocess
import sys

import pytest


def _run_alembic(*args: str) -> subprocess.CompletedProcess[str]:
    """Run alembic command in a subprocess with proper isolation.

    Uses the current Python interpreter and copies the environment
    (including POSTGRES_* vars set in CI). Captures output for debugging.
    """
    # alembic.ini is in the repo root; pytest runs from there by default
    cmd = [sys.executable, "-m", "alembic", "-c", "alembic.ini", *args]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=os.environ.copy(),
        check=False,  # We assert on returncode instead
    )

    if result.returncode != 0:
        # Provide full context for failure diagnosis
        raise AssertionError(
            f"alembic {' '.join(args)} failed (exit {result.returncode})\n"
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        )

    return result


@pytest.mark.skipif(
    # Skip unless we're in CI (GitHub Actions sets CI=true) or explicitly enabled
    not os.getenv("CI"),
    reason="Postgres smoke-test only runs in CI (set CI=1 to enable)",
)
def test_migrations_roundtrip() -> None:
    """Run full migration roundtrip: upgrade head → downgrade base → upgrade head.

    Runs alembic commands via subprocess to isolate resources (sockets, event
    loops). Each call gets a fresh process, preventing leaks from affecting
    other tests (see TASK-0009: in-process calls left unclosed resources).

    Ensures:
    - All revisions apply cleanly on a fresh DB.
    - downgrade is reversible (no orphan objects).
    """
    # Upgrade to latest (applies all pending migrations)
    _run_alembic("upgrade", "head")

    # Downgrade back to base (tests reversibility)
    _run_alembic("downgrade", "base")

    # Upgrade again (round-trip verification)
    _run_alembic("upgrade", "head")
