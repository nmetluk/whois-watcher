"""Тесты ARQ-задачи check_subdomains (TASK-0025 ревью v1)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.db.models import SubdomainEnumCache
from src.subdomains.types import SubdomainEnumError


@pytest.fixture
def mock_sync_redis() -> AsyncMock:
    """Мок sync Redis."""
    return AsyncMock()


@pytest.fixture
def mock_arq_redis() -> AsyncMock:
    """Мок arq Redis."""
    return AsyncMock()


def _ctx(*, sync_redis: AsyncMock, arq_redis: AsyncMock | None = None) -> dict[str, object]:
    """ARQ context для тестов."""
    return {
        "sync_redis": sync_redis,
        "redis": arq_redis or AsyncMock(),
        "bot": AsyncMock(),
    }


class TestCheckSubdomainsFirstFail:
    """Тесты для первого фейла — off-by-one guard (ревью v1)."""

    @pytest.mark.asyncio
    async def test_first_fail_yields_1_hour_next_check(
        self, mock_sync_redis: AsyncMock, mock_arq_redis: AsyncMock
    ) -> None:
        """При первом фейле next_check_at ≈ now + 1 час (fail_count=1 в scheduler)."""
        from src.tasks.check_subdomains import check_subdomains

        ctx = _ctx(sync_redis=mock_sync_redis, arq_redis=mock_arq_redis)

        # Redis set nx=True (acquired)
        mock_sync_redis.set = AsyncMock(return_value=True)

        # Мокаем fetch_subdomains → ошибка
        error_result = SubdomainEnumError(
            registrable_domain="example.com",
            error_type="timeout",
            message="crt.sh timeout",
        )

        # Мокаем старый кэш как None (первый фейл)
        mock_old_cache = None

        mock_session = AsyncMock()

        with patch("src.tasks.check_subdomains.get_session") as mock_get_session:
            mock_get_session.return_value.__aenter__.return_value = mock_session

            # get возвращает None (первый фейл — нет записи)
            async def get_none(*_):
                return mock_old_cache

            mock_session.get = get_none

            # Мокаем update_fail — запоминаем переданный next_check_at
            captured_next_check = []

            async def capture_update(*, next_check_at, **_kwargs):
                captured_next_check.append(next_check_at)

            mock_repo = MagicMock()
            mock_repo.get = get_none
            mock_repo.update_fail = capture_update

            with (
                patch(
                    "src.tasks.check_subdomains.SubdomainEnumCacheRepository",
                    return_value=mock_repo,
                ),
                patch("src.tasks.check_subdomains.fetch_subdomains", return_value=error_result),
            ):
                before = datetime.now(tz=UTC)
                await check_subdomains(ctx, "example.com")
                after = datetime.now(tz=UTC)

                # Проверяем что next_check_at был передан
                assert len(captured_next_check) == 1
                next_check = captured_next_check[0]

                # При fail_count=1 scheduler возвращает 1 час
                expected_min = before + timedelta(minutes=58)  # допуск на execution
                expected_max = after + timedelta(minutes=62)

                assert expected_min <= next_check <= expected_max, (
                    f"next_check_at={next_check} не в диапазоне 1 часа. "
                    f"Ожидается {expected_min}..{expected_max}"
                )

    @pytest.mark.asyncio
    async def test_second_fail_yields_1_hour_next_check(
        self, mock_sync_redis: AsyncMock, mock_arq_redis: AsyncMock
    ) -> None:
        """При втором фейле (был 1) next_check_at ≈ now + 1 час (fail_count=2 в scheduler)."""
        from src.tasks.check_subdomains import check_subdomains

        ctx = _ctx(sync_redis=mock_sync_redis, arq_redis=mock_arq_redis)

        # Redis set nx=True (acquired)
        mock_sync_redis.set = AsyncMock(return_value=True)

        # Мокаем fetch_subdomains → ошибка
        error_result = SubdomainEnumError(
            registrable_domain="example.com",
            error_type="timeout",
            message="crt.sh timeout",
        )

        # Мокаем старый кэш с fail_count=1
        mock_old_cache = MagicMock(spec=SubdomainEnumCache)
        mock_old_cache.fail_count = 1

        mock_session = AsyncMock()

        with patch("src.tasks.check_subdomains.get_session") as mock_get_session:
            mock_get_session.return_value.__aenter__.return_value = mock_session

            # get возвращает старый кэш
            async def get_old(*_):
                return mock_old_cache

            mock_session.get = get_old

            # Мокаем update_fail — запоминаем переданный next_check_at
            captured_next_check = []

            async def capture_update(*, next_check_at, **_kwargs):
                captured_next_check.append(next_check_at)

            mock_repo = MagicMock()
            mock_repo.get = get_old
            mock_repo.update_fail = capture_update

            with (
                patch(
                    "src.tasks.check_subdomains.SubdomainEnumCacheRepository",
                    return_value=mock_repo,
                ),
                patch("src.tasks.check_subdomains.fetch_subdomains", return_value=error_result),
            ):
                before = datetime.now(tz=UTC)
                await check_subdomains(ctx, "example.com")
                after = datetime.now(tz=UTC)

                # Проверяем что next_check_at был передан
                assert len(captured_next_check) == 1
                next_check = captured_next_check[0]

                # При fail_count=2 scheduler тоже возвращает 1 час
                expected_min = before + timedelta(minutes=58)
                expected_max = after + timedelta(minutes=62)

                assert expected_min <= next_check <= expected_max, (
                    f"next_check_at={next_check} не в диапазоне 1 часа. "
                    f"Ожидается {expected_min}..{expected_max}"
                )
