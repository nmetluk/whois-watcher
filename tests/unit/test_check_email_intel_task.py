"""Тесты ARQ-задачи ``check_email_intel``.

Стиль аналогичен ``test_check_ssl_task``: моки на БД-сессию,
``fetch_email_intel`` и Redis. Проверяем ключевые ветки:

- skip при удержанном ``email_intel_check_in_progress`` флаге
- успешный fetch → upsert + diff guard на first fetch
- ошибка fetch → update_fail + became_unreachable, но ТОЛЬКО при
  переходе reachable → unreachable
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.db.models import EmailIntelCache
from src.email_intel.types import (
    DKIMInfo,
    DMARCRecord,
    EmailIntelError,
    EmailIntelResult,
    MXRecord,
    SPFRecord,
)


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
    is_reachable: bool = True,
    mx_records: list[dict] | None = None,
    spf_record: str | None = "v=spf1 ip4:192.0.2.0/24 -all",
    spf_mode: str | None = "fail",
    dmarc_policy: str | None = "reject",
    fail_count: int = 0,
) -> EmailIntelCache:
    """Заполненный ``EmailIntelCache`` ORM-объект (без БД)."""
    cache = EmailIntelCache(domain="example.com")
    cache.is_reachable = is_reachable
    cache.mx_records = mx_records or [{"host": "mx.example.com", "priority": 10}]
    cache.spf_record = spf_record
    cache.spf_mode = spf_mode
    cache.dmarc_policy = dmarc_policy
    cache.dmarc_subpolicy = None
    cache.dmarc_pct = 100
    cache.dkim_selectors = ["google"]
    cache.fail_count = fail_count
    cache.last_error = None
    cache.last_checked_at = None
    cache.last_successful_check_at = None
    cache.next_check_at = datetime(2026, 5, 17, 12, 0, tzinfo=UTC)
    return cache


def _make_result(
    *,
    mx_records: list[MXRecord] | None = None,
    spf: SPFRecord | None = None,
    dmarc: DMARCRecord | None = None,
    dkim: DKIMInfo | None = None,
) -> EmailIntelResult:
    return EmailIntelResult(
        domain="example.com",
        is_reachable=True,
        mx_records=mx_records or [MXRecord(host="mx.example.com", priority=10)],
        spf=spf or SPFRecord(raw="v=spf1 ip4:192.0.2.0/24 -all", mode="fail", is_multiple=False),
        dmarc=dmarc or DMARCRecord(policy="reject"),
        dkim=dkim or DKIMInfo(selectors=["google"]),
    )


class TestSkipsWhenAlreadyInProgress:
    async def test_returns_early_if_redis_flag_held(self) -> None:
        sync_redis = AsyncMock()
        sync_redis.set.return_value = None
        ctx = _ctx(sync_redis=sync_redis)

        with patch("src.tasks.check_email_intel.fetch_email_intel") as fetch:
            from src.tasks.check_email_intel import check_email_intel

            await check_email_intel(ctx, "example.com")
        fetch.assert_not_called()


class TestSuccessfulFetch:
    async def test_first_fetch_does_not_enqueue_change_notices(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        sync_redis = AsyncMock()
        sync_redis.set.return_value = True
        arq_redis = AsyncMock()
        ctx = _ctx(sync_redis=sync_redis, arq_redis=arq_redis)

        cache_repo = AsyncMock()
        cache_repo.get.return_value = None  # ещё ни разу не проверяли
        cache_repo.upsert = AsyncMock()

        monkeypatch.setattr("src.tasks.check_email_intel.get_session", _fake_session)
        monkeypatch.setattr(
            "src.tasks.check_email_intel.EmailIntelCacheRepository", lambda _session: cache_repo
        )
        monkeypatch.setattr(
            "src.tasks.check_email_intel.fetch_email_intel",
            AsyncMock(return_value=_make_result()),
        )

        from src.tasks.check_email_intel import check_email_intel

        await check_email_intel(ctx, "example.com")

        cache_repo.upsert.assert_awaited_once()
        # Нет подписчиков — нет change-notice. Самое важное: НЕ enqueue ничего.
        arq_redis.enqueue_job.assert_not_called()

    async def test_mx_change_enqueues_for_subscribers(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        sync_redis = AsyncMock()
        sync_redis.set.return_value = True
        arq_redis = AsyncMock()
        ctx = _ctx(sync_redis=sync_redis, arq_redis=arq_redis)

        old = _make_cache(mx_records=[{"host": "mx1.example.com", "priority": 10}])
        # new_result должен иметь тот же dmarc что и old, чтобы только MX изменился
        new_result = EmailIntelResult(
            domain="example.com",
            is_reachable=True,
            mx_records=[MXRecord(host="mx2.example.com", priority=10)],
            spf=SPFRecord(raw="v=spf1 ip4:192.0.2.0/24 -all", mode="fail", is_multiple=False),
            dmarc=DMARCRecord(policy="reject", subpolicy=None, pct=100),
            dkim=DKIMInfo(selectors=["google"]),
        )

        cache_repo = AsyncMock()
        cache_repo.get.return_value = old
        cache_repo.upsert = AsyncMock()

        sub = MagicMock()
        sub.user_id = 42
        sub.is_muted = False
        sub.track_email = True
        sub.notify_email_mx = True

        domain_repo = AsyncMock()
        domain_repo.get_subscribers_for_domain.return_value = [sub]

        monkeypatch.setattr("src.tasks.check_email_intel.get_session", _fake_session)
        monkeypatch.setattr(
            "src.tasks.check_email_intel.EmailIntelCacheRepository", lambda _session: cache_repo
        )
        monkeypatch.setattr(
            "src.tasks.check_email_intel.DomainRepository", lambda _session: domain_repo
        )
        monkeypatch.setattr(
            "src.tasks.check_email_intel.fetch_email_intel",
            AsyncMock(return_value=new_result),
        )

        from src.tasks.check_email_intel import check_email_intel

        await check_email_intel(ctx, "example.com")

        # mx changed → один enqueue.
        calls = arq_redis.enqueue_job.await_args_list
        assert len(calls) == 1
        args = calls[0].args
        assert args[0] == "send_email_change_notice"
        assert args[1] == 42
        assert args[3] == "mx_changed"

    async def test_muted_subscriber_does_not_get_notice(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        sync_redis = AsyncMock()
        sync_redis.set.return_value = True
        arq_redis = AsyncMock()
        ctx = _ctx(sync_redis=sync_redis, arq_redis=arq_redis)

        old = _make_cache()
        new_result = _make_result(mx_records=[MXRecord(host="mx2.example.com", priority=10)])

        cache_repo = AsyncMock()
        cache_repo.get.return_value = old
        cache_repo.upsert = AsyncMock()

        sub = MagicMock()
        sub.user_id = 42
        sub.is_muted = True  # kill-switch
        sub.track_email = True
        sub.notify_email_mx = True

        domain_repo = AsyncMock()
        domain_repo.get_subscribers_for_domain.return_value = [sub]

        monkeypatch.setattr("src.tasks.check_email_intel.get_session", _fake_session)
        monkeypatch.setattr(
            "src.tasks.check_email_intel.EmailIntelCacheRepository", lambda _session: cache_repo
        )
        monkeypatch.setattr(
            "src.tasks.check_email_intel.DomainRepository", lambda _session: domain_repo
        )
        monkeypatch.setattr(
            "src.tasks.check_email_intel.fetch_email_intel",
            AsyncMock(return_value=new_result),
        )

        from src.tasks.check_email_intel import check_email_intel

        await check_email_intel(ctx, "example.com")

        arq_redis.enqueue_job.assert_not_called()


class TestFailedFetch:
    async def test_first_failure_marks_unreachable_and_enqueues(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        sync_redis = AsyncMock()
        sync_redis.set.return_value = True
        arq_redis = AsyncMock()
        ctx = _ctx(sync_redis=sync_redis, arq_redis=arq_redis)

        old = _make_cache(is_reachable=True, fail_count=0)
        error = EmailIntelError(
            domain="example.com",
            error_type="timeout",
            message="DNS timeout",
        )

        cache_repo = AsyncMock()
        cache_repo.get.return_value = old
        cache_repo.update_fail = AsyncMock()

        sub = MagicMock()
        sub.user_id = 42
        sub.is_muted = False
        sub.track_email = True
        sub.notify_email_mx = True

        domain_repo = AsyncMock()
        domain_repo.get_subscribers_for_domain.return_value = [sub]

        monkeypatch.setattr("src.tasks.check_email_intel.get_session", _fake_session)
        monkeypatch.setattr(
            "src.tasks.check_email_intel.EmailIntelCacheRepository", lambda _session: cache_repo
        )
        monkeypatch.setattr(
            "src.tasks.check_email_intel.DomainRepository", lambda _session: domain_repo
        )
        monkeypatch.setattr(
            "src.tasks.check_email_intel.fetch_email_intel",
            AsyncMock(return_value=error),
        )

        from src.tasks.check_email_intel import check_email_intel

        await check_email_intel(ctx, "example.com")

        cache_repo.update_fail.assert_awaited_once()

        # became_unreachable → один enqueue
        calls = arq_redis.enqueue_job.await_args_list
        assert len(calls) == 1
        assert calls[0].args[3] == "became_unreachable"

    async def test_repeat_failure_when_already_unreachable_no_duplicate_notice(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        sync_redis = AsyncMock()
        sync_redis.set.return_value = True
        arq_redis = AsyncMock()
        ctx = _ctx(sync_redis=sync_redis, arq_redis=arq_redis)

        # Уже зафиксировали недоступность на прошлом тике.
        old = _make_cache(is_reachable=False, fail_count=2)
        error = EmailIntelError(
            domain="example.com",
            error_type="timeout",
            message="still broken",
        )

        cache_repo = AsyncMock()
        cache_repo.get.return_value = old
        cache_repo.update_fail = AsyncMock()

        domain_repo = AsyncMock()
        domain_repo.get_subscribers_for_domain.return_value = []

        monkeypatch.setattr("src.tasks.check_email_intel.get_session", _fake_session)
        monkeypatch.setattr(
            "src.tasks.check_email_intel.EmailIntelCacheRepository", lambda _session: cache_repo
        )
        monkeypatch.setattr(
            "src.tasks.check_email_intel.DomainRepository", lambda _session: domain_repo
        )
        monkeypatch.setattr(
            "src.tasks.check_email_intel.fetch_email_intel",
            AsyncMock(return_value=error),
        )

        from src.tasks.check_email_intel import check_email_intel

        await check_email_intel(ctx, "example.com")

        cache_repo.update_fail.assert_awaited_once()
        # Никакого нового became_unreachable: уже зафиксировано.
        arq_redis.enqueue_job.assert_not_called()

    async def test_nxdomain_does_not_enqueue(self, monkeypatch: pytest.MonkeyPatch) -> None:
        sync_redis = AsyncMock()
        sync_redis.set.return_value = True
        arq_redis = AsyncMock()
        ctx = _ctx(sync_redis=sync_redis, arq_redis=arq_redis)

        old = _make_cache(is_reachable=True)
        error = EmailIntelError(
            domain="example.com",
            error_type="nxdomain",
            message="NXDOMAIN",
        )

        cache_repo = AsyncMock()
        cache_repo.get.return_value = old
        cache_repo.update_fail = AsyncMock()

        domain_repo = AsyncMock()
        domain_repo.get_subscribers_for_domain.return_value = []

        monkeypatch.setattr("src.tasks.check_email_intel.get_session", _fake_session)
        monkeypatch.setattr(
            "src.tasks.check_email_intel.EmailIntelCacheRepository", lambda _session: cache_repo
        )
        monkeypatch.setattr(
            "src.tasks.check_email_intel.DomainRepository", lambda _session: domain_repo
        )
        monkeypatch.setattr(
            "src.tasks.check_email_intel.fetch_email_intel",
            AsyncMock(return_value=error),
        )

        from src.tasks.check_email_intel import check_email_intel

        await check_email_intel(ctx, "example.com")

        # nxdomain — это не became_unreachable (по логике compute_email_diff)
        arq_redis.enqueue_job.assert_not_called()
