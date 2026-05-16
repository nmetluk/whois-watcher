"""ARQ cron-задача ``send_daily_summary``: ежедневная сводка в админ-канал.

Раз в сутки собирает агрегаты за прошедшие сутки и шлёт их в админ-канал
через ``AlertService.send_daily_summary``.

Что считаем (всё одним проходом через SQL, без вытягивания строк в Python):

- новые пользователи
- активные пользователи (``last_active_at >= 1 day ago``)
- сколько доменов добавлено (``user_domains.added_at >= 1 day ago``)
- сколько уведомлений отправлено, разбито по ``notification_type``
- топ ошибок из ``system_events`` за сутки
- сколько ``whois_cache.next_check_at <= now()`` (хвост очереди проверок)
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import text

from src.config.limits import get_limits
from src.config.settings import get_settings
from src.db.session import get_session
from src.services.alerts import AlertService

logger = logging.getLogger(__name__)


# language=PostgreSQL
_NEW_USERS_SQL = "SELECT count(*) FROM users WHERE created_at >= now() - interval '1 day'"
_ACTIVE_USERS_SQL = "SELECT count(*) FROM users WHERE last_active_at >= now() - interval '1 day'"
_DOMAINS_ADDED_SQL = "SELECT count(*) FROM user_domains WHERE added_at >= now() - interval '1 day'"
_NOTIFICATIONS_SQL = """
SELECT notification_type, count(*)
FROM sent_notifications
WHERE sent_at >= now() - interval '1 day'
GROUP BY notification_type
ORDER BY count(*) DESC
"""
_TOP_ERRORS_SQL = """
SELECT event_type, count(*)
FROM system_events
WHERE created_at >= now() - interval '1 day'
  AND severity IN ('error', 'critical')
GROUP BY event_type
ORDER BY count(*) DESC
LIMIT 5
"""
_DUE_CHECKS_SQL = (
    "SELECT count(*) FROM whois_cache " "WHERE next_check_at IS NOT NULL AND next_check_at <= now()"
)


async def send_daily_summary(ctx: dict[str, Any]) -> None:
    """Cron: собрать дневную статистику и отправить в админ-канал."""
    settings = get_settings()
    if settings.admin_channel_id is None:
        logger.debug("send_daily_summary: admin_channel_id is not set; skip")
        return

    stats = await _collect_stats()

    bot = ctx.get("bot")
    redis = ctx.get("sync_redis") or ctx.get("redis")
    if bot is None or redis is None:
        logger.warning("send_daily_summary: ctx is missing bot/redis; skip")
        return

    alerts = AlertService(bot=bot, redis=redis, settings=settings, limits=get_limits())
    await alerts.send_daily_summary(stats)


async def _collect_stats() -> dict[str, Any]:
    """Один поход в БД на всю сводку."""
    async with get_session() as session:
        new_users = (await session.execute(text(_NEW_USERS_SQL))).scalar_one()
        active_users = (await session.execute(text(_ACTIVE_USERS_SQL))).scalar_one()
        domains_added = (await session.execute(text(_DOMAINS_ADDED_SQL))).scalar_one()

        notifications_rows = (await session.execute(text(_NOTIFICATIONS_SQL))).all()
        errors_rows = (await session.execute(text(_TOP_ERRORS_SQL))).all()
        due_checks = (await session.execute(text(_DUE_CHECKS_SQL))).scalar_one()

    notifications: dict[str, int] = {row[0]: int(row[1]) for row in notifications_rows}
    top_errors: list[str] = [f"{row[0]}: {row[1]}" for row in errors_rows]

    return {
        "new_users": int(new_users or 0),
        "active_users": int(active_users or 0),
        "domains_added": int(domains_added or 0),
        "notifications": notifications,
        "top_errors": top_errors or ["(none)"],
        "due_checks": int(due_checks or 0),
    }


__all__ = ["send_daily_summary"]
