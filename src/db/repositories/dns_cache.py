"""Репозиторий общего кэша DNS-записей (ADR 032)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any, cast

from sqlalchemy import delete, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import CursorResult

from src.db.models import DNSCache, UserDomain
from src.db.repositories.base import BaseRepository


class DNSCacheRepository(BaseRepository):
    """CRUD по таблице ``dns_cache`` + выборка для scheduler-tick."""

    async def get(self, domain: str) -> DNSCache | None:
        return await self.session.get(DNSCache, domain)

    async def upsert(self, domain: str, /, **fields: Any) -> DNSCache:
        """UPSERT через ``ON CONFLICT (domain) DO UPDATE``.

        Если поля не переданы — простой ``INSERT … DO NOTHING`` (для
        создания пустой записи; типично из планировщика, когда новый
        домен впервые попадает в dns_scheduler).
        """
        if not fields:
            stmt = (
                pg_insert(DNSCache)
                .values(domain=domain)
                .on_conflict_do_nothing(index_elements=[DNSCache.domain])
            )
            await self.session.execute(stmt)
        else:
            stmt = (
                pg_insert(DNSCache)
                .values(domain=domain, **fields)
                .on_conflict_do_update(
                    index_elements=[DNSCache.domain],
                    set_=fields,
                )
            )
            await self.session.execute(stmt)
        await self.session.flush()
        refreshed = await self.session.get(DNSCache, domain)
        assert refreshed is not None  # invariant
        return refreshed

    async def get_due_for_check(self, *, limit: int) -> Sequence[DNSCache]:
        """Доменные записи у которых ``next_check_at <= now()`` И есть
        хотя бы один подписчик с ``track_dns=true AND NOT is_muted``.

        Ограничен ``limit`` — за один tick планировщика не берём больше.
        Сортировка по ``next_check_at ASC`` — старшие первыми.
        """
        # EXISTS-подзапрос — короче чем JOIN/GROUP BY (паттерн ssl_cache).
        subq = (
            select(UserDomain.id)
            .where(
                UserDomain.domain == DNSCache.domain,
                UserDomain.track_dns.is_(True),
                UserDomain.is_muted.is_(False),
            )
            .limit(1)
        )
        stmt = (
            select(DNSCache)
            .where(
                DNSCache.next_check_at <= text("now()"),
                subq.exists(),
            )
            .order_by(DNSCache.next_check_at.asc())
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
        пишет ``last_error``/``last_checked_at``/``next_check_at``.
        """
        stmt = (
            update(DNSCache)
            .where(DNSCache.domain == domain)
            .values(
                fail_count=DNSCache.fail_count + 1,
                last_error=error,
                last_checked_at=text("now()"),
                next_check_at=next_check_at,
            )
        )
        await self.session.execute(stmt)

    async def delete_orphans(self) -> int:
        """Удаляет ``dns_cache``-записи, на которые никто не подписан
        (аналог ADR 020 для whois_cache и параллельно ssl_cache).
        """
        subq = select(UserDomain.domain).distinct().scalar_subquery()
        stmt = delete(DNSCache).where(DNSCache.domain.not_in(subq))
        result = cast(CursorResult[Any], await self.session.execute(stmt))
        return result.rowcount or 0
