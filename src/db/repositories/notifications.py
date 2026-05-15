"""Репозиторий ``sent_notifications`` — журнал отправленных уведомлений."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.db.models import SentNotification
from src.db.repositories.base import BaseRepository


class NotificationRepository(BaseRepository):
    """Журнал уведомлений с UNIQUE-защитой от дублей."""

    async def record_sent(
        self,
        *,
        user_id: int,
        domain: str,
        notification_type: str,
        days_before: int | None = None,
        expires_at: datetime | None = None,
    ) -> bool:
        """Регистрирует факт отправки. Возвращает ``True`` если запись новая.

        Использует ``ON CONFLICT DO NOTHING`` на UNIQUE-индексе
        ``uq_sent_notifications_dedup``: если такое уведомление уже
        отправлялось — возвращаем ``False`` (caller может пропустить send).
        """
        stmt = (
            pg_insert(SentNotification)
            .values(
                user_id=user_id,
                domain=domain,
                notification_type=notification_type,
                days_before=days_before,
                expires_at=expires_at,
            )
            .on_conflict_do_nothing(constraint="uq_sent_notifications_dedup")
            .returning(SentNotification.id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def was_sent(
        self,
        *,
        user_id: int,
        domain: str,
        notification_type: str,
        days_before: int | None = None,
        expires_at: datetime | None = None,
    ) -> bool:
        """True, если такое уведомление уже отправлялось.

        NULL-сравнения в ключах UNIQUE — через ``is_``: для days_before и
        expires_at NULL и значение это разные кейсы (Postgres трактует
        NULL = NULL как FALSE).
        """
        conditions = [
            SentNotification.user_id == user_id,
            SentNotification.domain == domain,
            SentNotification.notification_type == notification_type,
        ]
        if days_before is None:
            conditions.append(SentNotification.days_before.is_(None))
        else:
            conditions.append(SentNotification.days_before == days_before)
        if expires_at is None:
            conditions.append(SentNotification.expires_at.is_(None))
        else:
            conditions.append(SentNotification.expires_at == expires_at)

        stmt = select(SentNotification.id).where(*conditions).limit(1)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def get_recent(
        self,
        user_id: int,
        *,
        limit: int = 20,
    ) -> Sequence[SentNotification]:
        """Недавние уведомления пользователя (для отладки / истории)."""
        stmt = (
            select(SentNotification)
            .where(SentNotification.user_id == user_id)
            .order_by(SentNotification.sent_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()
