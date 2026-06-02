"""ARQ-задачи чистки: сиротские записи WHOIS-кэша, старые ``system_events``.

Запускаются по cron из ``arq_config.py``. Не зависят от Bot/Telegram —
просто SQL.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import text

from src.config.settings import Settings, get_settings
from src.db.repositories import WhoisCacheRepository
from src.db.session import get_session

logger = logging.getLogger(__name__)


_DELETE_OLD_EVENTS_SQL = "DELETE FROM system_events WHERE created_at < now() - interval '30 days'"


async def cleanup_orphan_cache(ctx: dict[str, Any]) -> None:
    """Удаляет записи ``whois_cache``, на которые никто не подписан (ADR 020)."""
    del ctx
    async with get_session() as session:
        cache_repo = WhoisCacheRepository(session)
        removed = await cache_repo.delete_orphans()
    if removed:
        logger.info("cleanup_orphan_cache: removed %d whois_cache rows", removed)


async def cleanup_old_events(ctx: dict[str, Any]) -> None:
    """Удаляет ``system_events`` старше 30 дней."""
    del ctx
    async with get_session() as session:
        result = await session.execute(text(_DELETE_OLD_EVENTS_SQL))
    removed = getattr(result, "rowcount", 0) or 0
    if removed:
        logger.info("cleanup_old_events: removed %d rows", removed)


async def cleanup_old_audit_log(ctx: dict[str, Any]) -> None:
    """Удаляет записи ``audit_log`` старше N дней (N из settings.audit_retention_days, дефолт 90 по ADR 042)."""
    settings: Settings = ctx.get("settings") or get_settings()
    days = settings.audit_retention_days
    del ctx
    sql = f"DELETE FROM audit_log WHERE created_at < now() - interval '{days} days'"
    async with get_session() as session:
        result = await session.execute(text(sql))
    removed = getattr(result, "rowcount", 0) or 0
    if removed:
        logger.info("cleanup_old_audit_log: removed %d rows (retention=%d days)", removed, days)


__all__ = ["cleanup_old_events", "cleanup_orphan_cache", "cleanup_old_audit_log"]
