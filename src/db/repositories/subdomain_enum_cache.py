"""Репозиторий кэша subdomain enumeration (ADR 037)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any, cast

from sqlalchemy import delete, func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import CursorResult

from src.db.models import SubdomainEnumCache, User, UserDomain
from src.db.repositories.base import BaseRepository


class SubdomainEnumCacheRepository(BaseRepository):
    """CRUD по таблице ``subdomain_enum_cache``.

    Хранит результаты enumeration per registrable-домен. Повторные
    вызовы ``/subdomains`` в окне TTL не бьют crt.sh.
    """

    async def get(self, registrable_domain: str) -> SubdomainEnumCache | None:
        """Получить запись по registrable-домену."""
        return await self.session.get(SubdomainEnumCache, registrable_domain)

    async def upsert(self, registrable_domain: str, /, **fields: Any) -> SubdomainEnumCache:
        """UPSERT через ``ON CONFLICT (registrable_domain) DO UPDATE``.

        Если поля не переданы — простой `INSERT … DO NOTHING` (для
        создания пустой записи; типично из планировщика, когда новый
        registrable впервые попадает в scheduler).
        """
        if not fields:
            stmt = (
                pg_insert(SubdomainEnumCache)
                .values(registrable_domain=registrable_domain)
                .on_conflict_do_nothing(index_elements=[SubdomainEnumCache.registrable_domain])
            )
            await self.session.execute(stmt)
        else:
            stmt = (
                pg_insert(SubdomainEnumCache)
                .values(registrable_domain=registrable_domain, **fields)
                .on_conflict_do_update(
                    index_elements=[SubdomainEnumCache.registrable_domain],
                    set_=fields,
                )
            )
            await self.session.execute(stmt)
        await self.session.flush()
        refreshed = await self.session.get(SubdomainEnumCache, registrable_domain)
        assert refreshed is not None  # invariant
        return refreshed

    async def update_fail(
        self,
        registrable_domain: str,
        error: str,
        *,
        next_check_at: datetime,
    ) -> SubdomainEnumCache:
        """Зарегистрировать неудачную проверку.

        UPSERT-семантика: при первом фейле создаёт запись с ``fail_count=1``,
        при повторном — инкрементит ``fail_count``. Также пишет ``last_error``,
        ``next_check_at``, ``is_reachable=False``.
        """
        stmt = (
            pg_insert(SubdomainEnumCache)
            .values(
                registrable_domain=registrable_domain,
                fail_count=1,
                last_error=error,
                next_check_at=next_check_at,
                is_reachable=False,
            )
            .on_conflict_do_update(
                index_elements=[SubdomainEnumCache.registrable_domain],
                set_={
                    "fail_count": SubdomainEnumCache.fail_count + 1,
                    "last_error": error,
                    "next_check_at": next_check_at,
                    "is_reachable": False,
                },
            )
        )
        await self.session.execute(stmt)
        await self.session.flush()
        refreshed = await self.session.get(SubdomainEnumCache, registrable_domain)
        assert refreshed is not None  # invariant
        return refreshed

    async def get_due_for_check(self, *, limit: int) -> Sequence[SubdomainEnumCache]:
        """Registrable-записи у которых ``next_check_at <= now()`` И есть
        хотя бы один подписчик с ``track_subdomains=true`` (включая не-muted).

        Ограничен ``limit`` — за один tick планировщика не берём больше.
        Сортировка по ``next_check_at ASC`` — старшие первыми.
        """
        # EXISTS против JOIN — короче, эквивалентно.
        # Фильтр по registrable_domain (не domain!), т.к. SubdomainEnumCache PK — registrable
        subq = (
            select(UserDomain.id)
            .where(
                UserDomain.registrable_domain == SubdomainEnumCache.registrable_domain,
                UserDomain.track_subdomains.is_(True),
                UserDomain.is_muted.is_(False),
            )
            .limit(1)
        )
        stmt = (
            select(SubdomainEnumCache)
            .where(
                SubdomainEnumCache.next_check_at <= text("now()"),
                subq.exists(),
            )
            .order_by(SubdomainEnumCache.next_check_at.asc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_min_check_interval(self, registrable_domain: str) -> int:
        """Минимальный интервал проверки (дни) среди подписчиков
        ``track_subdomains=true`` на registrable-домен.

        Берёт ``COALESCE(ud.subdomain_check_interval_override,
        u.subdomain_check_interval_days)`` и возвращает минимум, но не менее 1.
        Если нет подписчиков — возвращает 7 (дефолт).
        """
        # Джойн User для user.default интервала
        subq = (
            select(
                func.coalesce(
                    UserDomain.subdomain_check_interval_override,
                    User.subdomain_check_interval_days,
                ).label("interval")
            )
            .join(User, User.id == UserDomain.user_id)
            .where(
                UserDomain.registrable_domain == registrable_domain,
                UserDomain.track_subdomains.is_(True),
                UserDomain.is_muted.is_(False),
            )
        )
        result = await self.session.execute(subq)
        intervals = result.scalars().all()

        if not intervals:
            return 7  # дефолт

        return max(1, min(intervals))

    async def delete_orphans(self) -> int:
        """Удаляет subdomain_enum_cache записи, на которые никто не подписан.

        Используется для периодической очистки (аналог ADR 020 для whois_cache).
        """
        # Сирота — registrable_domain, на который нет ни одной записи в user_domains
        # с matching registrable_domain
        subq = select(UserDomain.registrable_domain).distinct().scalar_subquery()
        stmt = delete(SubdomainEnumCache).where(SubdomainEnumCache.registrable_domain.not_in(subq))
        result = cast(CursorResult[Any], await self.session.execute(stmt))
        return result.rowcount or 0
