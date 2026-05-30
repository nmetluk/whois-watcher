"""Репозиторий wishlist (ADR 039)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any, cast

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import CursorResult

from src.db.models import WhoisCache, Wishlist
from src.db.repositories.base import BaseRepository
from src.utils.domains import registrable_domain
from src.utils.idn import normalize_domain


class WishlistRepository(BaseRepository):
    """CRUD по таблице ``wishlist``."""

    async def add(self, user_id: int, domain: str) -> Wishlist | None:
        """Добавляет домен в wishlist (UPSERT ON CONFLICT DO NOTHING).

        Returns:
            Wishlist запись или None если уже существовала (конфликт UNIQUE).
        """
        # Нормализуем домен
        normalized = normalize_domain(domain)
        if not normalized:
            return None

        reg_domain = registrable_domain(normalized)
        is_sub = normalized != reg_domain

        stmt = (
            pg_insert(Wishlist)
            .values(
                user_id=user_id,
                domain=normalized,
                registrable_domain=reg_domain,
                is_subdomain=is_sub,
            )
            .on_conflict_do_nothing(index_elements=[Wishlist.user_id, Wishlist.domain])
        )
        result = cast(CursorResult[Any], await self.session.execute(stmt))
        if result.rowcount == 0:  # Уже существовала
            return None

        await self.session.flush()
        select_stmt = select(Wishlist).where(
            Wishlist.user_id == user_id,
            Wishlist.domain == normalized,
        )
        select_result = await self.session.execute(select_stmt)
        return select_result.scalar_one()

    async def remove(self, user_id: int, domain: str) -> bool:
        """Удаляет домен из wishlist.

        Returns:
            True если запись была удалена, False если не найдена.
        """
        normalized = normalize_domain(domain)
        if not normalized:
            return False

        stmt = delete(Wishlist).where(
            Wishlist.user_id == user_id,
            Wishlist.domain == normalized,
        )
        result = cast(CursorResult[Any], await self.session.execute(stmt))
        return result.rowcount > 0

    async def exists(self, user_id: int, domain: str) -> bool:
        """Проверяет наличие домена в wishlist у пользователя."""
        normalized = normalize_domain(domain)
        if not normalized:
            return False

        stmt = select(
            select(Wishlist)
            .where(
                Wishlist.user_id == user_id,
                Wishlist.domain == normalized,
            )
            .exists()
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def count_by_user(self, user_id: int) -> int:
        """Возвращает количество wishlist-записей пользователя."""
        stmt = select(func.count()).where(Wishlist.user_id == user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one() or 0

    async def get_subscribers_for_domain(self, domain: str) -> Sequence[Wishlist]:
        """Возвращает всех подписчиков домена в wishlist.

        Args:
            domain: Домен в любой форме (punycode/UTF-8), нормализуется.
        """
        normalized = normalize_domain(domain)
        if not normalized:
            return []

        reg_domain = registrable_domain(normalized)

        # Ищем и по domain, и по registrable_domain (поддомены тоже)
        stmt = select(Wishlist).where(
            (Wishlist.domain == normalized) | (Wishlist.registrable_domain == reg_domain)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_with_whois(
        self,
        user_id: int,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[tuple[Wishlist, WhoisCache | None]], int]:
        """Возвращает wishlist пользователя с WHOIS-данными (джойн).

        Args:
            user_id: ID пользователя
            limit: Лимит записей
            offset: Сдвиг для пагинации

        Returns:
            (rows, total) где rows — список кортежей (Wishlist, WhoisCache|None)
        """
        # Сначала считаем total
        count_stmt = select(func.count()).where(Wishlist.user_id == user_id)
        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar_one() or 0

        # Основной запрос с LEFT JOIN на whois_cache
        stmt = (
            select(Wishlist, WhoisCache)
            .outerjoin(
                WhoisCache,
                Wishlist.registrable_domain == WhoisCache.domain,
            )
            .where(Wishlist.user_id == user_id)
            .order_by(Wishlist.added_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        # outerjoin делает WhoisCache опциональным на рантайме
        rows = [(row[0], row[1]) for row in result.all()]

        return rows, total

    async def mark_notified(
        self,
        user_id: int,
        domain: str,
        *,
        at: datetime | None = None,
    ) -> None:
        """Удаляет запись после уведомления об освобождении (одноразовость).

        Args:
            user_id: ID пользователя
            domain: Домен
            at: Не используется — оставлен для совместимости API
        """
        normalized = normalize_domain(domain)
        if not normalized:
            return

        stmt = delete(Wishlist).where(
            Wishlist.user_id == user_id,
            Wishlist.domain == normalized,
        )
        await self.session.execute(stmt)
