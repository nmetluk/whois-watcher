"""Тесты SubdomainEnumCacheRepository (TASK-0025, TASK-0028)."""

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


class TestSubdomainEnumCacheRepositoryScheduler:
    """Тесты методов для scheduler (TASK-0028, ADR 038)."""

    @pytest.mark.asyncio
    async def test_get_due_for_check_returns_sequence(
        self, repo: SubdomainEnumCacheRepository, mock_session: AsyncMock
    ) -> None:
        """get_due_for_check должен возвращать sequence SubdomainEnumCache."""
        # Мокаем результат execute
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []

        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.get_due_for_check(limit=500)

        assert isinstance(result, list)
        # Проверяем что execute был вызван
        assert mock_session.execute.called

    @pytest.mark.asyncio
    async def test_get_min_check_interval_returns_default_when_no_subscribers(
        self, repo: SubdomainEnumCacheRepository, mock_session: AsyncMock
    ) -> None:
        """get_min_check_interval должен возвращать 7 при отсутствии подписчиков."""
        # Мокаем результат execute (пустой результат)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []

        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.get_min_check_interval("example.com")

        assert result == 7  # дефолт

    @pytest.mark.asyncio
    async def test_get_min_check_interval_returns_min_from_subscribers(
        self, repo: SubdomainEnumCacheRepository, mock_session: AsyncMock
    ) -> None:
        """get_min_check_interval должен возвращать минимум из интервалов подписчиков."""
        # Мокаем результат execute с интервалами [3, 7, 14]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [3, 7, 14]

        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.get_min_check_interval("example.com")

        assert result == 3  # минимум

    @pytest.mark.asyncio
    async def test_get_min_check_interval_floor_at_1(
        self, repo: SubdomainEnumCacheRepository, mock_session: AsyncMock
    ) -> None:
        """get_min_check_interval должен возвращать минимум 1 (floor)."""
        # Мокаем результат execute с интервалом 0
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [0]

        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.get_min_check_interval("example.com")

        assert result == 1  # floor 1 день
