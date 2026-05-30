"""Тесты ``src.services.domains.DomainService``.

Репозитории мокаются — БД здесь не нужна. Проверяем правила бизнес-логики:
лимит, дубль, нормализация, ветвление по наличию данных в общем кэше.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from src.config.limits import Limits
from src.db.models import UserDomain, WhoisCache
from src.services.domains import DomainService


def _limits(*, max_domains: int = 100) -> Limits:
    """Дефолтные лимиты с переопределённым лимитом для тестов «limit_reached»."""
    return Limits(max_domains_per_user=max_domains)


def _make_service(
    *,
    domain_repo: AsyncMock,
    cache_repo: AsyncMock,
    facade: AsyncMock | None = None,
    limits: Limits | None = None,
) -> DomainService:
    return DomainService(
        domain_repo=domain_repo,
        cache_repo=cache_repo,
        facade=facade or AsyncMock(),
        limits=limits or _limits(),
    )


# ---------------------------------------------------------------------------
# add_for_user
# ---------------------------------------------------------------------------


class TestAddForUser:
    async def test_invalid_domain(self) -> None:
        service = _make_service(domain_repo=AsyncMock(), cache_repo=AsyncMock())
        result = await service.add_for_user(
            user_id=1, notify_days=[30, 7, 1], domain_input="not a domain!!"
        )
        assert result.status == "invalid_domain"

    async def test_limit_reached(self) -> None:
        domain_repo = AsyncMock()
        domain_repo.count_by_user.return_value = 100
        service = _make_service(
            domain_repo=domain_repo, cache_repo=AsyncMock(), limits=_limits(max_domains=100)
        )
        result = await service.add_for_user(
            user_id=1, notify_days=[30, 7, 1], domain_input="example.com"
        )
        assert result.status == "limit_reached"
        assert result.limit == 100
        # ``add`` НЕ вызвался
        domain_repo.add.assert_not_called()

    async def test_already_tracked_returns_cached(self) -> None:
        domain_repo = AsyncMock()
        domain_repo.count_by_user.return_value = 5
        # get_for_user возвращает обычную tracked-строку
        domain_repo.get_for_user.return_value = UserDomain(
            user_id=1,
            domain="example.com",
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
        assert result.whois_data is not None
        assert result.whois_data.registrar == "Example Inc."
        # ``add`` НЕ должен вызываться повторно
        domain_repo.add.assert_not_called()

    async def test_added_with_existing_cache(self) -> None:
        """Домен в общем кэше уже есть → status='added' + whois_data."""
        domain_repo = AsyncMock()
        domain_repo.count_by_user.return_value = 0
        # get_for_user возвращает None — домена нет у пользователя
        domain_repo.get_for_user.return_value = None
        cache_repo = AsyncMock()
        cache_repo.get.return_value = WhoisCache(
            domain="example.com",
            expires_at=datetime(2027, 3, 15, tzinfo=UTC),
            registrar="Example Inc.",
        )
        facade = AsyncMock()
        service = _make_service(domain_repo=domain_repo, cache_repo=cache_repo, facade=facade)
        result = await service.add_for_user(
            user_id=1, notify_days=[30, 7, 1], domain_input="example.com"
        )
        assert result.status == "added"
        assert result.whois_data is not None
        assert result.whois_data.expires_at == datetime(2027, 3, 15, tzinfo=UTC)
        domain_repo.add.assert_called_once()
        facade.enqueue_check.assert_not_called()

    async def test_added_pending_when_cache_empty(self) -> None:
        """Домена нет в общем кэше → status='added_pending', задача в очереди."""
        domain_repo = AsyncMock()
        domain_repo.count_by_user.return_value = 0
        # get_for_user возвращает None — домена нет у пользователя
        domain_repo.get_for_user.return_value = None
        cache_repo = AsyncMock()
        cache_repo.get.return_value = None
        facade = AsyncMock()
        service = _make_service(domain_repo=domain_repo, cache_repo=cache_repo, facade=facade)
        result = await service.add_for_user(
            user_id=1, notify_days=[30, 7, 1], domain_input="example.com"
        )
        assert result.status == "added_pending"
        cache_repo.upsert.assert_called_once_with("example.com")
        facade.enqueue_check.assert_called_once_with("example.com")

    async def test_added_pending_when_cache_has_no_expiry(self) -> None:
        """Запись в кэше есть, но expires_at=None → тоже pending (нужна свежая проверка)."""
        domain_repo = AsyncMock()
        domain_repo.count_by_user.return_value = 0
        # get_for_user возвращает None — домена нет у пользователя
        domain_repo.get_for_user.return_value = None
        cache_repo = AsyncMock()
        cache_repo.get.return_value = WhoisCache(domain="example.com", expires_at=None)
        facade = AsyncMock()
        service = _make_service(domain_repo=domain_repo, cache_repo=cache_repo, facade=facade)
        result = await service.add_for_user(
            user_id=1, notify_days=[30, 7, 1], domain_input="example.com"
        )
        assert result.status == "added_pending"
        facade.enqueue_check.assert_called_once()

    async def test_domain_normalization(self) -> None:
        """``Example.COM`` → ``example.com``: проверяем нормализацию ввода."""
        domain_repo = AsyncMock()
        domain_repo.count_by_user.return_value = 0
        # get_for_user возвращает None — домена нет у пользователя
        domain_repo.get_for_user.return_value = None
        cache_repo = AsyncMock()
        cache_repo.get.return_value = None
        service = _make_service(domain_repo=domain_repo, cache_repo=cache_repo)
        result = await service.add_for_user(
            user_id=1, notify_days=[30, 7, 1], domain_input="EXAMPLE.com"
        )
        assert result.normalized_domain == "example.com"
        domain_repo.add.assert_called_once_with(1, "example.com")


# ---------------------------------------------------------------------------
# remove_for_user
# ---------------------------------------------------------------------------


class TestRemoveForUser:
    async def test_removed(self) -> None:
        domain_repo = AsyncMock()
        domain_repo.remove.return_value = True
        service = _make_service(domain_repo=domain_repo, cache_repo=AsyncMock())
        result = await service.remove_for_user(user_id=1, domain_input="example.com")
        assert result.status == "removed"
        assert result.normalized_domain == "example.com"

    async def test_not_tracked(self) -> None:
        domain_repo = AsyncMock()
        domain_repo.remove.return_value = False
        service = _make_service(domain_repo=domain_repo, cache_repo=AsyncMock())
        result = await service.remove_for_user(user_id=1, domain_input="example.com")
        assert result.status == "not_tracked"

    async def test_invalid_domain(self) -> None:
        domain_repo = AsyncMock()
        service = _make_service(domain_repo=domain_repo, cache_repo=AsyncMock())
        result = await service.remove_for_user(user_id=1, domain_input="@@@")
        assert result.status == "invalid_domain"
        domain_repo.remove.assert_not_called()


# ---------------------------------------------------------------------------
# list_for_user
# ---------------------------------------------------------------------------


class TestListForUser:
    async def test_pagination_passes_offset(self) -> None:
        domain_repo = AsyncMock()
        domain_repo.list_with_whois_filtered.return_value = ([], 0)
        service = _make_service(domain_repo=domain_repo, cache_repo=AsyncMock())
        await service.list_for_user(user_id=1, page=3, page_size=20)
        domain_repo.list_with_whois_filtered.assert_called_once()
        kwargs = domain_repo.list_with_whois_filtered.call_args.kwargs
        assert kwargs["limit"] == 20
        assert kwargs["offset"] == 60
        assert kwargs["filter_type"] == "all"

    async def test_returns_rows_and_total(self) -> None:
        domain_repo = AsyncMock()
        rows = [(UserDomain(user_id=1, domain="example.com"), None)]
        domain_repo.list_with_whois_filtered.return_value = (rows, 1)
        service = _make_service(domain_repo=domain_repo, cache_repo=AsyncMock())
        page = await service.list_for_user(user_id=1, page=0, page_size=50)
        assert page.total == 1
        assert page.rows == rows
        assert page.is_empty is False

    @pytest.mark.parametrize("filter_type", ["all", "expiring", "no_data", "muted"])
    async def test_filter_passthrough(self, filter_type: str) -> None:
        domain_repo = AsyncMock()
        domain_repo.list_with_whois_filtered.return_value = ([], 0)
        service = _make_service(domain_repo=domain_repo, cache_repo=AsyncMock())
        await service.list_for_user(
            user_id=1,
            page=0,
            page_size=50,
            filter_type=filter_type,  # type: ignore[arg-type]
        )
        assert domain_repo.list_with_whois_filtered.call_args.kwargs["filter_type"] == filter_type
