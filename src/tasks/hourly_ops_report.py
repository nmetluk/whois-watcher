"""ARQ cron-задача ``hourly_ops_report``: ежечасный технический отчёт в админ-канал (ADR 042, TASK-0059).

Собирает за последний час:
- активные пользователи (last_active_at)
- новые домены (user_domains.added_at)
- lookups (прокси: whois_cache.fetched_at)
- ошибки/алерты из system_events + audit_log
+ статус последнего бекапа из Redis `ops:last_backup` (от TASK-0058)

Формат: «📟 Ops (hour): users N · lookups M · +домены K · ошибки E | 💾 бекап ✅ <size>/❌ <error>»

Отправка через AlertService.send_ops (без дедупа, т.к. меняется ежечасно).
Если admin_channel_id не задан — тихо пропускаем (как в daily).
"""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import text

from src.config.limits import get_limits
from src.config.settings import get_settings
from src.db.session import get_session
from src.services.alerts import AlertService

logger = logging.getLogger(__name__)


# language=PostgreSQL
_ACTIVE_USERS_1H_SQL = (
    "SELECT count(*) FROM users WHERE last_active_at >= now() - interval '1 hour'"
)
_NEW_DOMAINS_1H_SQL = (
    "SELECT count(*) FROM user_domains WHERE added_at >= now() - interval '1 hour'"
)
_LOOKUPS_1H_SQL = "SELECT count(*) FROM whois_cache WHERE fetched_at >= now() - interval '1 hour'"
_SYS_ERRORS_1H_SQL = """
SELECT count(*) FROM system_events
WHERE created_at >= now() - interval '1 hour'
  AND severity IN ('error', 'critical')
"""
_AUDIT_ERRORS_1H_SQL = """
SELECT count(*) FROM audit_log
WHERE created_at >= now() - interval '1 hour'
  AND level IN ('error', 'critical')
"""


async def hourly_ops_report(ctx: dict[str, Any]) -> None:
    """Cron (minute=0): собрать почасовую статистику + статус бекапа, отправить в админ-канал."""
    settings = get_settings()
    if settings.admin_channel_id is None:
        logger.debug("hourly_ops_report: admin_channel_id is not set; skip")
        return

    bot = ctx.get("bot")
    redis = ctx.get("sync_redis") or ctx.get("redis")
    if bot is None or redis is None:
        logger.warning("hourly_ops_report: ctx is missing bot/redis; skip")
        return

    stats = await _collect_hourly_stats()

    # Читаем статус бекапа (записан backup_postgres из TASK-0058)
    backup: dict[str, Any] = {"ok": False, "size": 0, "error": "no data"}
    if redis:
        try:
            raw = await redis.get("ops:last_backup")
            if raw:
                if isinstance(raw, bytes | bytearray):
                    raw = raw.decode("utf-8", errors="ignore")
                backup = json.loads(raw)
        except Exception:
            logger.warning("hourly_ops_report: failed to read ops:last_backup from redis")

    if backup.get("ok"):
        bstat = f"✅ {backup.get('size', 0)}"
    else:
        err = backup.get("error") or "no data"
        bstat = f"❌ {str(err)[:60]}"

    body = (
        f"users {stats['active_users']} · lookups {stats['lookups']} · "
        f"+домены {stats['new_domains']} · ошибки {stats['errors']} | "
        f"💾 бекап {bstat}"
    )

    alerts = AlertService(bot=bot, redis=redis, settings=settings, limits=get_limits())
    await alerts.send_ops(body)


async def _collect_hourly_stats() -> dict[str, Any]:
    """Один поход в БД для всех счётчиков за последний час."""
    async with get_session() as session:
        active = (await session.execute(text(_ACTIVE_USERS_1H_SQL))).scalar_one() or 0
        new_doms = (await session.execute(text(_NEW_DOMAINS_1H_SQL))).scalar_one() or 0
        lookups = (await session.execute(text(_LOOKUPS_1H_SQL))).scalar_one() or 0
        sys_err = (await session.execute(text(_SYS_ERRORS_1H_SQL))).scalar_one() or 0

        # audit_log может отсутствовать до мержа TASK-0057; защищаемся
        aud_err = 0
        try:
            aud_err = (await session.execute(text(_AUDIT_ERRORS_1H_SQL))).scalar_one() or 0
        except Exception:  # - таблица может быть ещё не создана
            logger.debug("hourly_ops_report: audit_log not available yet (pre TASK-0057)")

    total_err = int(sys_err) + int(aud_err)
    return {
        "active_users": int(active),
        "new_domains": int(new_doms),
        "lookups": int(lookups),
        "errors": total_err,
    }


__all__ = ["hourly_ops_report"]
