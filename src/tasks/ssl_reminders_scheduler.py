"""ARQ cron-задача ``ssl_reminders_scheduler``: ежечасный планировщик
напоминаний о скором истечении SSL-сертификата.

Параллельно ``expiry_notification_scheduler`` для WHOIS, но смотрит в
``ssl_cache.not_after`` и использует ``notify_ssl_days_override`` /
``users.notify_ssl_days_before``. Дедупликация — через
``sent_notifications`` с типом ``ssl_expiry``.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import text

from src.db.session import get_session

logger = logging.getLogger(__name__)


# language=PostgreSQL
_DUE_SSL_REMINDERS_SQL = """
WITH active_users AS (
    SELECT id,
           notify_ssl_days_before,
           timezone
    FROM users
    WHERE is_blocked = false
      AND EXTRACT(HOUR FROM (now() AT TIME ZONE timezone))::int = notify_at_hour
)
SELECT ud.user_id    AS user_id,
       ud.domain     AS domain,
       day_before    AS days_before,
       sc.not_after  AS not_after
FROM user_domains ud
JOIN active_users u ON u.id = ud.user_id
JOIN ssl_cache    sc ON sc.domain = ud.domain
CROSS JOIN unnest(
    COALESCE(ud.notify_ssl_days_override, u.notify_ssl_days_before)
) AS day_before
LEFT JOIN sent_notifications sn
       ON sn.user_id = ud.user_id
      AND sn.domain = ud.domain
      AND sn.notification_type = 'ssl_expiry'
      AND sn.days_before = day_before
      AND sn.expires_at = sc.not_after
WHERE ud.track_ssl = true
  AND ud.is_muted = false
  AND ud.notify_ssl_expiry = true
  AND sc.not_after IS NOT NULL
  AND sc.has_certificate = true
  AND ((sc.not_after AT TIME ZONE u.timezone)::date
       - (now() AT TIME ZONE u.timezone)::date) = day_before
  AND sn.id IS NULL
"""


async def ssl_reminders_scheduler(ctx: dict[str, Any]) -> None:
    """Cron: найти все due SSL-напоминания и поставить в очередь."""
    from arq import ArqRedis

    arq_redis: ArqRedis = ctx["redis"]

    async with get_session() as session:
        result = await session.execute(text(_DUE_SSL_REMINDERS_SQL))
        rows = result.all()

    if not rows:
        logger.debug("ssl_reminders_scheduler: no due reminders")
        return

    logger.info("ssl_reminders_scheduler: queuing %d reminders", len(rows))
    for row in rows:
        await arq_redis.enqueue_job(
            "send_ssl_expiry_reminder",
            int(row.user_id),
            str(row.domain),
            int(row.days_before),
        )


__all__ = ["ssl_reminders_scheduler"]
