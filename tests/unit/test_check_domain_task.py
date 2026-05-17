"""Тесты ARQ-задачи ``check_domain``.

Зависимости (БД-сессия, lookup_domain, Bot, Redis) полностью мокаются.
Проверяем ключевые ветки:

- успешный fetch → upsert в кэш с правильными полями
- ошибка fetch → update_fail + retry-расчёт
- параллельная проверка (Redis-флаг in_progress) → skip без падений

Эти тесты грубые «contract checks» — не проверяют форматирование
сообщений и нюансы followup'а (это другие модули).
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config.limits import Limits
from src.db.models import WhoisCache
from src.whois.types import WhoisData, WhoisError


def _ctx(*, sync_redis: AsyncMock, bot: AsyncMock | None = None) -> dict[str, object]:
    """Минимальный ARQ ``ctx`` для теста check_domain."""
    return {
        "sync_redis": sync_redis,
        "redis": AsyncMock(),  # ArqRedis (для enqueue_job)
        "bot": bot or AsyncMock(),
        "settings": AsyncMock(),
        "limits": Limits(),
    }


@asynccontextmanager
async def _fake_session_factory(*_args, **_kwargs):
    """Контекст-менеджер, отдающий нашу мок-сессию."""
    yield AsyncMock()


@pytest.fixture
def session_patch(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    """Подменяет ``src.tasks.check_domain.get_session`` на no-op CM."""
    monkeypatch.setattr("src.tasks.check_domain.get_session", _fake_session_factory)
    return AsyncMock()


class TestSkipsWhenAlreadyInProgress:
    async def test_returns_early_if_redis_flag_held(self, session_patch: AsyncMock) -> None:
        del session_patch
        sync_redis = AsyncMock()
        # ``set(... nx=True)`` вернёт None (вышло), True если флаг свободен.
        sync_redis.set.return_value = None
        ctx = _ctx(sync_redis=sync_redis)

        with patch("src.tasks.check_domain.lookup_domain") as lookup:
            from src.tasks.check_domain import check_domain

            await check_domain(ctx, "example.com")
        # Lookup не должен был вызваться — мы должны были выйти сразу.
        lookup.assert_not_called()


class TestSuccessfulFetch:
    async def test_upserts_cache_with_fields(self, monkeypatch: pytest.MonkeyPatch) -> None:
        sync_redis = AsyncMock()
        sync_redis.set.return_value = True
        sync_redis.smembers.return_value = set()
        ctx = _ctx(sync_redis=sync_redis)

        # Подменим репозитории на моки, чтобы видеть аргументы upsert.
        cache_repo_mock = AsyncMock()
        cache_repo_mock.get.return_value = None  # старого нет
        domain_repo_mock = AsyncMock()
        domain_repo_mock.get_subscribers_for_domain.return_value = []

        monkeypatch.setattr("src.tasks.check_domain.get_session", _fake_session_factory)
        monkeypatch.setattr(
            "src.tasks.check_domain.WhoisCacheRepository", lambda _s: cache_repo_mock
        )
        monkeypatch.setattr("src.tasks.check_domain.DomainRepository", lambda _s: domain_repo_mock)

        whois = WhoisData(
            domain="example.com",
            is_registered=True,
            expires_at=datetime(2027, 3, 15, tzinfo=UTC),
            registrar="Example Inc.",
            status=["clientTransferProhibited"],
            name_servers=["ns1.example.com", "ns2.example.com"],
        )
        with patch("src.tasks.check_domain.lookup_domain", new=AsyncMock(return_value=whois)):
            from src.tasks.check_domain import check_domain

            await check_domain(ctx, "example.com")

        cache_repo_mock.upsert.assert_awaited_once()
        kwargs = cache_repo_mock.upsert.call_args.kwargs
        assert kwargs["expires_at"] == datetime(2027, 3, 15, tzinfo=UTC)
        assert kwargs["registrar"] == "Example Inc."
        assert kwargs["status"] == ["clientTransferProhibited"]
        assert kwargs["name_servers"] == ["ns1.example.com", "ns2.example.com"]
        assert kwargs["fail_count"] == 0
        assert kwargs["last_error"] is None
        # next_check_at — рассчитан, не None для будущей даты
        assert kwargs["next_check_at"] is not None

    async def test_flag_released_in_finally(self, monkeypatch: pytest.MonkeyPatch) -> None:
        sync_redis = AsyncMock()
        sync_redis.set.return_value = True
        sync_redis.smembers.return_value = set()
        ctx = _ctx(sync_redis=sync_redis)
        monkeypatch.setattr("src.tasks.check_domain.get_session", _fake_session_factory)
        cache_repo_mock = AsyncMock()
        cache_repo_mock.get.return_value = None
        domain_repo_mock = AsyncMock()
        domain_repo_mock.get_subscribers_for_domain.return_value = []
        monkeypatch.setattr(
            "src.tasks.check_domain.WhoisCacheRepository", lambda _s: cache_repo_mock
        )
        monkeypatch.setattr("src.tasks.check_domain.DomainRepository", lambda _s: domain_repo_mock)

        whois = WhoisData(domain="example.com", is_registered=True)
        with patch("src.tasks.check_domain.lookup_domain", new=AsyncMock(return_value=whois)):
            from src.tasks.check_domain import check_domain

            await check_domain(ctx, "example.com")

        sync_redis.delete.assert_called_with("check_in_progress:example.com")


class TestFailedFetch:
    async def test_update_fail_called_with_retry_time(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        sync_redis = AsyncMock()
        sync_redis.set.return_value = True
        ctx = _ctx(sync_redis=sync_redis)

        # Существующий кэш с одним предыдущим фейлом → новый fail_count = 2.
        cache = WhoisCache(domain="example.com", fail_count=1)
        cache_repo_mock = AsyncMock()
        cache_repo_mock.get.return_value = cache

        monkeypatch.setattr("src.tasks.check_domain.get_session", _fake_session_factory)
        monkeypatch.setattr(
            "src.tasks.check_domain.WhoisCacheRepository", lambda _s: cache_repo_mock
        )
        monkeypatch.setattr("src.tasks.check_domain.DomainRepository", lambda _s: AsyncMock())

        err = WhoisError(domain="example.com", error_type="timeout", message="timed out")
        with patch("src.tasks.check_domain.lookup_domain", new=AsyncMock(return_value=err)):
            from src.tasks.check_domain import check_domain

            await check_domain(ctx, "example.com")

        cache_repo_mock.update_fail.assert_awaited_once()
        # ``next_check_at`` для fail_count=2 = +1 час (по нашей лестнице).
        kwargs = cache_repo_mock.update_fail.call_args.kwargs
        assert kwargs["next_check_at"] is not None


# ---------------------------------------------------------------------------
# Регрессия: первый fetch после /add — НЕ шлёт change-notice
# ---------------------------------------------------------------------------


class TestFirstFetchAfterAdd:
    """Реальный сценарий /add:

    1. ``DomainService.add_for_user`` делает upsert пустой строки
       ``whois_cache`` (только PK, expires_at=None, registrar=None).
    2. Воркер берёт задачу ``check_domain``.
    3. ``lookup_domain`` возвращает реальные данные.

    Ожидание: UPSERT данных сделан, но change-notice НЕ ставится в
    очередь — это первый fetch для домена, никаких «было/стало» нет.

    До фикса (guard'а на ``old_data.is_registered``) бот слал фейковые
    "registrar changed" и "expires_at changed" при каждом /add.
    """

    async def test_no_change_notice_when_placeholder_was_previous_state(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        sync_redis = AsyncMock()
        sync_redis.set.return_value = True
        sync_redis.smembers.return_value = set()
        arq_redis = AsyncMock()
        ctx = _ctx(sync_redis=sync_redis)
        ctx["redis"] = arq_redis  # ArqRedis с enqueue_job

        # Placeholder в кэше: PK заполнен, остальное NULL — как после
        # ``DomainService.add_for_user → self._cache.upsert(normalized)``.
        placeholder = WhoisCache(domain="example.com")
        cache_repo_mock = AsyncMock()
        cache_repo_mock.get.return_value = placeholder

        domain_repo_mock = AsyncMock()
        # Подписчик есть, но мы не должны до него дойти из-за guard'а.
        sub = MagicMock()
        sub.user_id = 100
        sub.is_wishlist = False
        sub.is_muted = False  # Этап 11: kill-switch
        sub.notify_expiry = True
        sub.notify_registrar_change = True
        sub.notify_ns_change = True
        sub.notify_status_change = True
        sub.notify_registrant_change = True
        sub.notify_problem = True
        domain_repo_mock.get_subscribers_for_domain.return_value = [sub]

        monkeypatch.setattr("src.tasks.check_domain.get_session", _fake_session_factory)
        monkeypatch.setattr(
            "src.tasks.check_domain.WhoisCacheRepository", lambda _s: cache_repo_mock
        )
        monkeypatch.setattr("src.tasks.check_domain.DomainRepository", lambda _s: domain_repo_mock)

        fresh = WhoisData(
            domain="example.com",
            is_registered=True,
            expires_at=datetime(2027, 3, 15, tzinfo=UTC),
            registrar="Example Inc.",
            status=["clientTransferProhibited"],
            name_servers=["ns1.example.com"],
        )
        with patch("src.tasks.check_domain.lookup_domain", new=AsyncMock(return_value=fresh)):
            from src.tasks.check_domain import check_domain

            await check_domain(ctx, "example.com")

        # UPSERT всё равно сделан — данные записались в кэш.
        cache_repo_mock.upsert.assert_awaited_once()

        # КЛЮЧЕВОЕ: enqueue_job НЕ был вызван с "send_change_notice".
        send_change_calls = [
            call
            for call in arq_redis.enqueue_job.await_args_list
            if call.args and call.args[0] == "send_change_notice"
        ]
        assert send_change_calls == [], (
            f"Expected NO send_change_notice on first fetch after /add, "
            f"got {len(send_change_calls)} call(s): {send_change_calls}"
        )

    async def test_change_notice_sent_when_real_change_after_fetched_data(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Обратный кейс: у нас УЖЕ были реальные данные, теперь они
        изменились — change-notice должен прийти как раньше."""
        sync_redis = AsyncMock()
        sync_redis.set.return_value = True
        sync_redis.smembers.return_value = set()
        arq_redis = AsyncMock()
        ctx = _ctx(sync_redis=sync_redis)
        ctx["redis"] = arq_redis

        # Старая запись с РЕАЛЬНЫМИ данными — is_registered=True
        # (expires_at и registrar не None).
        old = WhoisCache(
            domain="example.com",
            expires_at=datetime(2027, 3, 15, tzinfo=UTC),
            registrar="OldRegistrar",
            status=["clientTransferProhibited"],
            name_servers=["ns1.example.com"],
        )
        cache_repo_mock = AsyncMock()
        cache_repo_mock.get.return_value = old

        domain_repo_mock = AsyncMock()
        sub = MagicMock()
        sub.user_id = 100
        sub.is_wishlist = False
        sub.is_muted = False  # Этап 11: kill-switch
        sub.notify_expiry = True
        sub.notify_registrar_change = True
        sub.notify_ns_change = True
        sub.notify_status_change = True
        sub.notify_registrant_change = True
        sub.notify_problem = True
        domain_repo_mock.get_subscribers_for_domain.return_value = [sub]

        monkeypatch.setattr("src.tasks.check_domain.get_session", _fake_session_factory)
        monkeypatch.setattr(
            "src.tasks.check_domain.WhoisCacheRepository", lambda _s: cache_repo_mock
        )
        monkeypatch.setattr("src.tasks.check_domain.DomainRepository", lambda _s: domain_repo_mock)

        # Новые данные: тот же expires, но СМЕНИЛСЯ регистратор.
        fresh = WhoisData(
            domain="example.com",
            is_registered=True,
            expires_at=datetime(2027, 3, 15, tzinfo=UTC),
            registrar="NewRegistrar",  # ← изменение
            status=["clientTransferProhibited"],
            name_servers=["ns1.example.com"],
        )
        with patch("src.tasks.check_domain.lookup_domain", new=AsyncMock(return_value=fresh)):
            from src.tasks.check_domain import check_domain

            await check_domain(ctx, "example.com")

        # send_change_notice вызван хотя бы один раз с change_type="registrar".
        registrar_calls = [
            call
            for call in arq_redis.enqueue_job.await_args_list
            if call.args
            and call.args[0] == "send_change_notice"
            and len(call.args) >= 4
            and call.args[3] == "registrar"
        ]
        assert len(registrar_calls) == 1, (
            f"Expected exactly 1 send_change_notice(registrar) call, "
            f"got {len(registrar_calls)}: {arq_redis.enqueue_job.await_args_list}"
        )
