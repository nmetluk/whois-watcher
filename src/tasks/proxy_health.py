"""Cron-задача ``proxy_health_check`` (ADR 028, Этап 10).

Каждые 15 минут пинает ``/healthz`` WHOIS proxy gateway. Если прокси не
отвечает (``proxy_healthcheck()`` вернул False) — шлёт ``send_critical``
в админ-канал. ``AlertService`` дедуплицирует одинаковые алерты по
текстовому хешу + TTL (`Limits.alert_dedup_ttl_minutes`), так что
повторный fail в течение окна не задвоит сообщение.

Бот при этом продолжает работать через ``lookup_direct`` (RDAP +
WHOIS:43 fallback) — это просто потеря оптимизаций (24h-кеш, RU-relay).
"""

from __future__ import annotations

import logging
from typing import Any

from src.config.limits import get_limits
from src.config.settings import get_settings
from src.services.alerts import AlertService
from src.whois.proxy_client import proxy_healthcheck

logger = logging.getLogger(__name__)


_ALERT_TITLE = "WHOIS proxy is down"
_ALERT_DETAILS = (
    "Healthcheck to /healthz failed.\n"
    "Bot fell back to direct RDAP + WHOIS:43 lookup — functionality preserved "
    "but without 24h cache and RU-relay for .ru/.рф/.su."
)


async def proxy_health_check(ctx: dict[str, Any]) -> None:
    """ARQ-cron: пинг /healthz прокси, critical-alert если упал."""
    settings = get_settings()
    if not settings.whois_proxy_enabled:
        # Прокси выключен по политике — это не повод поднимать алерт.
        return

    healthy = await proxy_healthcheck()
    if healthy:
        logger.debug("proxy_health_check: ok")
        return

    bot = ctx.get("bot")
    redis = ctx.get("sync_redis") or ctx.get("redis")
    if bot is None or redis is None:
        logger.warning("proxy_health_check: ctx missing bot/redis; cannot alert")
        return

    alerter = AlertService(bot=bot, redis=redis, settings=settings, limits=get_limits())
    await alerter.send_critical(_ALERT_TITLE, _ALERT_DETAILS)


__all__ = ["proxy_health_check"]
