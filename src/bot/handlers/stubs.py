"""Заглушки для команд, требующих логики этапов 5-6.

Реализованные команды (/whois, /add, /rmv, /list, /check) живут в собственных
модулях. Здесь — только то, что ещё не реализовано: импорт/экспорт CSV и
гранулярная настройка уведомлений.
"""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from src.locales import t

router = Router(name="stubs")


@router.message(Command("csv"))
async def stub_csv(message: Message, lang: str) -> None:
    await message.answer(t("stubs.coming_soon", lang, command="/csv"))


@router.message(Command("download"))
async def stub_download(message: Message, lang: str) -> None:
    await message.answer(t("stubs.coming_soon_download", lang))


@router.message(Command("notify"))
async def stub_notify(message: Message, lang: str) -> None:
    await message.answer(t("stubs.coming_soon", lang, command="/notify"))


@router.message(Command("unnotify"))
async def stub_unnotify(message: Message, lang: str) -> None:
    await message.answer(t("stubs.coming_soon", lang, command="/unnotify"))
