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
12. ``download``     — ``/download`` + FSM + callback'и превью
13. ``admin``        — ``/admin`` (доступ ограничен ADMIN_USER_IDS)
14. ``version``      — скрытая ``/version`` (диагностика, не в меню/help)
15. ``wishlist``     — ``/wishlist`` + callback'и уведомления «домен освободился»
16. ``subdomains``   — ``/subdomains`` + callback'и (ADR 037)
17. ``stubs``        — пустой роутер (зарезервирован под будущие команды)
18. ``awaiting_arg`` — FSM-flow для команд без аргумента (ADR 033). ВАЖНО:
   должен идти ПОСЛЕ всех command-роутеров и ПЕРЕД ``text``-fallback'ом —
   тогда команды разбираются обычным path'ом, а текст в state'е
   подхватывается этим роутером, а не plain-text-роутером.
19. ``text``         — обработка не-команд (последний)
"""

from aiogram import Router

from src.bot.handlers import (
    add_remove,
    admin,
    awaiting_arg,
    check,
    csv_export,
    delete_me,
    download,
    help_cancel,
    list_domains,
    notifications,
    notify_config,
    settings,
    start,
    stats,
    stubs,
    subdomains,
    text,
    version,
    whois,
    wishlist,
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
    notify_config.router,  # Этап 11 — inline-конфигуратор уведомлений
    csv_export.router,
    download.router,
    admin.router,
    version.router,
    wishlist.router,
    subdomains.router,  # Этап 18 — subdomain enumeration (ADR 037)
    stubs.router,
    awaiting_arg.router,  # ADR 033 — FSM-flow для команд без аргумента
    text.router,
)

__all__ = ["ROUTERS"]
