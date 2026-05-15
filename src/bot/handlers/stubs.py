"""Заглушки для команд, требующих WHOIS-логики (Этапы 3-4).

Эти команды нужно объявить уже на Этапе 2, чтобы:

- ``set_my_commands`` показывал полный список в меню Telegram
- bot не отвечал «команда не распознана» на знакомые слова
- интерфейс уже сейчас был «бесшовным» для пользователя
"""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from src.locales import t

router = Router(name="stubs")


@router.message(Command("whois"))
async def stub_whois(message: Message, lang: str) -> None:
    await message.answer(t("stubs.coming_soon", lang, command="/whois"))


@router.message(Command("add"))
async def stub_add(message: Message, lang: str) -> None:
    await message.answer(t("stubs.coming_soon", lang, command="/add"))


@router.message(Command("rmv"))
async def stub_rmv(message: Message, lang: str) -> None:
    await message.answer(t("stubs.coming_soon", lang, command="/rmv"))


@router.message(Command("list"))
async def stub_list(message: Message, lang: str) -> None:
    await message.answer(t("stubs.coming_soon", lang, command="/list"))


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


@router.message(Command("check"))
async def stub_check(message: Message, lang: str) -> None:
    await message.answer(t("stubs.coming_soon", lang, command="/check"))
