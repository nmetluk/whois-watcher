"""Хэндлеры команд Telegram-бота.

``ROUTERS`` — упорядоченный список роутеров для регистрации в Dispatcher.
Порядок важен:

1. ``start`` — высокая узнаваемость, ловит ``/start``
2. ``help_cancel`` — ``/help`` и ``/cancel``
3. ``settings`` — ``/settings`` и его FSM (вызывается до ``text``,
   чтобы FSM-ввод не уходил в plain-text fallback)
4. ``stats`` — ``/stats``
5. ``delete_me`` — ``/delete_me``, ``/delete_me_confirm``
6. ``stubs`` — заглушки WHOIS-команд
7. ``text`` — обработка не-команд (последний)
"""

from aiogram import Router

from src.bot.handlers import delete_me, help_cancel, settings, start, stats, stubs, text

ROUTERS: tuple[Router, ...] = (
    start.router,
    help_cancel.router,
    settings.router,
    stats.router,
    delete_me.router,
    stubs.router,
    text.router,
)

__all__ = ["ROUTERS"]
