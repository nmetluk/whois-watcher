"""Репозиторий кэша deep email (TASK-0039, ADR 040).

Короткий TTL, on-demand только. Хранит результаты тяжёлого сбора
(SPF recursion, MTA-STS policy, DANE per-MX и т.д.) чтобы повторные
нажатия кнопки «Глубокий e-mail» в окне TTL не били сеть.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.db.models import EmailDeepCache
from src.db.repositories.base import BaseRepository


class EmailDeepCacheRepository(BaseRepository):
    """CRUD по таблице ``email_deep_cache``."""

    async def get(self, domain: str) -> EmailDeepCache | None:
        """Получить запись по domain."""
        return await self.session.get(EmailDeepCache, domain)

    async def upsert(self, domain: str, /, **fields: Any) -> EmailDeepCache:
        """UPSERT через ON CONFLICT (domain) DO UPDATE."""
        if not fields:
            stmt = (
                pg_insert(EmailDeepCache)
                .values(domain=domain)
                .on_conflict_do_nothing(index_elements=[EmailDeepCache.domain])
            )
            await self.session.execute(stmt)
        else:
            stmt = (
                pg_insert(EmailDeepCache)
                .values(domain=domain, **fields)
                .on_conflict_do_update(
                    index_elements=[EmailDeepCache.domain],
                    set_=fields,
                )
            )
            await self.session.execute(stmt)
        await self.session.flush()
        refreshed = await self.session.get(EmailDeepCache, domain)
        assert refreshed is not None  # invariant
        return refreshed

    async def update_fail(
        self,
        domain: str,
        error: str,
        *,
        next_check_at: datetime,
    ) -> EmailDeepCache:
        """Зарегистрировать неудачную попытку deep email сбора.

        Инкрементит fail_count, пишет last_error / next_check_at / is_reachable=False.
        """
        stmt = (
            pg_insert(EmailDeepCache)
            .values(
                domain=domain,
                fail_count=1,
                last_error=error,
                next_check_at=next_check_at,
                is_reachable=False,
            )
            .on_conflict_do_update(
                index_elements=[EmailDeepCache.domain],
                set_={
                    "fail_count": EmailDeepCache.fail_count + 1,
                    "last_error": error,
                    "next_check_at": next_check_at,
                    "is_reachable": False,
                },
            )
        )
        await self.session.execute(stmt)
        await self.session.flush()
        refreshed = await self.session.get(EmailDeepCache, domain)
        assert refreshed is not None  # invariant
        return refreshed


__all__ = ["EmailDeepCacheRepository"]
