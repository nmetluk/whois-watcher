"""Fixtures for ARQ integration tests using pytest-docker (TASK-0052)."""

from __future__ import annotations

import os
import socket
import subprocess
import time
from collections.abc import Iterator
from typing import Any

import pytest


@pytest.fixture(scope="session")
def docker_compose_file(pytestconfig: pytest.Config) -> str:
    return os.path.join(str(pytestconfig.rootdir), "tests", "docker-compose.test.yml")


@pytest.fixture(scope="session")
def docker_compose_project_name() -> str:
    return "pytest-arq"


@pytest.fixture(scope="session")
def docker_ip() -> str:
    """Host IP for docker services (localhost for port-mapped)."""
    return "127.0.0.1"


def _is_service_ready(host: str, port: int) -> bool:
    """TCP connect check."""
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except (OSError, ConnectionError):
        return False


@pytest.fixture(scope="session")
def docker_services(docker_services: Any, docker_ip: str) -> Any:
    """Wait for postgres/redis ports to be responsive.
    In CI use github services (dummy), locally use pytest-docker compose.
    """
    if os.getenv("CI"):

        class _Dummy:
            def port_for(self, service: str, container_port: int) -> int:
                if service == "postgres":
                    return int(os.environ.get("POSTGRES_PORT", "5432"))
                if service == "redis":
                    return int(os.environ.get("REDIS_PORT", "6379"))
                return container_port

        return _Dummy()
    # local docker
    pg_port = docker_services.port_for("postgres", 5432)
    docker_services.wait_until_responsive(
        check=lambda: _is_service_ready(docker_ip, pg_port),
        timeout=60.0,
        pause=1.0,
    )
    rd_port = docker_services.port_for("redis", 6379)
    docker_services.wait_until_responsive(
        check=lambda: _is_service_ready(docker_ip, rd_port),
        timeout=30.0,
        pause=0.5,
    )
    time.sleep(3)
    return docker_services


@pytest.fixture(scope="session")
def integration_postgres_url(docker_ip: str, docker_services: Any) -> str:
    port = docker_services.port_for("postgres", 5432)
    user = os.environ.get("POSTGRES_USER", "whoiswatcher")
    password = os.environ.get("POSTGRES_PASSWORD", "test-postgres-password")
    db = os.environ.get("POSTGRES_DB", "whoiswatcher")
    return f"postgresql+asyncpg://{user}:{password}@{docker_ip}:{port}/{db}"


@pytest.fixture(scope="session")
def integration_redis_url(docker_ip: str, docker_services: Any) -> str:
    port = docker_services.port_for("redis", 6379)
    return f"redis://{docker_ip}:{port}/0"


def _apply_migrations(postgres_url: str) -> None:
    import re

    m = re.search(r"@([^:]+):(\d+)/", postgres_url)
    if not m:
        raise RuntimeError("Cannot parse postgres url")
    host, port = m.groups()
    env = os.environ.copy()
    env["POSTGRES_HOST"] = host
    env["POSTGRES_PORT"] = port
    res = subprocess.run(
        ["python", "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"],
        capture_output=True,
        text=True,
        env=env,
    )
    if res.returncode != 0:
        raise AssertionError(f"alembic upgrade failed: {res.stderr}\n{res.stdout}")


@pytest.fixture(scope="session")
def apply_migrations_once(integration_postgres_url: str) -> Iterator[None]:
    _apply_migrations(integration_postgres_url)
    yield


@pytest.fixture(scope="function")
async def real_db_session(integration_postgres_url: str, apply_migrations_once: None) -> Any:
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    engine = create_async_engine(integration_postgres_url, echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    async with async_session() as session:
        yield session
    await engine.dispose()


@pytest.fixture(scope="function")
def real_redis(integration_redis_url: str) -> Any:
    import redis.asyncio as redis

    return redis.from_url(integration_redis_url, decode_responses=True)
