"""Entrypoint бота: webhook-сервер aiohttp.

Запуск::

    python -m src.main

Что делает:

- настраивает structlog (JSON в production, console в development)
- подключает Sentry, если задан ``SENTRY_DSN`` — через ``src.observability``
- собирает ``Bot``, ``Dispatcher`` и aiohttp-приложение
- запускает ``web.run_app`` — он сам обрабатывает SIGINT/SIGTERM
"""

from __future__ import annotations

import logging
import sys

import structlog
from aiohttp import web
from redis.asyncio import Redis

from src.bot.app import create_bot, create_dispatcher
from src.bot.webhook import create_app
from src.config.limits import get_limits
from src.config.settings import Settings, get_settings
from src.observability import setup_sentry


def _setup_logging(settings: Settings) -> None:
    """Настраивает structlog: console для dev, JSON для prod."""
    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        timestamper,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    renderer: structlog.types.Processor
    if settings.environment == "production":
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=False)

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(settings.log_level)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )

    # Привязываем stdlib logging к stderr с тем же уровнем — чтобы логи
    # aiogram/aiohttp/SQLAlchemy не терялись.
    logging.basicConfig(
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        level=settings.log_level,
        stream=sys.stderr,
    )


def main() -> None:
    """Точка входа: подняли logging/sentry → собрали app → web.run_app."""
    settings = get_settings()
    limits = get_limits()
    _setup_logging(settings)
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
