"""Команды для меню BotFather (``bot.set_my_commands``).

Списки для двух языков по спецификации ``docs/commands.md``. В меню НЕ
выводятся служебные команды ``/cancel`` и ``/delete_me_confirm``.
"""

from __future__ import annotations

from aiogram.types import BotCommand

# Внутренний тип — два списка (ru, en) вместо словаря, чтобы порядок
# команд был жёстко зафиксирован.
COMMANDS_RU: tuple[BotCommand, ...] = (
    BotCommand(command="start", description="Начать работу"),
    BotCommand(command="whois", description="Проверить домен"),
    BotCommand(command="add", description="Добавить домен на слежение"),
    BotCommand(command="rmv", description="Удалить домен"),
    BotCommand(command="list", description="Список ваших доменов"),
    BotCommand(command="wishlist", description="Wishlist: ждать освобождения домена"),
    BotCommand(command="csv", description="Экспорт в CSV"),
    BotCommand(command="download", description="Импорт из файла"),
    BotCommand(command="notify", description="Включить уведомления"),
    BotCommand(command="unnotify", description="Выключить уведомления"),
    BotCommand(command="settings", description="Настройки"),
    BotCommand(command="stats", description="Статистика"),
    BotCommand(command="check", description="Принудительная проверка"),
    BotCommand(command="help", description="Справка"),
    BotCommand(command="delete_me", description="Удалить все мои данные"),
)

COMMANDS_EN: tuple[BotCommand, ...] = (
    BotCommand(command="start", description="Start working with the bot"),
    BotCommand(command="whois", description="Check a domain"),
    BotCommand(command="add", description="Track a domain"),
    BotCommand(command="rmv", description="Remove a domain"),
    BotCommand(command="list", description="List your domains"),
    BotCommand(command="wishlist", description="Wishlist: wait for a domain to drop"),
    BotCommand(command="csv", description="Export to CSV"),
    BotCommand(command="download", description="Bulk import from a file"),
    BotCommand(command="notify", description="Enable notifications"),
    BotCommand(command="unnotify", description="Disable notifications"),
    BotCommand(command="settings", description="Settings"),
    BotCommand(command="stats", description="Statistics"),
    BotCommand(command="check", description="Force a domain refresh"),
    BotCommand(command="help", description="Help"),
    BotCommand(command="delete_me", description="Delete all my data"),
)
