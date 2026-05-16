"""Хэндлеры команд Telegram-бота.

``ROUTERS`` — упорядоченный список роутеров для регистрации в Dispatcher.
Порядок важен: команды-команды → callback'и → plain-text fallback.

1. ``start``         — ``/start``
2. ``help_cancel``   — ``/help``, ``/cancel``
3. ``settings``      — ``/settings`` + FSM (до ``text``, чтобы FSM-ввод не уходил
   в plain-text fallback)
4. ``stats``         — ``/stats``
5. ``delete_me``     — ``/delete_me``, ``/delete_me_confirm``
6. ``whois``         — ``/whois`` + callback'и карточки
7. ``add_remove``    — ``/add``, ``/rmv``
8. ``check``         — ``/check`` (после ``whois``, чтобы общий хелпер был доступен)
9. ``list_domains``  — ``/list`` + пагинация + фильтры
10. ``notifications`` — ``/notify``, ``/unnotify`` + callback'и из уведомлений
11. ``csv_export``   — ``/csv``
12. ``stubs``        — оставшиеся нереализованные команды (/download)
13. ``text``         — обработка не-команд (последний)
"""

from aiogram import Router

from src.bot.handlers import (
    add_remove,
    check,
    csv_export,
    delete_me,
    help_cancel,
    list_domains,
    notifications,
    settings,
    start,
    stats,
    stubs,
    text,
    whois,
)

ROUTERS: tuple[Router, ...] = (
    start.router,
    help_cancel.router,
    settings.router,
    stats.router,
    delete_me.router,
    whois.router,
    add_remove.router,
    check.router,
    list_domains.router,
    notifications.router,
    csv_export.router,
    stubs.router,
    text.router,
)

__all__ = ["ROUTERS"]
