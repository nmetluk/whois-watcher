"""Репозиторий ``audit_log`` (ADR 042, TASK-0057)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, cast

from sqlalchemy import delete, select, text
from sqlalchemy.engine import CursorResult

from src.db.models import AuditLog
from src.db.repositories.base import BaseRepository


class AuditLogRepository(BaseRepository):
    """Append-only журнал инцидентов + очистка по retention (90д)."""

    async def record(
        self,
        *,
        level: str,
        category: str,
        message: str,
        actor: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Записывает событие аудита (инцидент с контекстом).

        Используется через best-effort helper ``src.services.audit.audit()``.
        """
        row = AuditLog(
            level=level,
            category=category,
            message=message,
            actor=actor,
            context=context,
        )
        self.session.add(row)
        await self.session.flush()

    async def delete_older_than(self, days: int) -> int:
        """Удаляет записи старше N дней. Возвращает количество удалённых строк."""
        if days <= 0:
            return 0
        stmt = delete(AuditLog).where(AuditLog.created_at < text(f"now() - interval '{days} days'"))
        result = cast(CursorResult[Any], await self.session.execute(stmt))
        return result.rowcount or 0

    async def get_recent(
        self,
        *,
        limit: int = 100,
        category: str | None = None,
    ) -> Sequence[AuditLog]:
        """Недавние записи (для отладки и отчётов)."""
        stmt = select(AuditLog)
        if category is not None:
            stmt = stmt.where(AuditLog.category == category)
        stmt = stmt.order_by(AuditLog.created_at.desc()).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()
