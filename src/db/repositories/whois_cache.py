"""Репозиторий общего кэша WHOIS (ADR 006)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any, cast

from sqlalchemy import delete, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import CursorResult

from src.db.models import UserDomain, WhoisCache
from src.db.repositories.base import BaseRepository


class WhoisCacheRepository(BaseRepository):
    """CRUD по таблице ``whois_cache`` и спецзапросы для воркеров."""

    async def get(self, domain: str) -> WhoisCache | None:
        """Возвращает запись кэша или ``None``."""
        result = await self.session.get(WhoisCache, domain)
        return result

    async def upsert(self, domain: str, /, **fields: Any) -> WhoisCache:
        """UPSERT через PostgreSQL ON CONFLICT (domain) DO UPDATE.

        Все переданные поля попадают в SET. Имя ``domain`` обязательное
        (это PK). Возвращает свежую запись.
        """
        if not fields:
            # Чистый insert-if-missing, без UPDATE.
            stmt = (
                pg_insert(WhoisCache)
                .values(domain=domain)
                .on_conflict_do_nothing(index_elements=[WhoisCache.domain])
            )
            await self.session.execute(stmt)
        else:
            stmt = (
                pg_insert(WhoisCache)
                .values(domain=domain, **fields)
                .on_conflict_do_update(
                    index_elements=[WhoisCache.domain],
                    set_=fields,
                )
            )
            await self.session.execute(stmt)
        # Перечитываем после upsert, чтобы получить заполненные дефолты и тип-конвертацию.
        await self.session.flush()
        refreshed = await self.session.get(WhoisCache, domain)
        assert refreshed is not None  # invariant: только что вставили
        return refreshed

    async def get_due_for_check(self, *, limit: int) -> Sequence[WhoisCache]:
        """Доменные записи, у которых ``next_check_at <= now()``.

        Используется планировщиком каждые 5 минут (см. docs/architecture.md).
        """
        stmt = (
            select(WhoisCache)
            .where(
                WhoisCache.next_check_at.is_not(None),
                WhoisCache.next_check_at <= text("now()"),
            )
            .order_by(WhoisCache.next_check_at.asc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def delete_orphans(self) -> int:
        """Удаляет записи кэша, на которые никто не подписан (ADR 020).

        Возвращает количество удалённых строк.
        """
        subq = select(UserDomain.domain).distinct().scalar_subquery()
        stmt = delete(WhoisCache).where(WhoisCache.domain.not_in(subq))
        result = cast(CursorResult[Any], await self.session.execute(stmt))
        return result.rowcount or 0

    async def update_fail(
        self,
        domain: str,
        error: str,
        *,
        next_check_at: datetime | None = None,
    ) -> None:
        """Регистрирует неудачную попытку WHOIS-запроса.

        Инкрементит ``fail_count``, обновляет ``last_error``, ``fetched_at`` и
        (опционально) ``next_check_at``. Расчёт следующего интервала — забота
        вызывающей стороны (см. ``src/whois/scheduler.py``).
        """
        values: dict[str, Any] = {
            "fail_count": WhoisCache.fail_count + 1,
            "last_error": error,
            "fetched_at": text("now()"),
        }
        if next_check_at is not None:
            values["next_check_at"] = next_check_at
        stmt = update(WhoisCache).where(WhoisCache.domain == domain).values(**values)
        await self.session.execute(stmt)
