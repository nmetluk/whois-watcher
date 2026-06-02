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
from aiogram.fsm.storage.base import BaseStorage
from arq import ArqRedis
from redis.asyncio import Redis

from src.bot.handlers import ROUTERS
from src.bot.middlewares import (
    ClearAwaitingArgOnCommand,
    LocaleMiddleware,
    RateLimitMiddleware,
    UserRegisterMiddleware,
)
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
    storage: BaseStorage | None = None,
) -> Dispatcher:
    """Собирает Dispatcher: RedisStorage (FSM) + middleware + роутеры.

    Зависимости (``settings``, ``limits``, ``redis``, ``arq_redis``) кладутся
    в ``workflow_data`` — будут доступны хэндлерам через одноимённые параметры.

    ``arq_redis`` опционален: в проде это пул ARQ для постановки задач, в
    тестах сборки Dispatcher достаточно None — задачи всё равно не дёргаем.

    ``storage`` опционален (для тестов): если None — создаётся ``RedisStorage``
    с ``state_ttl`` из настроек + namespacing ``fsm:`` (ADR 041).
    """
    if storage is None:
        from aiogram.fsm.storage.base import DefaultKeyBuilder
        from aiogram.fsm.storage.redis import RedisStorage

        storage = RedisStorage.from_url(
            settings.redis_url,
            state_ttl=settings.redis_fsm_ttl,
            data_ttl=settings.redis_fsm_ttl,
            key_builder=DefaultKeyBuilder(prefix="fsm"),
        )

    dp = Dispatcher(storage=storage)

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
    # 4. clear-awaiting-arg (ADR 033) — только для message-observer'а:
    #    если пришла команда в состоянии AwaitingDomainArg.waiting, сбрасывает
    #    state ДО routing'а, чтобы команда пошла своим обычным путём.
    user_register = UserRegisterMiddleware(settings)
    locale = LocaleMiddleware()
    rate_limit = RateLimitMiddleware(redis, limits)
    clear_awaiting = ClearAwaitingArgOnCommand()

    for observer in (dp.message, dp.callback_query):
        observer.middleware(user_register)
        observer.middleware(locale)
        observer.middleware(rate_limit)
    dp.message.middleware(clear_awaiting)

    for router in ROUTERS:
        dp.include_router(router)

    return dp
