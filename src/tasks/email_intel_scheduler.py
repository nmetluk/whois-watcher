"""ARQ cron-задача ``email_intel_scheduler_tick``.

Параллельно ``ssl_scheduler_tick`` для SSL, но по таблице ``email_intel_cache``.
Каждый тик:

1. **Bootstrap**: для всех ``user_domains`` с ``track_email=true``, у которых
   ещё нет записи в ``email_intel_cache`` — кладём заглушку с ``next_check_at=now()``.
   Идемпотентно через ``ON CONFLICT DO NOTHING``.
2. **Выборка**: ``EmailIntelCacheRepository.get_due_for_check`` фильтрует те же
   домены по подписчикам с ``track_email=true AND is_muted=false``.
3. **Enqueue**: ``check_email_intel`` сам защищается флагом
   ``email_intel_check_in_progress:<domain>``, поэтому задвоение между тиками
   безопасно.
"""

from __future__ import annotations

import logging
from typing import Any, cast

from arq import ArqRedis
from sqlalchemy import text
from sqlalchemy.engine import CursorResult

from src.db.repositories import EmailIntelCacheRepository
from src.db.session import get_session

logger = logging.getLogger(__name__)

BATCH_LIMIT = 500


# language=PostgreSQL
_BOOTSTRAP_SQL = """
INSERT INTO email_intel_cache (domain, next_check_at)
SELECT DISTINCT ud.domain, now()
FROM user_domains ud
WHERE ud.track_email = true
  AND NOT EXISTS (SELECT 1 FROM email_intel_cache eic WHERE eic.domain = ud.domain)
ON CONFLICT (domain) DO NOTHING
"""


async def email_intel_scheduler_tick(ctx: dict[str, Any]) -> None:
    """Раздать due-домены в очередь ``check_email_intel`` (с bootstrap-шагом)."""
    arq_redis: ArqRedis = ctx["redis"]

    async with get_session() as session:
        result = cast(CursorResult[Any], await session.execute(text(_BOOTSTRAP_SQL)))
        bootstrapped = result.rowcount or 0
        if bootstrapped:
            logger.info("email_intel_scheduler_tick: bootstrapped %d new domain(s)", bootstrapped)
        cache_repo = EmailIntelCacheRepository(session)
        due = await cache_repo.get_due_for_check(limit=BATCH_LIMIT)

    if not due:
        logger.debug("email_intel_scheduler_tick: nothing due")
        return

    for entry in due:
        await arq_redis.enqueue_job("check_email_intel", entry.domain)
    logger.info("email_intel_scheduler_tick: queued %d domain(s)", len(due))


__all__ = ["email_intel_scheduler_tick"]
