"""Тесты ``src.services.whois_facade.WhoisFacade``.

Все зависимости (cache_repo, arq_redis, lookup_domain) мокаются. Проверяем:

- из кэша при свежих данных
- live-lookup при отсутствии кэша
- live-lookup при ``force_refresh=True``
- fallback на stale-кэш при ошибке live
- enqueue_check ставит задачу
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from src.config.limits import Limits
from src.db.models import WhoisCache
from src.services.whois_facade import WhoisFacade
from src.whois.types import WhoisData, WhoisError


def _facade(cache_repo: AsyncMock, arq_redis: AsyncMock) -> WhoisFacade:
    return WhoisFacade(cache_repo, arq_redis, Limits())


def _whois_data(domain: str = "example.com") -> WhoisData:
    return WhoisData(
        domain=domain,
        is_registered=True,
        expires_at=datetime(2027, 3, 15, tzinfo=UTC),
        registrar="Example Inc.",
    )


def _fresh_cache(domain: str = "example.com") -> WhoisCache:
    return WhoisCache(
        domain=domain,
        expires_at=datetime(2027, 3, 15, tzinfo=UTC),
        registrar="Cached Inc.",
        fetched_at=datetime.now(tz=UTC) - timedelta(hours=1),
    )


def _stale_cache(domain: str = "example.com", *, days_old: int = 10) -> WhoisCache:
    return WhoisCache(
        domain=domain,
        expires_at=datetime(2027, 3, 15, tzinfo=UTC),
        registrar="Old Inc.",
        fetched_at=datetime.now(tz=UTC) - timedelta(days=days_old),
    )


class TestGetOrFetch:
    async def test_returns_from_fresh_cache_without_live_call(self) -> None:
        cache_repo = AsyncMock()
        cache_repo.get.return_value = _fresh_cache()
        with patch("src.services.whois_facade.lookup_domain") as lookup:
            result = await _facade(cache_repo, AsyncMock()).get_or_fetch("example.com")
        assert result.error is None
        assert result.data is not None
        assert result.data.registrar == "Cached Inc."
        assert result.is_stale is False
        lookup.assert_not_awaited()

    async def test_force_refresh_skips_cache(self) -> None:
        cache_repo = AsyncMock()
        cache_repo.get.return_value = _fresh_cache()
        with patch(
            "src.services.whois_facade.lookup_domain", new=AsyncMock(return_value=_whois_data())
        ) as lookup:
            result = await _facade(cache_repo, AsyncMock()).get_or_fetch(
                "example.com", force_refresh=True
            )
        lookup.assert_awaited_once()
        assert result.data is not None
        assert result.data.registrar == "Example Inc."

    async def test_live_lookup_when_cache_empty(self) -> None:
        cache_repo = AsyncMock()
        cache_repo.get.return_value = None
        with patch(
            "src.services.whois_facade.lookup_domain", new=AsyncMock(return_value=_whois_data())
        ):
            result = await _facade(cache_repo, AsyncMock()).get_or_fetch("example.com")
        assert result.data is not None
        assert result.data.domain == "example.com"
        assert result.is_stale is False

    async def test_stale_fallback_on_live_error(self) -> None:
        """Live упал, в кэше есть устаревшие данные → отдаём их с пометкой."""
        cache_repo = AsyncMock()
        cache_repo.get.return_value = _stale_cache(days_old=10)
        error = WhoisError(domain="example.com", error_type="timeout", message="timed out")
        with patch("src.services.whois_facade.lookup_domain", new=AsyncMock(return_value=error)):
            result = await _facade(cache_repo, AsyncMock()).get_or_fetch(
                "example.com", force_refresh=True
            )
        assert result.is_stale is True
        assert result.stale_age_days >= 9
        assert result.data is not None
        assert result.error is None

    async def test_error_when_no_cache_and_live_fails(self) -> None:
        cache_repo = AsyncMock()
        cache_repo.get.return_value = None
        error = WhoisError(domain="example.com", error_type="timeout", message="timed out")
        with patch("src.services.whois_facade.lookup_domain", new=AsyncMock(return_value=error)):
            result = await _facade(cache_repo, AsyncMock()).get_or_fetch("example.com")
        assert result.error is not None
        assert result.data is None


def _fresh_free_cache(domain: str = "example.com") -> WhoisCache:
    """Свежая кэш-запись «домен свободен»: ни expires_at, ни registrar."""
    return WhoisCache(
        domain=domain,
        expires_at=None,
        registrar=None,
        fetched_at=datetime.now(tz=UTC) - timedelta(minutes=5),
    )


class TestFreeNeverServedFromCache:
    """ADR 046: «свободен» не отдаётся из кэша — всегда live-перепроверка."""

    async def test_fresh_free_cache_triggers_live_lookup(self) -> None:
        """Кэш свежий, но описывает свободный домен → live обязателен."""
        cache_repo = AsyncMock()
        cache_repo.get.return_value = _fresh_free_cache()
        live = _whois_data()  # домен уже зарегистрировали
        with patch(
            "src.services.whois_facade.lookup_domain", new=AsyncMock(return_value=live)
        ) as lookup:
            result = await _facade(cache_repo, AsyncMock()).get_or_fetch("example.com")
        lookup.assert_awaited_once()
        assert result.data is not None
        assert result.data.is_registered is True
        assert result.data.registrar == "Example Inc."
        assert result.is_stale is False

    async def test_fresh_free_cache_live_confirms_free(self) -> None:
        """Live подтвердил свободность → отдаём live-результат, не кэш."""
        cache_repo = AsyncMock()
        cache_repo.get.return_value = _fresh_free_cache()
        live = WhoisData(domain="example.com", is_registered=False)
        with patch(
            "src.services.whois_facade.lookup_domain", new=AsyncMock(return_value=live)
        ) as lookup:
            result = await _facade(cache_repo, AsyncMock()).get_or_fetch("example.com")
        lookup.assert_awaited_once()
        assert result.data is live
        assert result.is_stale is False

    async def test_free_cache_not_served_as_stale_on_live_error(self) -> None:
        """Live упал, в кэше «свободен» → ошибка, а не stale-«свободен»."""
        cache_repo = AsyncMock()
        cache_repo.get.return_value = _fresh_free_cache()
        error = WhoisError(domain="example.com", error_type="timeout", message="timed out")
        with patch("src.services.whois_facade.lookup_domain", new=AsyncMock(return_value=error)):
            result = await _facade(cache_repo, AsyncMock()).get_or_fetch("example.com")
        assert result.error is not None
        assert result.data is None

    async def test_registered_cache_still_served_fresh(self) -> None:
        """Контроль: зарегистрированный домен из свежего кэша — без live."""
        cache_repo = AsyncMock()
        cache_repo.get.return_value = _fresh_cache()
        with patch("src.services.whois_facade.lookup_domain") as lookup:
            result = await _facade(cache_repo, AsyncMock()).get_or_fetch("example.com")
        lookup.assert_not_awaited()
        assert result.data is not None
        assert result.data.is_registered is True


class TestEnqueueCheck:
    async def test_enqueue_check_calls_arq(self) -> None:
        arq_redis = AsyncMock()
        facade = _facade(AsyncMock(), arq_redis)
        await facade.enqueue_check("example.com")
        arq_redis.enqueue_job.assert_awaited_once_with("check_domain", "example.com")


class TestStaleAgeBoundary:
    @pytest.mark.parametrize("hours_old", [0, 1, 3])
    async def test_fresh_within_window(self, hours_old: int) -> None:
        cache_repo = AsyncMock()
        cache = _fresh_cache()
        cache.fetched_at = datetime.now(tz=UTC) - timedelta(hours=hours_old)
        cache_repo.get.return_value = cache
        with patch("src.services.whois_facade.lookup_domain") as lookup:
            result = await _facade(cache_repo, AsyncMock()).get_or_fetch("example.com")
        assert result.is_stale is False
        lookup.assert_not_awaited()
