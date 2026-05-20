"""Тесты ARQ-задачи ``check_dns``.

Стиль аналогичен ``test_check_ssl_task``: моки на БД-сессию,
``resolve_records`` и Redis. Проверяем ключевые ветки:

- skip при удержанном ``dns_check_in_progress`` флаге
- first fetch (``old=None``) → upsert + НЕТ уведомлений
- a_changed → enqueue ``a_changed``-нотис для подписчиков
- ``invalid_domain`` → upsert БЕЗ is_reachable=False, без enqueue
- ns_mismatch detected transition → enqueue ``ns_mismatch_detected``
- ``is_muted`` гасит уведомления
- ``track_dns=false`` гасит уведомления
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.db.models import DNSCache
from src.dns_monitor import DNSError, DNSRecords


def _ctx(*, sync_redis: AsyncMock, arq_redis: AsyncMock | None = None) -> dict[str, object]:
    return {
        "sync_redis": sync_redis,
        "redis": arq_redis or AsyncMock(),
        "bot": AsyncMock(),
    }


@asynccontextmanager
async def _fake_session(*_args, **_kwargs):  # type: ignore[no-untyped-def]
    yield AsyncMock()


def _make_cache(
    *,
    a_records: list[str] | None = None,
    aaaa_records: list[str] | None = None,
    ns_records: list[str] | None = None,
    is_reachable: bool | None = True,
    ns_mismatch_active: bool = False,
    fail_count: int = 0,
) -> DNSCache:
    """Заполненный ``DNSCache`` ORM-объект (без БД)."""
    cache = DNSCache(domain="example.com")
    cache.a_records = a_records if a_records is not None else ["192.0.2.1"]
    cache.aaaa_records = aaaa_records
    cache.ns_records = ns_records if ns_records is not None else ["ns1.example.com"]
    cache.asn_set = None
    cache.resolution_state = "resolved"
    cache.is_reachable = is_reachable
    cache.resolver_used = "1.1.1.1"
    cache.ns_mismatch_active = ns_mismatch_active
    cache.fail_count = fail_count
    cache.last_error = None
    cache.last_checked_at = datetime(2026, 5, 17, 12, 0, tzinfo=UTC)
    cache.last_successful_check_at = datetime(2026, 5, 17, 12, 0, tzinfo=UTC)
    cache.last_changed_at = None
    cache.next_check_at = datetime(2026, 5, 17, 12, 0, tzinfo=UTC)
    return cache


def _make_records(
    *,
    a: list[str] | None = None,
    aaaa: list[str] | None = None,
    ns: list[str] | None = None,
) -> DNSRecords:
    return DNSRecords(
        domain="example.com",
        is_reachable=True,
        a_records=a if a is not None else ["192.0.2.1"],
        aaaa_records=aaaa or [],
        ns_records=ns if ns is not None else ["ns1.example.com"],
        resolution_state="resolved",
        resolver_used="1.1.1.1",
    )


def _patch_repos(
    monkeypatch: pytest.MonkeyPatch,
    *,
    cache_repo: AsyncMock,
    domain_repo: AsyncMock | None = None,
    whois_repo: AsyncMock | None = None,
    resolve_result: DNSRecords | DNSError | None = None,
) -> None:
    monkeypatch.setattr("src.tasks.check_dns.get_session", _fake_session)
    monkeypatch.setattr("src.tasks.check_dns.DNSCacheRepository", lambda _s: cache_repo)
    if domain_repo is not None:
        monkeypatch.setattr("src.tasks.check_dns.DomainRepository", lambda _s: domain_repo)
    if whois_repo is None:
        whois_repo = AsyncMock()
        whois_repo.get.return_value = None
    monkeypatch.setattr("src.tasks.check_dns.WhoisCacheRepository", lambda _s: whois_repo)
    if resolve_result is not None:
        monkeypatch.setattr(
            "src.tasks.check_dns.resolve_records",
            AsyncMock(return_value=resolve_result),
        )


class TestSkipsWhenAlreadyInProgress:
    async def test_returns_early_if_redis_flag_held(self) -> None:
        sync_redis = AsyncMock()
        sync_redis.set.return_value = None
        ctx = _ctx(sync_redis=sync_redis)

        with patch("src.tasks.check_dns.resolve_records") as resolve:
            from src.tasks.check_dns import check_dns

            await check_dns(ctx, "example.com")
        resolve.assert_not_called()


class TestFirstFetch:
    async def test_first_fetch_no_enqueue(self, monkeypatch: pytest.MonkeyPatch) -> None:
        sync_redis = AsyncMock()
        sync_redis.set.return_value = True
        arq_redis = AsyncMock()
        ctx = _ctx(sync_redis=sync_redis, arq_redis=arq_redis)

        cache_repo = AsyncMock()
        cache_repo.get.return_value = None  # первая проверка
        cache_repo.upsert = AsyncMock()

        _patch_repos(
            monkeypatch,
            cache_repo=cache_repo,
            resolve_result=_make_records(),
        )

        from src.tasks.check_dns import check_dns

        await check_dns(ctx, "example.com")

        cache_repo.upsert.assert_awaited_once()
        arq_redis.enqueue_job.assert_not_called()

    async def test_bootstrap_row_no_notifications(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """check_dns на свежей bootstrap-строке (last_checked_at=None)
        не шлёт change-уведомлений — это первая реальная проверка.

        Регрессия 14e: первый dns_scheduler_tick прислал 38 false-alerts
        потому что bootstrap-строки с NULL-записями проходили
        first-fetch guard в ``compute_dns_diff`` (там был только
        ``if old is None``).
        """
        sync_redis = AsyncMock()
        sync_redis.set.return_value = True
        arq_redis = AsyncMock()
        ctx = _ctx(sync_redis=sync_redis, arq_redis=arq_redis)

        # Bootstrap-строка: запись существует, но не была проверена.
        bootstrap_row = DNSCache(domain="example.com")
        bootstrap_row.a_records = None
        bootstrap_row.aaaa_records = None
        bootstrap_row.ns_records = None
        bootstrap_row.asn_set = None
        bootstrap_row.resolution_state = "unknown"
        bootstrap_row.is_reachable = None
        bootstrap_row.resolver_used = None
        bootstrap_row.ns_mismatch_active = False
        bootstrap_row.fail_count = 0
        bootstrap_row.last_error = None
        bootstrap_row.last_checked_at = None
        bootstrap_row.last_successful_check_at = None
        bootstrap_row.last_changed_at = None
        bootstrap_row.next_check_at = datetime(2026, 5, 20, 12, 0, tzinfo=UTC)

        cache_repo = AsyncMock()
        cache_repo.get.return_value = bootstrap_row
        cache_repo.upsert = AsyncMock()

        domain_repo = AsyncMock()
        domain_repo.get_subscribers_for_domain.return_value = []

        _patch_repos(
            monkeypatch,
            cache_repo=cache_repo,
            domain_repo=domain_repo,
            resolve_result=_make_records(a=["1.2.3.4"], ns=["ns1.example.com"]),
        )

        from src.tasks.check_dns import check_dns

        await check_dns(ctx, "example.com")

        # Данные записаны в кэш, но send_dns_change_notice НЕ enqueue'нут.
        cache_repo.upsert.assert_awaited_once()
        notify_calls = [
            c
            for c in arq_redis.enqueue_job.await_args_list
            if c.args and c.args[0] == "send_dns_change_notice"
        ]
        assert (
            notify_calls == []
        ), f"bootstrap row must not enqueue notifications, got: {notify_calls}"


class TestChangeDetection:
    async def test_a_change_enqueues_for_subscribers(self, monkeypatch: pytest.MonkeyPatch) -> None:
        sync_redis = AsyncMock()
        sync_redis.set.return_value = True
        arq_redis = AsyncMock()
        ctx = _ctx(sync_redis=sync_redis, arq_redis=arq_redis)

        old = _make_cache(a_records=["192.0.2.1"])
        new = _make_records(a=["192.0.2.99"])  # IP сменился

        cache_repo = AsyncMock()
        cache_repo.get.return_value = old
        cache_repo.upsert = AsyncMock()

        sub = MagicMock()
        sub.user_id = 42
        sub.is_muted = False
        sub.track_dns = True
        domain_repo = AsyncMock()
        domain_repo.get_subscribers_for_domain.return_value = [sub]

        _patch_repos(
            monkeypatch,
            cache_repo=cache_repo,
            domain_repo=domain_repo,
            resolve_result=new,
        )

        from src.tasks.check_dns import check_dns

        await check_dns(ctx, "example.com")

        calls = arq_redis.enqueue_job.await_args_list
        assert len(calls) == 1
        args = calls[0].args
        assert args[0] == "send_dns_change_notice"
        assert args[1] == 42
        assert args[3] == "a_changed"

    async def test_muted_subscriber_does_not_get_notice(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        sync_redis = AsyncMock()
        sync_redis.set.return_value = True
        arq_redis = AsyncMock()
        ctx = _ctx(sync_redis=sync_redis, arq_redis=arq_redis)

        old = _make_cache(a_records=["192.0.2.1"])
        new = _make_records(a=["192.0.2.99"])

        cache_repo = AsyncMock()
        cache_repo.get.return_value = old
        cache_repo.upsert = AsyncMock()

        sub = MagicMock()
        sub.user_id = 42
        sub.is_muted = True  # kill-switch
        sub.track_dns = True
        domain_repo = AsyncMock()
        domain_repo.get_subscribers_for_domain.return_value = [sub]

        _patch_repos(
            monkeypatch,
            cache_repo=cache_repo,
            domain_repo=domain_repo,
            resolve_result=new,
        )

        from src.tasks.check_dns import check_dns

        await check_dns(ctx, "example.com")

        arq_redis.enqueue_job.assert_not_called()

    async def test_track_dns_off_does_not_get_notice(self, monkeypatch: pytest.MonkeyPatch) -> None:
        sync_redis = AsyncMock()
        sync_redis.set.return_value = True
        arq_redis = AsyncMock()
        ctx = _ctx(sync_redis=sync_redis, arq_redis=arq_redis)

        old = _make_cache(a_records=["192.0.2.1"])
        new = _make_records(a=["192.0.2.99"])

        cache_repo = AsyncMock()
        cache_repo.get.return_value = old
        cache_repo.upsert = AsyncMock()

        sub = MagicMock()
        sub.user_id = 42
        sub.is_muted = False
        sub.track_dns = False  # отключил DNS-трекинг
        domain_repo = AsyncMock()
        domain_repo.get_subscribers_for_domain.return_value = [sub]

        _patch_repos(
            monkeypatch,
            cache_repo=cache_repo,
            domain_repo=domain_repo,
            resolve_result=new,
        )

        from src.tasks.check_dns import check_dns

        await check_dns(ctx, "example.com")

        arq_redis.enqueue_job.assert_not_called()


class TestNSMismatch:
    async def test_ns_mismatch_detected_transition_enqueues(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        sync_redis = AsyncMock()
        sync_redis.set.return_value = True
        arq_redis = AsyncMock()
        ctx = _ctx(sync_redis=sync_redis, arq_redis=arq_redis)

        # old.ns_mismatch_active=False, DNS-NS совпадали с WHOIS.
        old = _make_cache(
            ns_records=["ns1.example.com"],
            ns_mismatch_active=False,
        )
        # Свежий резолв: DNS-NS теперь "ns1.attacker.com".
        new = _make_records(ns=["ns1.attacker.com"])

        cache_repo = AsyncMock()
        cache_repo.get.return_value = old
        cache_repo.upsert = AsyncMock()

        whois_cache = MagicMock()
        whois_cache.name_servers = ["ns1.example.com"]
        whois_repo = AsyncMock()
        whois_repo.get.return_value = whois_cache

        sub = MagicMock()
        sub.user_id = 42
        sub.is_muted = False
        sub.track_dns = True
        domain_repo = AsyncMock()
        domain_repo.get_subscribers_for_domain.return_value = [sub]

        _patch_repos(
            monkeypatch,
            cache_repo=cache_repo,
            domain_repo=domain_repo,
            whois_repo=whois_repo,
            resolve_result=new,
        )

        from src.tasks.check_dns import check_dns

        await check_dns(ctx, "example.com")

        change_types = {call.args[3] for call in arq_redis.enqueue_job.await_args_list}
        # NS-список изменился → ns_changed; DNS-NS != WHOIS-NS → ns_mismatch_detected.
        assert "ns_changed" in change_types
        assert "ns_mismatch_detected" in change_types


class TestErrorBranch:
    async def test_invalid_domain_does_not_mark_unreachable(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        sync_redis = AsyncMock()
        sync_redis.set.return_value = True
        arq_redis = AsyncMock()
        ctx = _ctx(sync_redis=sync_redis, arq_redis=arq_redis)

        old = _make_cache(is_reachable=True)
        error = DNSError(
            domain="example.com",
            error_type="invalid_domain",
            message="idna failed",
        )

        cache_repo = AsyncMock()
        cache_repo.get.return_value = old
        cache_repo.upsert = AsyncMock()

        domain_repo = AsyncMock()
        domain_repo.get_subscribers_for_domain.return_value = []

        _patch_repos(
            monkeypatch,
            cache_repo=cache_repo,
            domain_repo=domain_repo,
            resolve_result=error,
        )

        from src.tasks.check_dns import check_dns

        await check_dns(ctx, "example.com")

        cache_repo.upsert.assert_awaited_once()
        # Проверяем что upsert НЕ выставил is_reachable=False для invalid_domain.
        kwargs = cache_repo.upsert.await_args.kwargs
        assert "is_reachable" not in kwargs
        # И никаких became_unreachable enqueue не было.
        arq_redis.enqueue_job.assert_not_called()

    async def test_nxdomain_first_failure_marks_unreachable_and_enqueues(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        sync_redis = AsyncMock()
        sync_redis.set.return_value = True
        arq_redis = AsyncMock()
        ctx = _ctx(sync_redis=sync_redis, arq_redis=arq_redis)

        old = _make_cache(is_reachable=True, fail_count=0)
        error = DNSError(
            domain="example.com",
            error_type="nxdomain",
            message="not found",
        )

        cache_repo = AsyncMock()
        cache_repo.get.return_value = old
        cache_repo.upsert = AsyncMock()

        sub = MagicMock()
        sub.user_id = 42
        sub.is_muted = False
        sub.track_dns = True
        domain_repo = AsyncMock()
        domain_repo.get_subscribers_for_domain.return_value = [sub]

        _patch_repos(
            monkeypatch,
            cache_repo=cache_repo,
            domain_repo=domain_repo,
            resolve_result=error,
        )

        from src.tasks.check_dns import check_dns

        await check_dns(ctx, "example.com")

        cache_repo.upsert.assert_awaited_once()
        kwargs = cache_repo.upsert.await_args.kwargs
        assert kwargs.get("is_reachable") is False

        # became_unreachable → один enqueue.
        calls = arq_redis.enqueue_job.await_args_list
        assert len(calls) == 1
        assert calls[0].args[3] == "became_unreachable"
