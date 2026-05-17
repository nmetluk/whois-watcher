"""ARQ cron-задача ``ssl_scheduler_tick``.

Параллельно ``scheduler_tick`` для WHOIS, но по таблице ``ssl_cache``.
``SSLCacheRepository.get_due_for_check`` уже фильтрует домены, на которые
никто не подписан с ``track_ssl=true`` — поэтому здесь только enqueue.

``check_ssl`` сам защищается флагом ``ssl_check_in_progress:<domain>``,
так что задвоение между тиками безопасно.
"""

from __future__ import annotations

import logging
from typing import Any

from arq import ArqRedis

from src.db.repositories import SSLCacheRepository
from src.db.session import get_session

logger = logging.getLogger(__name__)

BATCH_LIMIT = 500


async def ssl_scheduler_tick(ctx: dict[str, Any]) -> None:
    """Раздать due-домены в очередь ``check_ssl``."""
    arq_redis: ArqRedis = ctx["redis"]

    async with get_session() as session:
        cache_repo = SSLCacheRepository(session)
        due = await cache_repo.get_due_for_check(limit=BATCH_LIMIT)

    if not due:
        logger.debug("ssl_scheduler_tick: nothing due")
        return

    for entry in due:
        await arq_redis.enqueue_job("check_ssl", entry.domain)
    logger.info("ssl_scheduler_tick: queued %d domain(s)", len(due))


__all__ = ["ssl_scheduler_tick"]
