"""Aiohttp-приложение с webhook-эндпойнтом и healthcheck.

Используем ``aiogram.webhook.aiohttp_server`` — это «штатная» интеграция
aiogram 3.x. Преимущества перед самописным эндпойнтом:

- проверка ``X-Telegram-Bot-Api-Secret-Token`` встроена
- корректная обработка ошибок aiogram (валидация апдейтов и т. п.)
- единый формат ответов

Lifecycle:

- ``on_startup``: ``bot.set_webhook`` (drop_pending=True) + установка
  команд бота в меню Telegram (RU/EN)
- ``on_shutdown``: ``bot.delete_webhook`` + закрытие сессий БД/Redis
"""

from __future__ import annotations

import logging

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommandScopeDefault
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from redis.asyncio import Redis

from src.bot.commands import COMMANDS_EN, COMMANDS_RU
from src.config.settings import Settings
from src.db.session import dispose_engine

logger = logging.getLogger(__name__)


async def _health(request: web.Request) -> web.Response:
    """``GET /health`` — readiness/liveness probe."""
    del request  # параметр обязателен сигнатурой aiohttp, но не используется
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

    # Регистрируем webhook-хендлер aiogram.
    SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        secret_token=settings.webhook_secret.get_secret_value(),
    ).register(app, path=settings.webhook_path)

    # ``setup_application`` подвешивает к aiohttp lifecycle-хуки aiogram:
    # graceful shutdown сессий Bot и т. п.
    setup_application(app, dp, bot=bot)

    async def _on_startup(_app: web.Application) -> None:
        webhook_url = settings.webhook_url
        await bot.set_webhook(
            url=webhook_url,
            secret_token=settings.webhook_secret.get_secret_value(),
            drop_pending_updates=True,
        )
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

    async def _on_shutdown(_app: web.Application) -> None:
        try:
            await bot.delete_webhook(drop_pending_updates=False)
        except Exception:
            logger.exception("Failed to delete webhook on shutdown")
        await redis.close()
        await dispose_engine()
        logger.info("Bot stopped gracefully")

    app.on_startup.append(_on_startup)
    app.on_shutdown.append(_on_shutdown)
    return app
