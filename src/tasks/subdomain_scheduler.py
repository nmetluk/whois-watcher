"""ARQ cron-задача ``subdomain_scheduler_tick`` (TASK-0028, ADR 038).

Параллельно ``ssl_scheduler_tick`` для SSL-мониторинга, но по таблице
``subdomain_enum_cache`` и registrable-доменам. Каждый тик:

1. **Bootstrap**: для всех ``user_domains`` с ``track_subdomains=true``,
   у которых ещё нет записи в ``subdomain_enum_cache`` — кладём заглушку
   с ``next_check_at=now()`` по registrable_domain. Идемпотентно через
   ``ON CONFLICT DO NOTHING``.
2. **Выборка**: ``SubdomainEnumCacheRepository.get_due_for_check`` фильтрует
   registrable-домены по подписчикам с ``track_subdomains=true AND is_muted=false``.
3. **Enqueue**: ``check_subdomains`` сам защищается флагом
   ``subdomain_check_in_progress:<registrable>``, поэтому задвоение между
   тиками безопасно.
"""

from __future__ import annotations

import logging
from typing import Any, cast

from arq import ArqRedis
from sqlalchemy import text
from sqlalchemy.engine import CursorResult

from src.db.repositories import SubdomainEnumCacheRepository
from src.db.session import get_session

logger = logging.getLogger(__name__)

BATCH_LIMIT = 500


# language=PostgreSQL
_BOOTSTRAP_SQL = """
INSERT INTO subdomain_enum_cache (registrable_domain, next_check_at)
SELECT DISTINCT ud.registrable_domain, now()
FROM user_domains ud
WHERE ud.track_subdomains = true
  AND NOT EXISTS (
    SELECT 1 FROM subdomain_enum_cache sec
    WHERE sec.registrable_domain = ud.registrable_domain
  )
ON CONFLICT (registrable_domain) DO NOTHING
"""


async def subdomain_scheduler_tick(ctx: dict[str, Any]) -> None:
    """Раздать due-registrable-домены в очередь ``check_subdomains`` (с bootstrap-шагом)."""
    arq_redis: ArqRedis = ctx["redis"]

    async with get_session() as session:
        result = cast(CursorResult[Any], await session.execute(text(_BOOTSTRAP_SQL)))
        bootstrapped = result.rowcount or 0
        if bootstrapped:
            logger.info(
                "subdomain_scheduler_tick: bootstrapped %d registrable domain(s)", bootstrapped
            )
        cache_repo = SubdomainEnumCacheRepository(session)
        due = await cache_repo.get_due_for_check(limit=BATCH_LIMIT)

    if not due:
        logger.debug("subdomain_scheduler_tick: nothing due")
        return

    for entry in due:
        await arq_redis.enqueue_job("check_subdomains", entry.registrable_domain)
    logger.info("subdomain_scheduler_tick: queued %d registrable domain(s)", len(due))


__all__ = ["subdomain_scheduler_tick"]
