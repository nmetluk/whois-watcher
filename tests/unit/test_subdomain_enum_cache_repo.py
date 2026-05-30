"""Тесты SubdomainEnumCacheRepository (TASK-0025)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.db.models import SubdomainEnumCache
from src.db.repositories.subdomain_enum_cache import SubdomainEnumCacheRepository


@pytest.fixture
def mock_session() -> AsyncMock:
    """Мок SQLAlchemy сессии."""
    session = AsyncMock()
    return session


@pytest.fixture
def repo(mock_session: AsyncMock) -> SubdomainEnumCacheRepository:
    """Репозиторий с моковой сессией."""
    return SubdomainEnumCacheRepository(mock_session)


class TestSubdomainEnumCacheRepository:
    """Тесты SubdomainEnumCacheRepository."""

    @pytest.mark.asyncio
    async def test_update_fail_calls_upsert_logic(
        self, repo: SubdomainEnumCacheRepository, mock_session: AsyncMock
    ) -> None:
        """update_fail должен вызывать execute с UPSERT-логикой."""

        now = datetime(2026, 5, 30, 12, 0, tzinfo=UTC)

        # Мокаем execute чтобы не падал
        mock_session.execute = AsyncMock()
        mock_session.flush = AsyncMock()

        # Мокаем get чтобы вернуть созданный объект
        mock_cache = MagicMock(spec=SubdomainEnumCache)
        mock_cache.registrable_domain = "example.com"
        mock_cache.fail_count = 1
        mock_cache.last_error = "timeout"
        mock_cache.next_check_at = now
        mock_cache.is_reachable = False

        mock_session.get = AsyncMock(return_value=mock_cache)

        result = await repo.update_fail(
            registrable_domain="example.com",
            error="timeout",
            next_check_at=now,
        )

        # Проверяем что execute был вызван
        assert mock_session.execute.called
        # Проверяем что flush был вызван
        assert mock_session.flush.called
        # Проверяем что get был вызван для получения обновлённой записи
        assert mock_session.get.called

        # Результат — обновлённый кэш
        assert result.registrable_domain == "example.com"
        assert result.fail_count == 1

    @pytest.mark.asyncio
    async def test_update_fail_returns_subdomain_enum_cache(
        self, repo: SubdomainEnumCacheRepository, mock_session: AsyncMock
    ) -> None:
        """update_fail должен возвращать SubdomainEnumCache."""
        now = datetime(2026, 5, 30, 12, 0, tzinfo=UTC)

        mock_session.execute = AsyncMock()
        mock_session.flush = AsyncMock()

        mock_cache = MagicMock(spec=SubdomainEnumCache)
        mock_cache.registrable_domain = "example.com"
        mock_cache.fail_count = 2

        mock_session.get = AsyncMock(return_value=mock_cache)

        result = await repo.update_fail(
            registrable_domain="example.com",
            error="error",
            next_check_at=now,
        )

        assert isinstance(result, MagicMock)  # мок SubdomainEnumCache
        assert result.registrable_domain == "example.com"
