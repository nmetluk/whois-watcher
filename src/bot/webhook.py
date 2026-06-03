"""Aiohttp-приложение с webhook-эндпойнтом и healthcheck.

Используем ``aiogram.webhook.aiohttp_server`` — это «штатная» интеграция
aiogram 3.x. Преимущества перед самописным эндпойнтом:

- проверка ``X-Telegram-Bot-Api-Secret-Token`` встроена
- корректная обработка ошибок aiogram (валидация апдейтов и т. п.)
- единый формат ответов

Lifecycle:

- ``on_startup``: ``bot.set_webhook`` (drop_pending=True) + установка команд
  бота + создание ArqRedis-пула для постановки задач из хэндлеров
- ``on_shutdown``: ``bot.delete_webhook`` + закрытие сессий БД/Redis/ArqRedis
"""

from __future__ import annotations

import logging
from contextlib import suppress

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommandScopeDefault
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from arq import create_pool
from redis.asyncio import Redis

from src.bot.commands import COMMANDS_EN, COMMANDS_RU
from src.bot.webapp.api import setup_webapp_on_main
from src.config.limits import get_limits
from src.config.settings import Settings
from src.db.session import dispose_engine
from src.services.alerts import AlertService
from src.services.audit import audit
from src.tasks.arq_config import get_redis_settings

logger = logging.getLogger(__name__)


async def _health(request: web.Request) -> web.Response:
    """``GET /health`` — readiness/liveness probe."""
    del request
    return web.json_response({"status": "ok"})


def create_app(
    *,
    bot: Bot,
    dp: Dispatcher,
    settings: Settings,
    redis: Redis[str],
) -> web.Application:
    """Создаёт aiohttp-приложение со всеми эндпойнтами и lifecycle-хуками."""
    app = web.Application()
    app.router.add_get("/health", _health)

    # WebApp JSON API (ADR 043 / TASK-0066/70). Mounted at /api/webapp/*
    # Auth (initData) + CORS inside the subapp. Read + Write.
    setup_webapp_on_main(app, settings=settings)

    SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        secret_token=settings.webhook_secret.get_secret_value(),
    ).register(app, path=settings.webhook_path)

    setup_application(app, dp, bot=bot)

    async def _on_startup(_app: web.Application) -> None:
        # ArqRedis-пул создаётся здесь (нужен event loop). Кладём в DI-контейнер
        # Dispatcher'а — хэндлерам доступен как параметр ``arq_redis``.
        arq_redis = await create_pool(get_redis_settings())
        dp["arq_redis"] = arq_redis

        webhook_url = settings.webhook_url
        try:
            await bot.set_webhook(
                url=webhook_url,
                secret_token=settings.webhook_secret.get_secret_value(),
                drop_pending_updates=True,
            )
        except Exception as exc:
            await _try_send_critical(bot, redis, settings, "webhook setup failed", repr(exc))
            raise
        await bot.set_my_commands(
            commands=list(COMMANDS_RU),
            scope=BotCommandScopeDefault(),
            language_code="ru",
        )
        await bot.set_my_commands(
            commands=list(COMMANDS_EN),
            scope=BotCommandScopeDefault(),
            language_code="en",
        )
        logger.info("Webhook set: %s", webhook_url)

        await _try_send_info(
            bot, redis, settings, "bot started", f"environment={settings.environment}"
        )

    async def _on_shutdown(_app: web.Application) -> None:
        await _try_send_info(
            bot, redis, settings, "bot stopping", f"environment={settings.environment}"
        )
        try:
            await bot.delete_webhook(drop_pending_updates=False)
        except Exception:
            logger.exception("Failed to delete webhook on shutdown")
        arq_redis = dp.get("arq_redis")
        if arq_redis is not None:
            await arq_redis.close()
        await redis.close()
        await dispose_engine()
        logger.info("Bot stopped gracefully")

    app.on_startup.append(_on_startup)
    app.on_shutdown.append(_on_shutdown)
    return app


async def _try_send_info(
    bot: Bot, redis: Redis[str], settings: Settings, title: str, details: str
) -> None:
    """Шлёт info-алерт, проглатывая любые ошибки (startup не должен падать)."""
    try:
        alerts = AlertService(bot=bot, redis=redis, settings=settings, limits=get_limits())
        await alerts.send_info(title, details)
    except Exception:
        logger.exception("Failed to send info alert: %s", title)


async def _try_send_critical(
    bot: Bot, redis: Redis[str], settings: Settings, title: str, details: str
) -> None:
    """Шлёт critical-алерт без проброса ошибок отправки."""
    try:
        alerts = AlertService(bot=bot, redis=redis, settings=settings, limits=get_limits())
        await alerts.send_critical(title, details)
    except Exception:
        logger.exception("Failed to send critical alert: %s", title)
        with suppress(Exception):  # pragma: no cover
            await audit(
                level="critical",
                category="webhook",
                message="failed to send critical alert",
                actor="system",
                context={"title": title},
            )
