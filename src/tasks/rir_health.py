"""Cron-задача ``rir_health_check`` (Этап 13, ADR 031).

Каждые 30 минут проверяет:

1. ``/v1/healthz`` отвечает ``{"status":"ok"}``
2. ``/v1/status.latest_sync_run.started_at`` свежее ``MAX_SYNC_AGE``
3. ``latest_sync_run.status == "success"``

На любом из несоответствий — ``send_critical`` в админ-канал. Дедупликация
у ``AlertService`` идёт по ``(severity, title, details[:200])`` — отсюда
разные title-константы для каждого failure mode, чтобы каждый дедуплился
независимо.

Lookup'ы IP/ASN при недоступности сервиса возвращают
``RIRError(kind='unreachable')``, поэтому бот не падает — но качество
данных деградирует.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from src.config.limits import get_limits
from src.config.settings import get_settings
from src.rir_client import RIRUnreachable, get_status, healthcheck
from src.services.alerts import AlertService

logger = logging.getLogger(__name__)


# Данные считаем устаревшими если последний sync_run.started_at старше этого.
# rir2localdb syncs ежедневно в 03:00 UTC, 26h-буфер покрывает нормальный
# каденс плюс ~2h слака на randomized delays / медленные прогоны.
MAX_SYNC_AGE = timedelta(hours=26)


# Title-константы — стабильный hash для дедупликации в AlertService.
_TITLE_UNREACHABLE = "rir2localdb unreachable"
_DETAILS_UNREACHABLE = (
    "Healthz пинг провален.\n"
    "Lookup'ы IP/ASN будут возвращать RIRError(unreachable) до восстановления."
)

_TITLE_UNHEALTHY = "rir2localdb unhealthy"
_DETAILS_UNHEALTHY = (
    "Сервис отвечает, но /healthz статус не 'ok'.\n" "Возможна частичная деградация (БД, миграции)."
)

_TITLE_NO_SYNC = "rir2localdb has no sync runs yet"
_DETAILS_NO_SYNC = (
    "Сервис запущен, но ни одного sync_run в БД.\n"
    "Возможно ETL ещё не отрабатывал. Проверь rir2localdb-sync.service."
)

_TITLE_STALE = "rir2localdb data is stale"

_TITLE_SYNC_FAILED = "rir2localdb last sync_run failed"


async def rir_health_check(ctx: dict[str, Any]) -> None:
    """ARQ-cron: пинг + проверка свежести данных rir2localdb."""
    settings = get_settings()
    if not settings.rir2localdb_enabled:
        # Сервис выключен по политике — не повод поднимать алерт.
        return

    bot = ctx.get("bot")
    redis = ctx.get("sync_redis") or ctx.get("redis")
    if bot is None or redis is None:
        logger.warning("rir_health_check: ctx missing bot/redis; cannot alert")
        return
    alerter = AlertService(bot=bot, redis=redis, settings=settings, limits=get_limits())

    # Шаг 1 — liveness
    try:
        ok = await healthcheck()
    except RIRUnreachable as exc:
        logger.warning("rir_health.unreachable: %s", exc)
        await alerter.send_critical(_TITLE_UNREACHABLE, _DETAILS_UNREACHABLE)
        return

    if not ok:
        logger.warning("rir_health.unhealthy: healthz returned non-ok status")
        await alerter.send_critical(_TITLE_UNHEALTHY, _DETAILS_UNHEALTHY)
        return

    # Шаг 2 — freshness и status последнего sync_run
    try:
        status = await get_status()
    except RIRUnreachable as exc:
        # Healthz прошёл, status упал — странно, но не критично.
        logger.info("rir_health.status_unreachable: %s", exc)
        return

    if status.latest_sync_run is None:
        logger.warning("rir_health.no_sync_runs_yet")
        await alerter.send_critical(_TITLE_NO_SYNC, _DETAILS_NO_SYNC)
        return

    sync = status.latest_sync_run
    age = datetime.now(UTC) - sync.started_at
    if age > MAX_SYNC_AGE:
        age_hours = age.total_seconds() / 3600
        max_hours = MAX_SYNC_AGE.total_seconds() / 3600
        logger.warning(
            "rir_health.stale_data started_at=%s age_hours=%.1f status=%s",
            sync.started_at.isoformat(),
            age_hours,
            sync.status,
        )
        details = (
            f"Последний sync: {sync.started_at.isoformat()} "
            f"({age_hours:.1f}h назад, status={sync.status})\n"
            f"Максимум — {max_hours:.0f}h. "
            "Проверь rir2localdb-sync.service и .timer."
        )
        await alerter.send_critical(_TITLE_STALE, details)
        return

    if sync.status != "success":
        logger.warning(
            "rir_health.last_sync_not_success status=%s error=%s",
            sync.status,
            sync.error,
        )
        details = (
            f"Status: {sync.status}\n"
            f"Error: {sync.error or 'нет деталей'}\n"
            f"Started: {sync.started_at.isoformat()}"
        )
        await alerter.send_critical(_TITLE_SYNC_FAILED, details)
        return

    logger.debug(
        "rir_health.ok last_sync=%s age_hours=%.2f",
        sync.started_at.isoformat(),
        age.total_seconds() / 3600,
    )


__all__ = ["rir_health_check"]
