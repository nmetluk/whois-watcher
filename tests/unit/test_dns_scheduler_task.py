"""Тесты ARQ-задачи ``dns_scheduler_tick``.

Параллельно ``test_check_ssl_task`` / ``test_check_dns_task``.
Моки на БД-сессию и Redis, проверяем три ветки:

- bootstrap отрабатывает (raw SQL → INSERT … ON CONFLICT DO NOTHING)
- enqueue для каждого due-домена
- skip если ничего не due
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest


@asynccontextmanager
async def _fake_session(session_mock):  # type: ignore[no-untyped-def]
    yield session_mock


def _make_due_entry(domain: str) -> MagicMock:
    entry = MagicMock()
    entry.domain = domain
    return entry


class TestBootstrap:
    async def test_bootstrap_sql_executed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        arq_redis = AsyncMock()
        ctx = {"redis": arq_redis}

        session_mock = AsyncMock()
        # session.execute возвращает объект с rowcount — это результат
        # raw SQL bootstrap-инсерта.
        result_mock = MagicMock()
        result_mock.rowcount = 3
        session_mock.execute.return_value = result_mock

        cache_repo = AsyncMock()
        cache_repo.get_due_for_check.return_value = []

        @asynccontextmanager
        async def session_cm(*_args, **_kwargs):  # type: ignore[no-untyped-def]
            yield session_mock

        monkeypatch.setattr("src.tasks.dns_scheduler.get_session", session_cm)
        monkeypatch.setattr("src.tasks.dns_scheduler.DNSCacheRepository", lambda _s: cache_repo)

        from src.tasks.dns_scheduler import dns_scheduler_tick

        await dns_scheduler_tick(ctx)

        # Bootstrap SQL должен быть выполнен.
        session_mock.execute.assert_awaited_once()
        # Без due-доменов очередь не наполняем.
        arq_redis.enqueue_job.assert_not_called()


class TestEnqueueDue:
    async def test_enqueues_each_due_domain(self, monkeypatch: pytest.MonkeyPatch) -> None:
        arq_redis = AsyncMock()
        ctx = {"redis": arq_redis}

        session_mock = AsyncMock()
        result_mock = MagicMock()
        result_mock.rowcount = 0
        session_mock.execute.return_value = result_mock

        due = [_make_due_entry("a.example.com"), _make_due_entry("b.example.com")]
        cache_repo = AsyncMock()
        cache_repo.get_due_for_check.return_value = due

        @asynccontextmanager
        async def session_cm(*_args, **_kwargs):  # type: ignore[no-untyped-def]
            yield session_mock

        monkeypatch.setattr("src.tasks.dns_scheduler.get_session", session_cm)
        monkeypatch.setattr("src.tasks.dns_scheduler.DNSCacheRepository", lambda _s: cache_repo)

        from src.tasks.dns_scheduler import dns_scheduler_tick

        await dns_scheduler_tick(ctx)

        calls = arq_redis.enqueue_job.await_args_list
        assert len(calls) == 2
        assert calls[0].args == ("check_dns", "a.example.com")
        assert calls[1].args == ("check_dns", "b.example.com")


class TestNothingDue:
    async def test_skips_when_nothing_due(self, monkeypatch: pytest.MonkeyPatch) -> None:
        arq_redis = AsyncMock()
        ctx = {"redis": arq_redis}

        session_mock = AsyncMock()
        result_mock = MagicMock()
        result_mock.rowcount = 0
        session_mock.execute.return_value = result_mock

        cache_repo = AsyncMock()
        cache_repo.get_due_for_check.return_value = []

        @asynccontextmanager
        async def session_cm(*_args, **_kwargs):  # type: ignore[no-untyped-def]
            yield session_mock

        monkeypatch.setattr("src.tasks.dns_scheduler.get_session", session_cm)
        monkeypatch.setattr("src.tasks.dns_scheduler.DNSCacheRepository", lambda _s: cache_repo)

        from src.tasks.dns_scheduler import dns_scheduler_tick

        await dns_scheduler_tick(ctx)

        arq_redis.enqueue_job.assert_not_called()
