"""Заглушки для команд, реализация которых отложена.

После того как ``/csv`` обзавёлся собственным модулем (``csv_export``),
здесь остаётся только заглушка ``/download``. Она уйдёт в следующем
коммите, когда мы подключим реальный массовый импорт.
"""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from src.locales import t

router = Router(name="stubs")


@router.message(Command("download"))
async def stub_download(message: Message, lang: str) -> None:
    await message.answer(t("stubs.coming_soon_download", lang))
