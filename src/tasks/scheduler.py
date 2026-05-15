"""ARQ cron-задача: ``scheduler_tick``.

Раздаёт работу — сам не делает HTTP/whois-запросов. Каждые 5 минут:

1. Берёт из ``whois_cache`` записи с ``next_check_at <= now()``, до ``BATCH_LIMIT``
   штук, отсортированные по ``next_check_at ASC`` — самые «голодные» первыми.
2. Для каждой ставит задачу ``check_domain`` в очередь ARQ. Уникальность по
   домену гарантирует Redis-флаг ``check_in_progress:<domain>`` внутри
   ``check_domain`` (см. ``tasks/check_domain.py``).
3. Если доменов оказалось столько же, сколько ``BATCH_LIMIT`` — значит очередь
   проверок «отстаёт». Следующий тик через 5 минут добьёт остаток.

Не задача-распределитель страдает от «тонкого пайплайна»: воркеры ARQ потянут
``max_jobs`` параллельных проверок одновременно, лимит задаётся в
``arq_config.WorkerSettings``.
"""

from __future__ import annotations

import logging
from typing import Any

from arq import ArqRedis

from src.db.repositories import WhoisCacheRepository
from src.db.session import get_session

logger = logging.getLogger(__name__)

# Сколько доменов раздаём за один тик. 500 × 12 тиков/час = 6000/час потолок,
# на старте этого хватит. Поднимать при росте.
BATCH_LIMIT = 500


async def scheduler_tick(ctx: dict[str, Any]) -> None:
    """Раздать due-домены в очередь ``check_domain``."""
    arq_redis: ArqRedis = ctx["redis"]

    async with get_session() as session:
        cache_repo = WhoisCacheRepository(session)
        due = await cache_repo.get_due_for_check(limit=BATCH_LIMIT)

    if not due:
        logger.debug("scheduler_tick: nothing due")
        return

    for entry in due:
        await arq_redis.enqueue_job("check_domain", entry.domain)
    logger.info("scheduler_tick: queued %d domain(s)", len(due))


__all__ = ["scheduler_tick"]
