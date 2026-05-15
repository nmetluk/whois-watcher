"""Сборка ``Bot`` и ``Dispatcher`` aiogram.

Никаких глобальных переменных — всё через функции с DI. Это упрощает:

- тестирование (можно собрать Dispatcher без реального Bot/Redis)
- горизонтальное масштабирование (несколько процессов с разными ID/токенами)
- замену зависимостей (MemoryStorage в проде/тестах)
"""

from __future__ import annotations

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from arq import ArqRedis
from redis.asyncio import Redis

from src.bot.handlers import ROUTERS
from src.bot.middlewares import LocaleMiddleware, RateLimitMiddleware, UserRegisterMiddleware
from src.config.limits import Limits
from src.config.settings import Settings


def create_bot(token: str) -> Bot:
    """Создаёт ``Bot`` с ``parse_mode=HTML`` по умолчанию.

    HTML удобнее для подстановки имён и доменов в сообщения: не нужно
    эскейпить MarkdownV2-спецсимволы (``.``, ``-`` и т. п.), но обязательно
    эскейпить HTML-спецсимволы (``<``, ``>``, ``&``) — это сделано в локалях.
    """
    return Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))


def create_dispatcher(
    *,
    settings: Settings,
    limits: Limits,
    redis: Redis[str],
    arq_redis: ArqRedis | None = None,
) -> Dispatcher:
    """Собирает Dispatcher: MemoryStorage + middleware + роутеры.

    Зависимости (``settings``, ``limits``, ``redis``, ``arq_redis``) кладутся
    в ``workflow_data`` — будут доступны хэндлерам через одноимённые параметры.

    ``arq_redis`` опционален: в проде это пул ARQ для постановки задач, в
    тестах сборки Dispatcher достаточно None — задачи всё равно не дёргаем.
    """
    dp = Dispatcher(storage=MemoryStorage())

    # Прокидываем зависимости — aiogram автоматически инжектирует одноимённые
    # параметры в хэндлеры (например, ``redis: Redis``).
    dp["settings"] = settings
    dp["limits"] = limits
    dp["redis"] = redis
    dp["arq_redis"] = arq_redis

    # Порядок middleware (см. docs/architecture.md → "Бот"):
    # 1. регистрация пользователя — должна быть первой, остальные читают user
    # 2. локаль — кладёт data["lang"], читает user.language
    # 3. rate limit — читает user
    user_register = UserRegisterMiddleware(settings)
    locale = LocaleMiddleware()
    rate_limit = RateLimitMiddleware(redis, limits)

    for observer in (dp.message, dp.callback_query):
        observer.middleware(user_register)
        observer.middleware(locale)
        observer.middleware(rate_limit)

    for router in ROUTERS:
        dp.include_router(router)

    return dp
