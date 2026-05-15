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
from typing import Any

from arq.connections import RedisSettings
from arq.cron import cron
from arq.typing import WorkerSettingsBase
from redis.asyncio import Redis as AsyncRedis

from src.bot.app import create_bot
from src.config.limits import Limits, get_limits
from src.config.settings import Settings, get_settings

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


async def _on_shutdown(ctx: dict[str, Any]) -> None:
    """Закрывает то, что открыли в startup."""
    bot = ctx.get("bot")
    if bot is not None:
        await bot.session.close()
    sync_redis = ctx.get("sync_redis")
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
    from src.tasks.check_domain import check_domain
    from src.tasks.notify_stubs import send_change_notice, send_problem_notice
    from src.tasks.scheduler import scheduler_tick

    return [check_domain, scheduler_tick, send_change_notice, send_problem_notice]


def _build_cron_jobs() -> list[Any]:
    from src.tasks.scheduler import scheduler_tick

    return [
        cron(
            scheduler_tick,
            name="scheduler_tick",
            minute={0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55},
            run_at_startup=True,
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
