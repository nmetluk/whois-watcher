"""Репозиторий общего кэша SSL-сертификатов (ADR 030)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any, cast

from sqlalchemy import delete, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import CursorResult

from src.db.models import SSLCache, UserDomain
from src.db.repositories.base import BaseRepository


class SSLCacheRepository(BaseRepository):
    """CRUD по таблице ``ssl_cache`` + выборка для scheduler-tick."""

    async def get(self, domain: str) -> SSLCache | None:
        return await self.session.get(SSLCache, domain)

    async def upsert(self, domain: str, /, **fields: Any) -> SSLCache:
        """UPSERT через ``ON CONFLICT (domain) DO UPDATE``.

        Если поля не переданы — простой `INSERT … DO NOTHING` (для
        создания пустой записи; типично из планировщика, когда новый
        домен впервые попадает в ssl_scheduler).
        """
        if not fields:
            stmt = (
                pg_insert(SSLCache)
                .values(domain=domain)
                .on_conflict_do_nothing(index_elements=[SSLCache.domain])
            )
            await self.session.execute(stmt)
        else:
            stmt = (
                pg_insert(SSLCache)
                .values(domain=domain, **fields)
                .on_conflict_do_update(
                    index_elements=[SSLCache.domain],
                    set_=fields,
                )
            )
            await self.session.execute(stmt)
        await self.session.flush()
        refreshed = await self.session.get(SSLCache, domain)
        assert refreshed is not None  # invariant
        return refreshed

    async def get_due_for_check(self, *, limit: int) -> Sequence[SSLCache]:
        """Доменные записи у которых ``next_check_at <= now()`` И есть
        хотя бы один подписчик с ``track_ssl=true`` (включая не-muted).

        Ограничен ``limit`` — за один tick планировщика не берём больше.
        Сортировка по ``next_check_at ASC`` — старшие первыми.
        """
        # Используем EXISTS вместо JOIN/GROUP BY — короче, эквивалентно.
        subq = (
            select(UserDomain.id)
            .where(
                UserDomain.domain == SSLCache.domain,
                UserDomain.track_ssl.is_(True),
                UserDomain.is_muted.is_(False),
            )
            .limit(1)
        )
        stmt = (
            select(SSLCache)
            .where(
                SSLCache.next_check_at <= text("now()"),
                subq.exists(),
            )
            .order_by(SSLCache.next_check_at.asc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def update_fail(
        self,
        domain: str,
        error: str,
        *,
        next_check_at: datetime,
    ) -> None:
        """Зарегистрировать неудачную проверку. Инкрементит ``fail_count``,
        пишет ``last_error``/``last_checked_at``/``next_check_at``."""
        stmt = (
            update(SSLCache)
            .where(SSLCache.domain == domain)
            .values(
                fail_count=SSLCache.fail_count + 1,
                last_error=error,
                last_checked_at=text("now()"),
                next_check_at=next_check_at,
            )
        )
        await self.session.execute(stmt)

    async def delete_orphans(self) -> int:
        """Удаляет ssl_cache записи, на которые никто не подписан
        (аналог ADR 020 для whois_cache).
        """
        subq = select(UserDomain.domain).distinct().scalar_subquery()
        stmt = delete(SSLCache).where(SSLCache.domain.not_in(subq))
        result = cast(CursorResult[Any], await self.session.execute(stmt))
        return result.rowcount or 0
