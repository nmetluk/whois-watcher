"""ARQ cron-задача ``daily_graph_report``: дневные графики в админ-канал (ADR 042, TASK-0060).

Cron в 21:00 МСК (18:00 UTC). Строит PNG с 4 графиками за ~14 дней:
lookups, active users, new domains, notifications.

Использует ``src.services.charts`` (headless Agg + to_thread).
Текстовая сводка в 06:00 остаётся в send_daily_summary (не трогаем).

Если admin_channel_id не задан — no-op.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import text

from src.config.settings import get_settings
from src.db.session import get_session
from src.services.charts import render_daily_charts

logger = logging.getLogger(__name__)


# language=PostgreSQL
_LOOKUPS_DAILY_SQL = """
SELECT date_trunc('day', fetched_at) AS day, count(*) AS cnt
FROM whois_cache
WHERE fetched_at >= now() - interval '14 days'
GROUP BY 1
ORDER BY 1
"""

_ACTIVE_DAILY_SQL = """
SELECT date_trunc('day', last_active_at) AS day, count(*) AS cnt
FROM users
WHERE last_active_at >= now() - interval '14 days'
GROUP BY 1
ORDER BY 1
"""

_NEW_DOMAINS_DAILY_SQL = """
SELECT date_trunc('day', added_at) AS day, count(*) AS cnt
FROM user_domains
WHERE added_at >= now() - interval '14 days'
GROUP BY 1
ORDER BY 1
"""

_NOTIFS_DAILY_SQL = """
SELECT date_trunc('day', sent_at) AS day, count(*) AS cnt
FROM sent_notifications
WHERE sent_at >= now() - interval '14 days'
GROUP BY 1
ORDER BY 1
"""


async def daily_graph_report(ctx: dict[str, Any]) -> None:
    """Cron: собрать данные за 14 дней, отрендерить графики, отправить PNG в админ-канал."""
    settings = get_settings()
    if settings.admin_channel_id is None:
        logger.debug("daily_graph_report: admin_channel_id is not set; skip")
        return

    bot = ctx.get("bot")
    if bot is None:
        logger.warning("daily_graph_report: bot missing in ctx; skip")
        return

    try:
        series = await _collect_daily_series()
        png_bytes = await render_daily_charts(series)

        from aiogram.types import BufferedInputFile

        photo = BufferedInputFile(png_bytes, filename="daily_graphs.png")
        await bot.send_photo(
            chat_id=settings.admin_channel_id,
            photo=photo,
            caption="📈 Daily graphs (last 14 days, 21:00 MSK)",
        )
        logger.info("daily_graph_report: sent graphs to admin channel")
    except Exception:
        logger.exception("daily_graph_report: failed to build/send graphs")


async def _collect_daily_series() -> dict[str, list[tuple[Any, int]]]:
    """Один поход в БД за всеми рядами."""
    async with get_session() as session:
        lookups = await _fetch_series(session, _LOOKUPS_DAILY_SQL)
        active = await _fetch_series(session, _ACTIVE_DAILY_SQL)
        new_doms = await _fetch_series(session, _NEW_DOMAINS_DAILY_SQL)
        notifs = await _fetch_series(session, _NOTIFS_DAILY_SQL)

    return {
        "lookups": lookups,
        "active": active,
        "new_domains": new_doms,
        "notifications": notifs,
    }


async def _fetch_series(session: Any, sql: str) -> list[tuple[Any, int]]:
    rows = (await session.execute(text(sql))).all()
    return [(row.day, int(row.cnt or 0)) for row in rows]


__all__ = ["daily_graph_report"]
