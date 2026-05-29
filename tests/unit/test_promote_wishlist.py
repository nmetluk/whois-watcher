"""Тесты для промоута wishlist → tracked."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from src.db.models import UserDomain, WhoisCache
from src.services.domains import DomainService


def _limits(*, max_domains: int = 100):
    """Дефолтные лимиты с переопределённым лимитом для тестов."""
    from src.config.limits import Limits

    return Limits(max_domains_per_user=max_domains)


def _make_service(
    *,
    domain_repo: AsyncMock,
    cache_repo: AsyncMock,
    facade: AsyncMock | None = None,
    limits: pytest.fixture | None = None,
) -> DomainService:
    return DomainService(
        domain_repo=domain_repo,
        cache_repo=cache_repo,
        facade=facade or AsyncMock(),
        limits=limits or _limits(),
    )


class TestPromoteFromWishlist:
    """Тесты промоута wishlist → tracked в DomainService."""

    async def test_promotes_wishlist_to_tracked(self) -> None:
        """add_for_user на wishlist-строку → status='promoted'."""
        domain_repo = AsyncMock()
        domain_repo.count_by_user.return_value = 5
        # get_for_user возвращает wishlist-строку
        domain_repo.get_for_user.return_value = UserDomain(
            user_id=1,
            domain="example.com",
            is_wishlist=True,
            notify_expiry=False,
            notify_ns_change=False,
            notify_registrar_change=False,
            notify_status_change=False,
        )
        domain_repo.promote_from_wishlist.return_value = True
        cache_repo = AsyncMock()
        cache_repo.get.return_value = WhoisCache(
            domain="example.com",
            expires_at=datetime(2027, 3, 15, tzinfo=UTC),
            registrar="Example Inc.",
        )
        service = _make_service(domain_repo=domain_repo, cache_repo=cache_repo)

        result = await service.add_for_user(
            user_id=1, notify_days=[30, 7, 1], domain_input="example.com"
        )

        assert result.status == "promoted"
        assert result.normalized_domain == "example.com"
        assert result.whois_data is not None
        domain_repo.promote_from_wishlist.assert_called_once_with(1, "example.com")

    async def test_already_tracked_returns_cached(self) -> None:
        """add_for_user на обычную tracked-строку → status='already_tracked'."""
        domain_repo = AsyncMock()
        domain_repo.count_by_user.return_value = 5
        # get_for_user возвращает обычную tracked-строку
        domain_repo.get_for_user.return_value = UserDomain(
            user_id=1,
            domain="example.com",
            is_wishlist=False,
            notify_expiry=True,
            notify_ns_change=False,
            notify_registrar_change=True,
            notify_status_change=True,
        )
        cache_repo = AsyncMock()
        cache_repo.get.return_value = WhoisCache(
            domain="example.com",
            expires_at=datetime(2027, 3, 15, tzinfo=UTC),
            registrar="Example Inc.",
        )
        service = _make_service(domain_repo=domain_repo, cache_repo=cache_repo)

        result = await service.add_for_user(
            user_id=1, notify_days=[30, 7, 1], domain_input="example.com"
        )

        assert result.status == "already_tracked"
        assert result.normalized_domain == "example.com"
        # promote_from_wishlist НЕ должен вызываться
        domain_repo.promote_from_wishlist.assert_not_called()

    async def test_promote_is_idempotent(self) -> None:
        """Повторный add_for_user после промоута → already_tracked."""
        domain_repo = AsyncMock()
        domain_repo.count_by_user.return_value = 5
        # Первый вызов: get_for_user возвращает wishlist
        wishlist_row = UserDomain(
            user_id=1,
            domain="example.com",
            is_wishlist=True,
            notify_expiry=False,
            notify_ns_change=False,
            notify_registrar_change=False,
            notify_status_change=False,
        )
        # После промоута: обычная tracked-строка
        tracked_row = UserDomain(
            user_id=1,
            domain="example.com",
            is_wishlist=False,
            notify_expiry=True,
            notify_ns_change=False,
            notify_registrar_change=True,
            notify_status_change=True,
        )

        # Первый вызов — wishlist, второй — tracked
        domain_repo.get_for_user.side_effect = [wishlist_row, tracked_row]
        domain_repo.promote_from_wishlist.return_value = True
        cache_repo = AsyncMock()
        cache_repo.get.return_value = None
        service = _make_service(domain_repo=domain_repo, cache_repo=cache_repo)

        result1 = await service.add_for_user(
            user_id=1, notify_days=[30, 7, 1], domain_input="example.com"
        )
        assert result1.status == "promoted"

        result2 = await service.add_for_user(
            user_id=1, notify_days=[30, 7, 1], domain_input="example.com"
        )
        assert result2.status == "already_tracked"
        # promote_from_wishlist вызван только один раз
        assert domain_repo.promote_from_wishlist.call_count == 1

    async def test_new_domain_adds_normally(self) -> None:
        """add_for_user на новый домен (нет записи) → status='added_pending'."""
        domain_repo = AsyncMock()
        domain_repo.count_by_user.return_value = 0
        # get_for_user возвращает None — домена нет
        domain_repo.get_for_user.return_value = None
        cache_repo = AsyncMock()
        cache_repo.get.return_value = None
        facade = AsyncMock()
        service = _make_service(domain_repo=domain_repo, cache_repo=cache_repo, facade=facade)

        result = await service.add_for_user(
            user_id=1, notify_days=[30, 7, 1], domain_input="newdomain.com"
        )

        assert result.status == "added_pending"
        assert result.normalized_domain == "newdomain.com"
        domain_repo.add.assert_called_once_with(1, "newdomain.com")
        # promote_from_wishlist НЕ должен вызываться для нового домена
        domain_repo.promote_from_wishlist.assert_not_called()

    async def test_promote_without_cached_whois(self) -> None:
        """Промоут работает даже если WHOIS-кэш пуст."""
        domain_repo = AsyncMock()
        domain_repo.count_by_user.return_value = 5
        domain_repo.get_for_user.return_value = UserDomain(
            user_id=1,
            domain="example.com",
            is_wishlist=True,
            notify_expiry=False,
            notify_ns_change=False,
            notify_registrar_change=False,
            notify_status_change=False,
        )
        domain_repo.promote_from_wishlist.return_value = True
        cache_repo = AsyncMock()
        cache_repo.get.return_value = None  # Нет кэша
        service = _make_service(domain_repo=domain_repo, cache_repo=cache_repo)

        result = await service.add_for_user(
            user_id=1, notify_days=[30, 7, 1], domain_input="example.com"
        )

        assert result.status == "promoted"
        assert result.whois_data is None
        domain_repo.promote_from_wishlist.assert_called_once()


# ---------------------------------------------------------------------------
# Конец файла
# ---------------------------------------------------------------------------
# Примечание: полноценные тесты репозитория с реальной БД требуют
# фикстуры db_session с PostgreSQL. Здесь мы тестируем бизнес-логику
# DomainService, которая вызывает promote_from_wishlist, через моки.
# ---------------------------------------------------------------------------
