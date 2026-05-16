"""Тесты ARQ cron-задачи ``expiry_notification_scheduler``.

Логика — SQL внутри Postgres, поэтому здесь проверяем только:

- пустой result → нет enqueue
- N строк → enqueue N раз с правильными аргументами
- значения из строки правильно передаются в задачу
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.tasks import expiry_scheduler


def _async_cm(value: object) -> MagicMock:
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=value)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


def _row(user_id: int, domain: str, days: int) -> SimpleNamespace:
    return SimpleNamespace(
        user_id=user_id,
        domain=domain,
        days_before=days,
        expires_at=datetime(2027, 3, 15, tzinfo=UTC),
    )


@pytest.fixture
def session_and_redis() -> Iterator[tuple[MagicMock, AsyncMock]]:
    with patch.object(expiry_scheduler, "get_session") as gs:
        session = MagicMock()
        session.execute = AsyncMock()
        gs.return_value = _async_cm(session)
        arq_redis = AsyncMock()
        yield session, arq_redis


class TestExpiryScheduler:
    async def test_no_rows_no_enqueue(self, session_and_redis: tuple[MagicMock, AsyncMock]) -> None:
        session, arq_redis = session_and_redis
        result = MagicMock()
        result.all.return_value = []
        session.execute.return_value = result

        await expiry_scheduler.expiry_notification_scheduler({"redis": arq_redis})

        arq_redis.enqueue_job.assert_not_called()

    async def test_each_row_becomes_one_job(
        self, session_and_redis: tuple[MagicMock, AsyncMock]
    ) -> None:
        session, arq_redis = session_and_redis
        result = MagicMock()
        result.all.return_value = [
            _row(1, "a.ru", 30),
            _row(1, "a.ru", 7),
            _row(2, "b.com", 1),
        ]
        session.execute.return_value = result

        await expiry_scheduler.expiry_notification_scheduler({"redis": arq_redis})

        assert arq_redis.enqueue_job.await_count == 3
        # Проверяем что первый вызов содержит правильные аргументы
        first_args = arq_redis.enqueue_job.await_args_list[0].args
        assert first_args == ("send_expiry_reminder", 1, "a.ru", 30)
        last_args = arq_redis.enqueue_job.await_args_list[2].args
        assert last_args == ("send_expiry_reminder", 2, "b.com", 1)
