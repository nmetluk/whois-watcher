"""ARQ cron-задача ``expiry_notification_scheduler``: ежечасный планировщик.

Каждый час:

1. Один SQL: для активных пользователей (``is_blocked=false`` и сейчас
   локальный час совпадает с ``notify_at_hour``) находит все ``user_domains``,
   у которых ``notify_expiry=true``, есть ``whois_cache.expires_at``, и
   разница между ``expires_at`` (в TZ пользователя) и сегодняшней датой
   (в его же TZ) точно равна одному из ``notify_days``, и для которого
   ``sent_notifications`` ещё нет.
2. Для каждой выбранной строки ставит ``send_expiry_reminder``.

SQL делает всю работу одним проходом — не тащим домены в Python.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import text

from src.db.session import get_session

logger = logging.getLogger(__name__)


# language=PostgreSQL
_DUE_REMINDERS_SQL = """
WITH active_users AS (
    SELECT id, notify_days, timezone
    FROM users
    WHERE is_blocked = false
      AND EXTRACT(HOUR FROM (now() AT TIME ZONE timezone))::int = notify_at_hour
)
SELECT ud.user_id   AS user_id,
       ud.domain    AS domain,
       day_before   AS days_before,
       wc.expires_at AS expires_at
FROM user_domains ud
JOIN active_users u ON u.id = ud.user_id
JOIN whois_cache wc ON wc.domain = ud.domain
CROSS JOIN unnest(COALESCE(ud.notify_days, u.notify_days)) AS day_before
LEFT JOIN sent_notifications sn
       ON sn.user_id = ud.user_id
      AND sn.domain = ud.domain
      AND sn.notification_type = 'expiry'
      AND sn.days_before = day_before
      AND sn.expires_at = wc.expires_at
WHERE ud.notify_expiry = true
  AND wc.expires_at IS NOT NULL
  AND ((wc.expires_at AT TIME ZONE u.timezone)::date
       - (now() AT TIME ZONE u.timezone)::date) = day_before
  AND sn.id IS NULL
"""


async def expiry_notification_scheduler(ctx: dict[str, Any]) -> None:
    """Cron: пройти по активным пользователям и поставить нужные напоминания."""
    from arq import ArqRedis

    arq_redis: ArqRedis = ctx["redis"]

    async with get_session() as session:
        result = await session.execute(text(_DUE_REMINDERS_SQL))
        rows = result.all()

    if not rows:
        logger.debug("expiry_notification_scheduler: no due reminders")
        return

    logger.info("expiry_notification_scheduler: queuing %d reminders", len(rows))
    for row in rows:
        await arq_redis.enqueue_job(
            "send_expiry_reminder",
            int(row.user_id),
            str(row.domain),
            int(row.days_before),
        )


__all__ = ["expiry_notification_scheduler"]
