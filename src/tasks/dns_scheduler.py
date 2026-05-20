"""ARQ cron-задача ``dns_scheduler_tick``.

Параллельно ``ssl_scheduler_tick`` для DNS-мониторинга
(Этап 14, ADR 032). Каждый тик:

1. **Bootstrap**: для всех ``user_domains`` с ``track_dns=true``,
   у которых ещё нет записи в ``dns_cache`` — кладём заглушку
   с ``next_check_at=now()``. Идемпотентно через
   ``ON CONFLICT DO NOTHING``. Без этого шага существующие до
   v0.8.0 домены никогда бы не попали в DNS-мониторинг.

2. **Выборка**: ``DNSCacheRepository.get_due_for_check`` фильтрует
   те же домены по подписчикам с ``track_dns=true AND is_muted=false``.

3. **Enqueue**: ``check_dns`` сам защищается флагом
   ``dns_check_in_progress:<domain>`` в Redis, поэтому задвоение
   между тиками безопасно.
"""

from __future__ import annotations

import logging
from typing import Any, cast

from arq import ArqRedis
from sqlalchemy import text
from sqlalchemy.engine import CursorResult

from src.db.repositories import DNSCacheRepository
from src.db.session import get_session

logger = logging.getLogger(__name__)

BATCH_LIMIT = 500


# language=PostgreSQL
_BOOTSTRAP_SQL = """
INSERT INTO dns_cache (domain, next_check_at)
SELECT DISTINCT ud.domain, now()
FROM user_domains ud
WHERE ud.track_dns = true
  AND NOT EXISTS (SELECT 1 FROM dns_cache dc WHERE dc.domain = ud.domain)
ON CONFLICT (domain) DO NOTHING
"""


async def dns_scheduler_tick(ctx: dict[str, Any]) -> None:
    """Раздать due-домены в очередь ``check_dns`` (с bootstrap-шагом)."""
    arq_redis: ArqRedis = ctx["redis"]

    async with get_session() as session:
        result = cast(CursorResult[Any], await session.execute(text(_BOOTSTRAP_SQL)))
        bootstrapped = result.rowcount or 0
        if bootstrapped:
            logger.info("dns_scheduler_tick: bootstrapped %d new domain(s)", bootstrapped)
        cache_repo = DNSCacheRepository(session)
        due = await cache_repo.get_due_for_check(limit=BATCH_LIMIT)

    if not due:
        logger.debug("dns_scheduler_tick: nothing due")
        return

    for entry in due:
        await arq_redis.enqueue_job("check_dns", entry.domain)
    logger.info("dns_scheduler_tick: queued %d domain(s)", len(due))


__all__ = ["dns_scheduler_tick"]
