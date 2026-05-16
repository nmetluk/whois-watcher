"""Entrypoint бота: webhook-сервер aiohttp.

Запуск::

    python -m src.main

Что делает:

- настраивает structlog (JSON в production, console в development) и
  stdlib logging — через ``src.observability``
- подключает Sentry, если задан ``SENTRY_DSN``
- собирает ``Bot``, ``Dispatcher`` и aiohttp-приложение
- запускает ``web.run_app`` — он сам обрабатывает SIGINT/SIGTERM
"""

from __future__ import annotations

from aiohttp import web
from redis.asyncio import Redis

from src.bot.app import create_bot, create_dispatcher
from src.bot.webhook import create_app
from src.config.limits import get_limits
from src.config.settings import get_settings
from src.observability import setup_logging, setup_sentry


def main() -> None:
    """Точка входа: подняли logging/sentry → собрали app → web.run_app."""
    settings = get_settings()
    limits = get_limits()
    setup_logging(settings)
    setup_sentry(settings)

    bot = create_bot(settings.bot_token.get_secret_value())
    redis: Redis[str] = Redis.from_url(settings.redis_url, decode_responses=True)
    dp = create_dispatcher(settings=settings, limits=limits, redis=redis)
    app = create_app(bot=bot, dp=dp, settings=settings, redis=redis)

    web.run_app(
        app,
        host=settings.webhook_host,
        port=settings.webhook_port,
    )


if __name__ == "__main__":
    main()
