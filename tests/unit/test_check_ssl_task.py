"""Тесты ARQ-задачи ``check_ssl``.

Стиль аналогичен ``test_check_domain_task``: моки на БД-сессию,
``fetch_certificate`` и Redis. Проверяем ключевые ветки:

- skip при удержанном ``ssl_check_in_progress`` флаге
- успешный fetch → upsert + diff guard на first fetch
- ошибка fetch → update_fail + became_unreachable, но ТОЛЬКО при
  переходе reachable → unreachable
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.db.models import SSLCache
from src.ssl.types import SSLCertificate, SSLError


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
    has_certificate: bool = True,
    is_reachable: bool | None = True,
    not_after: datetime | None = None,
    issuer_cn: str | None = "R3",
    issuer_o: str | None = "Let's Encrypt",
    fail_count: int = 0,
) -> SSLCache:
    """Заполненный ``SSLCache`` ORM-объект (без БД)."""
    cache = SSLCache(domain="example.com")
    cache.has_certificate = has_certificate
    cache.is_reachable = is_reachable
    cache.not_before = datetime(2026, 4, 1, tzinfo=UTC)
    cache.not_after = not_after or datetime(2026, 8, 1, tzinfo=UTC)
    cache.issuer_cn = issuer_cn
    cache.issuer_o = issuer_o
    cache.subject_cn = "example.com"
    cache.subject_alt_names = ["example.com"]
    cache.serial_number = "1"
    cache.fingerprint_sha256 = "a" * 64
    cache.signature_algorithm = "sha256WithRSAEncryption"
    cache.fail_count = fail_count
    cache.last_error = None
    cache.last_checked_at = None
    cache.last_successful_check_at = None
    cache.next_check_at = datetime(2026, 5, 17, 12, 0, tzinfo=UTC)
    return cache


def _make_cert(
    *,
    issuer_cn: str = "R3",
    issuer_o: str = "Let's Encrypt",
    not_after: datetime | None = None,
) -> SSLCertificate:
    return SSLCertificate(
        domain="example.com",
        is_reachable=True,
        has_certificate=True,
        not_before=datetime(2026, 4, 1, tzinfo=UTC),
        not_after=not_after or datetime(2026, 8, 1, tzinfo=UTC),
        issuer_cn=issuer_cn,
        issuer_o=issuer_o,
        subject_cn="example.com",
        subject_alt_names=["example.com"],
        serial_number="1",
        fingerprint_sha256="b" * 64,
        signature_algorithm="sha256WithRSAEncryption",
    )


class TestSkipsWhenAlreadyInProgress:
    async def test_returns_early_if_redis_flag_held(self) -> None:
        sync_redis = AsyncMock()
        sync_redis.set.return_value = None
        ctx = _ctx(sync_redis=sync_redis)

        with patch("src.tasks.check_ssl.fetch_certificate") as fetch:
            from src.tasks.check_ssl import check_ssl

            await check_ssl(ctx, "example.com")
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

        monkeypatch.setattr("src.tasks.check_ssl.get_session", _fake_session)
        monkeypatch.setattr(
            "src.tasks.check_ssl.SSLCacheRepository", lambda _session: cache_repo
        )
        monkeypatch.setattr(
            "src.tasks.check_ssl.fetch_certificate",
            AsyncMock(return_value=_make_cert()),
        )

        from src.tasks.check_ssl import check_ssl

        await check_ssl(ctx, "example.com")

        cache_repo.upsert.assert_awaited_once()
        # Нет подписчиков — нет change-notice. Самое важное: НЕ enqueue ничего.
        arq_redis.enqueue_job.assert_not_called()

    async def test_issuer_change_enqueues_for_subscribers(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        sync_redis = AsyncMock()
        sync_redis.set.return_value = True
        arq_redis = AsyncMock()
        ctx = _ctx(sync_redis=sync_redis, arq_redis=arq_redis)

        old = _make_cache(issuer_cn="R3", issuer_o="Let's Encrypt")
        new_cert = _make_cert(issuer_cn="DigiCert", issuer_o="DigiCert")

        cache_repo = AsyncMock()
        cache_repo.get.return_value = old
        cache_repo.upsert = AsyncMock()

        sub = MagicMock()
        sub.user_id = 42
        sub.is_muted = False
        sub.track_ssl = True
        sub.notify_ssl_change_issuer = True
        sub.notify_ssl_expiry = True

        domain_repo = AsyncMock()
        domain_repo.get_subscribers_for_domain.return_value = [sub]

        monkeypatch.setattr("src.tasks.check_ssl.get_session", _fake_session)
        monkeypatch.setattr(
            "src.tasks.check_ssl.SSLCacheRepository", lambda _session: cache_repo
        )
        monkeypatch.setattr(
            "src.tasks.check_ssl.DomainRepository", lambda _session: domain_repo
        )
        monkeypatch.setattr(
            "src.tasks.check_ssl.fetch_certificate",
            AsyncMock(return_value=new_cert),
        )

        from src.tasks.check_ssl import check_ssl

        await check_ssl(ctx, "example.com")

        # issuer changed → один enqueue. not_after не менялся.
        calls = arq_redis.enqueue_job.await_args_list
        assert len(calls) == 1
        args = calls[0].args
        assert args[0] == "send_ssl_change_notice"
        assert args[1] == 42
        assert args[3] == "issuer_changed"

    async def test_muted_subscriber_does_not_get_notice(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        sync_redis = AsyncMock()
        sync_redis.set.return_value = True
        arq_redis = AsyncMock()
        ctx = _ctx(sync_redis=sync_redis, arq_redis=arq_redis)

        old = _make_cache()
        new_cert = _make_cert(issuer_cn="DigiCert", issuer_o="DigiCert")

        cache_repo = AsyncMock()
        cache_repo.get.return_value = old
        cache_repo.upsert = AsyncMock()

        sub = MagicMock()
        sub.user_id = 42
        sub.is_muted = True  # kill-switch
        sub.track_ssl = True
        sub.notify_ssl_change_issuer = True

        domain_repo = AsyncMock()
        domain_repo.get_subscribers_for_domain.return_value = [sub]

        monkeypatch.setattr("src.tasks.check_ssl.get_session", _fake_session)
        monkeypatch.setattr(
            "src.tasks.check_ssl.SSLCacheRepository", lambda _session: cache_repo
        )
        monkeypatch.setattr(
            "src.tasks.check_ssl.DomainRepository", lambda _session: domain_repo
        )
        monkeypatch.setattr(
            "src.tasks.check_ssl.fetch_certificate",
            AsyncMock(return_value=new_cert),
        )

        from src.tasks.check_ssl import check_ssl

        await check_ssl(ctx, "example.com")

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
        error = SSLError(
            domain="example.com",
            error_type="tls_handshake_failed",
            message="boom",
        )

        cache_repo = AsyncMock()
        cache_repo.get.return_value = old
        cache_repo.update_fail = AsyncMock()

        sub = MagicMock()
        sub.user_id = 42
        sub.is_muted = False
        sub.track_ssl = True
        sub.notify_ssl_expiry = True
        sub.notify_ssl_change_issuer = True

        domain_repo = AsyncMock()
        domain_repo.get_subscribers_for_domain.return_value = [sub]

        monkeypatch.setattr("src.tasks.check_ssl.get_session", _fake_session)
        monkeypatch.setattr(
            "src.tasks.check_ssl.SSLCacheRepository", lambda _session: cache_repo
        )
        monkeypatch.setattr(
            "src.tasks.check_ssl.DomainRepository", lambda _session: domain_repo
        )
        monkeypatch.setattr(
            "src.tasks.check_ssl.fetch_certificate",
            AsyncMock(return_value=error),
        )

        from src.tasks.check_ssl import check_ssl

        await check_ssl(ctx, "example.com")

        cache_repo.update_fail.assert_awaited_once()
        # is_reachable должен быть помечен False после первого фейла
        assert old.is_reachable is False

        # became_unreachable → один enqueue с notify_ssl_expiry-токеном
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
        error = SSLError(
            domain="example.com",
            error_type="tls_handshake_failed",
            message="still broken",
        )

        cache_repo = AsyncMock()
        cache_repo.get.return_value = old
        cache_repo.update_fail = AsyncMock()

        domain_repo = AsyncMock()
        domain_repo.get_subscribers_for_domain.return_value = []

        monkeypatch.setattr("src.tasks.check_ssl.get_session", _fake_session)
        monkeypatch.setattr(
            "src.tasks.check_ssl.SSLCacheRepository", lambda _session: cache_repo
        )
        monkeypatch.setattr(
            "src.tasks.check_ssl.DomainRepository", lambda _session: domain_repo
        )
        monkeypatch.setattr(
            "src.tasks.check_ssl.fetch_certificate",
            AsyncMock(return_value=error),
        )

        from src.tasks.check_ssl import check_ssl

        await check_ssl(ctx, "example.com")

        cache_repo.update_fail.assert_awaited_once()
        # Никакого нового became_unreachable: уже зафиксировано.
        arq_redis.enqueue_job.assert_not_called()

    async def test_no_https_does_not_enqueue(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        sync_redis = AsyncMock()
        sync_redis.set.return_value = True
        arq_redis = AsyncMock()
        ctx = _ctx(sync_redis=sync_redis, arq_redis=arq_redis)

        old = _make_cache(is_reachable=True)
        error = SSLError(
            domain="example.com",
            error_type="no_https",
            message="dns failed",
        )

        cache_repo = AsyncMock()
        cache_repo.get.return_value = old
        cache_repo.update_fail = AsyncMock()

        domain_repo = AsyncMock()
        domain_repo.get_subscribers_for_domain.return_value = []

        monkeypatch.setattr("src.tasks.check_ssl.get_session", _fake_session)
        monkeypatch.setattr(
            "src.tasks.check_ssl.SSLCacheRepository", lambda _session: cache_repo
        )
        monkeypatch.setattr(
            "src.tasks.check_ssl.DomainRepository", lambda _session: domain_repo
        )
        monkeypatch.setattr(
            "src.tasks.check_ssl.fetch_certificate",
            AsyncMock(return_value=error),
        )

        from src.tasks.check_ssl import check_ssl

        await check_ssl(ctx, "example.com")

        # no_https — это не алерт, никаких enqueue.
        arq_redis.enqueue_job.assert_not_called()
        # И is_reachable НЕ должно быть помечено False для no_https.
        assert old.is_reachable is True
