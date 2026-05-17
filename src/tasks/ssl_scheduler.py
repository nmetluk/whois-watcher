"""ARQ cron-задача ``ssl_scheduler_tick``.

Параллельно ``scheduler_tick`` для WHOIS, но по таблице ``ssl_cache``.
Каждый тик:

1. **Bootstrap**: для всех ``user_domains`` с ``track_ssl=true``, у которых
   ещё нет записи в ``ssl_cache`` — кладём заглушку с ``next_check_at=now()``.
   Идемпотентно через ``ON CONFLICT DO NOTHING``. Без этого шага существующие
   до Этапа 12 домены никогда бы не попали в SSL-мониторинг (а новые — только
   через первый ручной ``/whois``, см. handler).
2. **Выборка**: ``SSLCacheRepository.get_due_for_check`` фильтрует те же
   домены по подписчикам с ``track_ssl=true AND is_muted=false``.
3. **Enqueue**: ``check_ssl`` сам защищается флагом
   ``ssl_check_in_progress:<domain>``, поэтому задвоение между тиками
   безопасно.
"""

from __future__ import annotations

import logging
from typing import Any, cast

from arq import ArqRedis
from sqlalchemy import text
from sqlalchemy.engine import CursorResult

from src.db.repositories import SSLCacheRepository
from src.db.session import get_session

logger = logging.getLogger(__name__)

BATCH_LIMIT = 500


# language=PostgreSQL
_BOOTSTRAP_SQL = """
INSERT INTO ssl_cache (domain, next_check_at)
SELECT DISTINCT ud.domain, now()
FROM user_domains ud
WHERE ud.track_ssl = true
  AND NOT EXISTS (SELECT 1 FROM ssl_cache sc WHERE sc.domain = ud.domain)
ON CONFLICT (domain) DO NOTHING
"""


async def ssl_scheduler_tick(ctx: dict[str, Any]) -> None:
    """Раздать due-домены в очередь ``check_ssl`` (с bootstrap-шагом)."""
    arq_redis: ArqRedis = ctx["redis"]

    async with get_session() as session:
        result = cast(CursorResult[Any], await session.execute(text(_BOOTSTRAP_SQL)))
        bootstrapped = result.rowcount or 0
        if bootstrapped:
            logger.info("ssl_scheduler_tick: bootstrapped %d new domain(s)", bootstrapped)
        cache_repo = SSLCacheRepository(session)
        due = await cache_repo.get_due_for_check(limit=BATCH_LIMIT)

    if not due:
        logger.debug("ssl_scheduler_tick: nothing due")
        return

    for entry in due:
        await arq_redis.enqueue_job("check_ssl", entry.domain)
    logger.info("ssl_scheduler_tick: queued %d domain(s)", len(due))


__all__ = ["ssl_scheduler_tick"]
