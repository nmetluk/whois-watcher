"""Rate-limit middleware на Redis.

Реализует sliding-окно через ``INCR`` + ``EXPIRE`` (упрощённая модель —
для нашего объёма этого достаточно, а классический sliding window можно
будет вкрутить на Этапе 3, если понадобится точность).

Ключи в Redis (см. ``docs/architecture.md``):

- ``rate:user:{user_id}:cmd_minute`` — общие команды в минуту
- ``rate:user:{user_id}:whois_minute`` — ``/whois`` и ``/check``

Команды-исключения: ``/start``, ``/cancel`` не лимитируются (UX-критично).
Лимиты ``/add/час`` и ``/download/сутки`` — на стороне самих хэндлеров
(они потребуют более точной семантики, ставим заглушку через middleware
только на простые сценарии).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject
from redis.asyncio import Redis

from src.config.limits import Limits
from src.db.models import User
from src.locales import t

# Команды, для которых работает «дорогой» WHOIS-лимит.
_WHOIS_COMMANDS = frozenset({"/whois", "/check"})
# Команды-исключения: лимит не применяем (важно для UX и админ-сценариев).
_BYPASS_COMMANDS = frozenset({"/start", "/cancel", "/help", "/delete_me", "/delete_me_confirm"})

# TTL ключей в Redis (секунды).
_CMD_WINDOW_SECONDS = 60
_WHOIS_WINDOW_SECONDS = 60

# Общий лимит команд в минуту на пользователя (мягкая защита от спама).
_MAX_CMD_PER_MINUTE = 30


def _first_word(text: str | None) -> str | None:
    if not text:
        return None
    return text.split(maxsplit=1)[0].lower()


class RateLimitMiddleware(BaseMiddleware):
    """Sliding window поверх Redis для команд бота.

    Принимает экземпляр ``Redis`` (async) и набор ``Limits``. Хранит счётчики
    в Redis, не в памяти процесса — чтобы при горизонтальном масштабировании
    бот не дублировал квоты.
    """

    def __init__(self, redis: Redis[str], limits: Limits) -> None:
        self._redis = redis
        self._limits = limits

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("user")
        if not isinstance(user, User):
            # Без зарегистрированного пользователя лимитировать нечего.
            return await handler(event, data)

        command = _extract_command(event)
        if command in _BYPASS_COMMANDS:
            return await handler(event, data)

        # 1) Общий лимит «команд в минуту».
        retry_after = await self._incr_and_check(
            key=f"rate:user:{user.id}:cmd_minute",
            limit=_MAX_CMD_PER_MINUTE,
            window_seconds=_CMD_WINDOW_SECONDS,
        )
        if retry_after is not None:
            await _reply_rate_limit(event, user, retry_after)
            return None

        # 2) Узкий лимит на WHOIS-команды.
        if command in _WHOIS_COMMANDS:
            retry_after = await self._incr_and_check(
                key=f"rate:user:{user.id}:whois_minute",
                limit=self._limits.max_whois_per_minute,
                window_seconds=_WHOIS_WINDOW_SECONDS,
            )
            if retry_after is not None:
                await _reply_rate_limit(event, user, retry_after)
                return None

        return await handler(event, data)

    async def _incr_and_check(
        self,
        *,
        key: str,
        limit: int,
        window_seconds: int,
    ) -> int | None:
        """Атомарно инкрементирует счётчик с TTL.

        Возвращает ``None`` если в пределах лимита, или число секунд до
        сброса окна — если лимит превышен.
        """
        count = await self._redis.incr(key)
        if count == 1:
            await self._redis.expire(key, window_seconds)
        if count > limit:
            ttl = await self._redis.ttl(key)
            return ttl if ttl > 0 else window_seconds
        return None


def _extract_command(event: TelegramObject) -> str | None:
    """Возвращает команду вида ``/cmd`` или ``None``.

    Для не-Message событий команда определяется как ``None`` (callback'и
    из inline-кнопок отдельно не лимитируем — они и так за хэндлером).
    """
    if isinstance(event, Message):
        cmd = _first_word(event.text or event.caption)
        if cmd and cmd.startswith("/"):
            return cmd.split("@", 1)[0]
    return None


async def _reply_rate_limit(event: TelegramObject, user: User, retry_after: int) -> None:
    """Сообщает пользователю о превышении лимита и завершает обработку."""
    text = t("errors.rate_limit", user.language, seconds=retry_after)
    if isinstance(event, Message):
        await event.answer(text)
    elif isinstance(event, CallbackQuery):
        await event.answer(text, show_alert=True)
