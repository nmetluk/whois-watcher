"""Конфигурация ARQ-воркера.

Стартует через ``src.worker``. Регистрирует все фоновые задачи, поднимает
зависимости (Bot, БД-движок) и кладёт их в ``ctx``, чтобы задачи могли
ходить в БД и слать сообщения пользователям.

Cron:

- ``scheduler_tick`` — каждые 5 минут (см. ``docs/architecture.md``).
  Берёт из ``whois_cache`` все ``next_check_at <= now()`` и ставит на каждый
  задачу ``check_domain``.

Концурентность ограничена ``Limits.max_concurrent_whois``: ARQ запустит не
больше столько джоб параллельно.
"""

from __future__ import annotations

import logging
from contextlib import suppress
from typing import Any

from arq.connections import RedisSettings
from arq.cron import cron
from arq.typing import WorkerSettingsBase
from redis.asyncio import Redis as AsyncRedis

from src.bot.app import create_bot
from src.config.limits import Limits, get_limits
from src.config.settings import Settings, get_settings
from src.services.audit import audit

logger = logging.getLogger(__name__)


def get_redis_settings() -> RedisSettings:
    """Строит ``RedisSettings`` ARQ из настроек проекта."""
    settings = get_settings()
    return RedisSettings(
        host=settings.redis_host,
        port=settings.redis_port,
        database=settings.redis_db,
    )


async def _on_startup(ctx: dict[str, Any]) -> None:
    """Готовит ``ctx`` для всех задач: Bot, Limits, Settings, sync-Redis."""
    settings = get_settings()
    limits = get_limits()
    bot = create_bot(settings.bot_token.get_secret_value())
    # Отдельный «обычный» Redis-клиент для check_in_progress / pending_add
    # флагов: ``ctx['redis']`` от ARQ — это уже ArqRedis, но он подходит и для
    # обычных операций (set/get/sadd).
    sync_redis: AsyncRedis[str] = AsyncRedis.from_url(settings.redis_url, decode_responses=True)
    ctx["bot"] = bot
    ctx["settings"] = settings
    ctx["limits"] = limits
    ctx["sync_redis"] = sync_redis
    logger.info("ARQ worker started")

    # Info-алерт в админ-канал — даёт сигнал, что воркер реально стартовал.
    try:
        from src.services.alerts import AlertService

        alerts = AlertService(bot=bot, redis=sync_redis, settings=settings, limits=limits)
        await alerts.send_info("worker started", f"environment={settings.environment}")
    except Exception:
        logger.exception("Failed to send worker-start alert")
        with suppress(Exception):  # pragma: no cover
            await audit(
                level="critical",
                category="startup",
                message="worker startup alert failed",
                actor="system",
                context={"environment": getattr(settings, "environment", "unknown")},
            )


async def _on_shutdown(ctx: dict[str, Any]) -> None:
    """Закрывает то, что открыли в startup."""
    bot = ctx.get("bot")
    sync_redis = ctx.get("sync_redis")
    settings = ctx.get("settings")
    limits = ctx.get("limits")
    if bot is not None and sync_redis is not None and settings is not None and limits is not None:
        try:
            from src.services.alerts import AlertService

            alerts = AlertService(bot=bot, redis=sync_redis, settings=settings, limits=limits)
            await alerts.send_info("worker stopped", f"environment={settings.environment}")
        except Exception:
            logger.exception("Failed to send worker-stop alert")

    if bot is not None:
        await bot.session.close()
    if sync_redis is not None:
        await sync_redis.close()
    # ``dispose_engine`` зовём только если кто-то реально дёрнул БД —
    # ``_get_engine`` ленивый, и если задачи в этом процессе не запускались,
    # движок не создавался. ``close`` идемпотентен.
    from src.db.session import dispose_engine

    await dispose_engine()
    logger.info("ARQ worker stopped")


def _build_functions() -> list[Any]:
    """Импорты задач отложены — это разбивает цикл tasks → arq_config → tasks."""
    from src.tasks.backup_postgres import backup_postgres
    from src.tasks.check_dns import check_dns
    from src.tasks.check_dns_report import check_dns_report
    from src.tasks.check_domain import check_domain
    from src.tasks.check_email_deep import check_email_deep
    from src.tasks.check_email_intel import check_email_intel
    from src.tasks.check_ssl import check_ssl
    from src.tasks.check_subdomains import check_subdomains
    from src.tasks.cleanup import (
        cleanup_old_audit_log,
        cleanup_old_events,
        cleanup_orphan_cache,
    )
    from src.tasks.daily_graph_report import daily_graph_report
    from src.tasks.daily_stats import send_daily_summary
    from src.tasks.dns_scheduler import dns_scheduler_tick
    from src.tasks.email_intel_scheduler import email_intel_scheduler_tick
    from src.tasks.expiry_scheduler import expiry_notification_scheduler
    from src.tasks.hourly_ops_report import hourly_ops_report
    from src.tasks.notify_changes import send_change_notice
    from src.tasks.notify_dns_changes import send_dns_change_notice
    from src.tasks.notify_email_changes import send_email_change_notice
    from src.tasks.notify_problem import send_problem_notice
    from src.tasks.notify_ssl_changes import send_ssl_change_notice
    from src.tasks.notify_subdomain_changes import notify_subdomain_changes
    from src.tasks.notify_wishlist import send_wishlist_available_notice
    from src.tasks.proxy_health import proxy_health_check
    from src.tasks.rir_health import rir_health_check
    from src.tasks.scheduler import scheduler_tick
    from src.tasks.send_reminders import send_expiry_reminder
    from src.tasks.send_ssl_reminder import send_ssl_expiry_reminder
    from src.tasks.ssl_reminders_scheduler import ssl_reminders_scheduler
    from src.tasks.ssl_scheduler import ssl_scheduler_tick

    return [
        backup_postgres,
        check_domain,
        check_email_deep,
        scheduler_tick,
        send_change_notice,
        send_problem_notice,
        send_expiry_reminder,
        expiry_notification_scheduler,
        send_daily_summary,
        cleanup_orphan_cache,
        cleanup_old_events,
        cleanup_old_audit_log,
        send_wishlist_available_notice,
        daily_graph_report,
        proxy_health_check,
        hourly_ops_report,
        # RIR/ASN lookup (Этап 13, ADR 031)
        rir_health_check,
        # SSL (Этап 12, ADR 030)
        check_ssl,
        ssl_scheduler_tick,
        ssl_reminders_scheduler,
        send_ssl_expiry_reminder,
        send_ssl_change_notice,
        # DNS monitoring (Этап 14, ADR 032)
        check_dns,
        dns_scheduler_tick,
        send_dns_change_notice,
        # DNS report — on-demand расширенный анализ (ADR 044)
        check_dns_report,
        # Email-intel (Этап 17, ADR 036)
        check_email_intel,
        email_intel_scheduler_tick,
        send_email_change_notice,
        # Subdomain enumeration (Этап 18, ADR 037)
        check_subdomains,
        # Subdomain monitoring (TASK-0029, ADR 038)
        notify_subdomain_changes,
    ]


def _build_cron_jobs() -> list[Any]:
    from src.tasks.backup_postgres import backup_postgres
    from src.tasks.cleanup import (
        cleanup_old_audit_log,
        cleanup_old_events,
        cleanup_orphan_cache,
    )
    from src.tasks.daily_graph_report import daily_graph_report
    from src.tasks.daily_stats import send_daily_summary
    from src.tasks.dns_scheduler import dns_scheduler_tick
    from src.tasks.email_intel_scheduler import email_intel_scheduler_tick
    from src.tasks.expiry_scheduler import expiry_notification_scheduler
    from src.tasks.hourly_ops_report import hourly_ops_report
    from src.tasks.proxy_health import proxy_health_check
    from src.tasks.rir_health import rir_health_check
    from src.tasks.scheduler import scheduler_tick
    from src.tasks.ssl_reminders_scheduler import ssl_reminders_scheduler
    from src.tasks.ssl_scheduler import ssl_scheduler_tick
    from src.tasks.subdomain_scheduler import subdomain_scheduler_tick

    return [
        cron(
            scheduler_tick,
            name="scheduler_tick",
            minute={0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55},
            run_at_startup=True,
        ),
        # ADR 028: каждые 15 мин пингуем /healthz WHOIS proxy.
        cron(
            proxy_health_check,
            name="proxy_health_check",
            minute={0, 15, 30, 45},
            run_at_startup=True,
        ),
        # ADR 031: каждые 30 мин пингуем rir2localdb + проверяем свежесть
        # данных (последний sync_run не старше 26h, status == "success").
        cron(
            rir_health_check,
            name="rir_health_check",
            minute={0, 30},
            run_at_startup=False,
        ),
        cron(
            expiry_notification_scheduler,
            name="expiry_notification_scheduler",
            minute={0},
        ),
        # ADR 030: SSL scheduler работает на той же частоте что и WHOIS
        # — каждые 5 минут раздаёт due-домены в очередь check_ssl.
        cron(
            ssl_scheduler_tick,
            name="ssl_scheduler_tick",
            minute={0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55},
            run_at_startup=True,
        ),
        # ADR 032: DNS scheduler — каждые 5 минут, как WHOIS и SSL.
        cron(
            dns_scheduler_tick,
            name="dns_scheduler_tick",
            minute={0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55},
            run_at_startup=True,
        ),
        # ADR 036: Email-intel scheduler — каждые 5 минут.
        cron(
            email_intel_scheduler_tick,
            name="email_intel_scheduler_tick",
            minute={0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55},
            run_at_startup=True,
        ),
        # ADR 038: Subdomain scheduler — каждые 5 минут, как WHOIS/SSL/DNS.
        cron(
            subdomain_scheduler_tick,
            name="subdomain_scheduler_tick",
            minute={0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55},
            run_at_startup=True,
        ),
        # Напоминания об истечении SSL — раз в час, как и для WHOIS.
        cron(
            ssl_reminders_scheduler,
            name="ssl_reminders_scheduler",
            minute={0},
        ),
        # ADR 042: ежечасный бекап Postgres (в scheduler-контейнере).
        cron(
            backup_postgres,
            name="backup_postgres",
            minute={0},
        ),
        # ADR 042, TASK-0059: ежечасный ops-отчёт (статистика + статус бекапа).
        cron(
            hourly_ops_report,
            name="hourly_ops_report",
            minute={0},
        ),
        # ADR 042, TASK-0060: дневные графики в 21:00 МСК (18:00 UTC). 06:00 текстовая сводка остаётся.
        cron(
            daily_graph_report,
            name="daily_graph_report",
            hour={18},
            minute={0},
        ),
        # Раз в сутки в 03:00 UTC = 06:00 по Москве — сразу после ночного окна.
        cron(
            send_daily_summary,
            name="send_daily_summary",
            hour={3},
            minute={0},
        ),
        # Раз в сутки чистим сиротские записи кэша и старые system_events.
        cron(
            cleanup_orphan_cache,
            name="cleanup_orphan_cache",
            hour={4},
            minute={0},
        ),
        cron(
            cleanup_old_events,
            name="cleanup_old_events",
            hour={4},
            minute={10},
        ),
        # TASK-0061: чистим audit_log по retention (90 дней по умолчанию).
        cron(
            cleanup_old_audit_log,
            name="cleanup_old_audit_log",
            hour={4},
            minute={20},
        ),
    ]


class WorkerSettings(WorkerSettingsBase):
    """``WorkerSettings`` для ``arq.worker.run_worker``.

    Используется как класс (а не инстанс) — ARQ читает атрибуты класса.
    Наследуем ``WorkerSettingsBase`` — это Protocol, дающий mypy уверенность,
    что класс пригоден для ``run_worker``.
    """

    redis_settings: RedisSettings = get_redis_settings()
    functions: list[Any] = _build_functions()
    cron_jobs: list[Any] = _build_cron_jobs()
    on_startup = staticmethod(_on_startup)
    on_shutdown = staticmethod(_on_shutdown)
    # ``max_jobs`` совпадает с глобальным лимитом конкурентных WHOIS —
    # не имеет смысла иметь больше джоб в полёте, чем мы готовы выпускать
    # WHOIS-запросов наружу.
    _limits_snapshot: Limits = get_limits()
    max_jobs: int = _limits_snapshot.max_concurrent_whois
    job_timeout: int = 60
    keep_result: int = 0


def _build_settings_for_test() -> Settings:
    """Хелпер для тестов: даёт уверенность, что settings/limits резолвятся."""
    return get_settings()
