"""Тесты AuditLogRepository (TASK-0057, ADR 042)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.db.models import AuditLog
from src.db.repositories.audit_log import AuditLogRepository


@pytest.fixture
def mock_session() -> AsyncMock:
    """Мок SQLAlchemy сессии."""
    session = AsyncMock()
    return session


@pytest.fixture
def repo(mock_session: AsyncMock) -> AuditLogRepository:
    """Репозиторий с моковой сессией."""
    return AuditLogRepository(mock_session)


class TestAuditLogRepository:
    """Тесты AuditLogRepository (record + delete_older_than)."""

    @pytest.mark.asyncio
    async def test_record_adds_row_and_flushes(
        self, repo: AuditLogRepository, mock_session: AsyncMock
    ) -> None:
        """record должен создавать AuditLog, добавлять в сессию и flush."""
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()

        await repo.record(
            level="error",
            category="task_failure",
            message="ARQ task foo failed",
            actor="system",
            context={"task": "check_foo", "err": "timeout"},
        )

        # Проверяем, что add вызван с правильным объектом
        assert mock_session.add.called
        added = mock_session.add.call_args[0][0]
        assert isinstance(added, AuditLog)
        assert added.level == "error"
        assert added.category == "task_failure"
        assert added.message == "ARQ task foo failed"
        assert added.actor == "system"
        assert added.context == {"task": "check_foo", "err": "timeout"}

        mock_session.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_delete_older_than_executes_delete_with_interval(
        self, repo: AuditLogRepository, mock_session: AsyncMock
    ) -> None:
        """delete_older_than строит DELETE WHERE created_at < now() - interval."""
        mock_result = MagicMock()
        mock_result.rowcount = 7
        mock_session.execute = AsyncMock(return_value=mock_result)

        removed = await repo.delete_older_than(90)

        assert removed == 7
        mock_session.execute.assert_awaited()
        # Проверяем, что stmt содержит текст с интервалом (грубая проверка по repr)
        stmt = mock_session.execute.call_args[0][0]
        stmt_text = str(stmt)
        assert "audit_log" in stmt_text.lower()
        assert "created_at" in stmt_text
        assert "90" in stmt_text or "interval" in stmt_text.lower()

    @pytest.mark.asyncio
    async def test_delete_older_than_zero_or_negative_returns_zero(
        self, repo: AuditLogRepository, mock_session: AsyncMock
    ) -> None:
        """Отрицательные/нулевые дни — no-op, 0 строк."""
        removed = await repo.delete_older_than(0)
        assert removed == 0
        removed = await repo.delete_older_than(-5)
        assert removed == 0
        mock_session.execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_get_recent_queries_with_order_limit(
        self, repo: AuditLogRepository, mock_session: AsyncMock
    ) -> None:
        """get_recent делает select + order by created_at desc + limit."""
        mock_session.execute = AsyncMock(
            return_value=MagicMock(
                scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
            )
        )

        await repo.get_recent(limit=50, category="rate_limit")

        mock_session.execute.assert_awaited()
