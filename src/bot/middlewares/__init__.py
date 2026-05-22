"""Мидлвары aiogram: регистрация пользователя, локаль, rate limit.

Порядок регистрации в Dispatcher важен:

1. ``UserRegisterMiddleware`` — создаёт/обновляет ``User``, кладёт в ``data["user"]``
2. ``LocaleMiddleware`` — кладёт ``data["lang"]`` (читает ``data["user"]``)
3. ``RateLimitMiddleware`` — проверяет лимиты по ``data["user"]``
4. ``ClearAwaitingArgOnCommand`` — сбрасывает FSM-state на любую команду
   (ADR 033)
"""

from src.bot.middlewares.clear_state_on_command import ClearAwaitingArgOnCommand
from src.bot.middlewares.locale import LocaleMiddleware
from src.bot.middlewares.rate_limit import RateLimitMiddleware
from src.bot.middlewares.user_register import UserRegisterMiddleware

__all__ = [
    "ClearAwaitingArgOnCommand",
    "LocaleMiddleware",
    "RateLimitMiddleware",
    "UserRegisterMiddleware",
]
