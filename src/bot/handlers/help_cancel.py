"""Хэндлеры ``/help`` и ``/cancel``.

Объединены в один файл — обе команды короткие и без бизнес-логики.
"""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from src.locales import t

router = Router(name="help_cancel")

# URL'ы внешних ресурсов под кнопками /help.
# Жёстко зашиты — это публичные ссылки проекта, не секреты.
_PRIVACY_URL = "https://github.com/your-org/whois-watcher/blob/main/PRIVACY.md"
_GITHUB_URL = "https://github.com/your-org/whois-watcher"


def _help_keyboard(lang: str) -> InlineKeyboardMarkup:
    """Кнопки внизу справки: ссылки на политику и GitHub."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=t("button.privacy", lang), url=_PRIVACY_URL),
                InlineKeyboardButton(text=t("button.github", lang), url=_GITHUB_URL),
            ]
        ]
    )


@router.message(Command("help"))
async def cmd_help(message: Message, lang: str) -> None:
    """``/help`` — развёрнутая справка."""
    await message.answer(t("help.body", lang), reply_markup=_help_keyboard(lang))


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext, lang: str) -> None:
    """``/cancel`` — сброс активного FSM-состояния."""
    current_state = await state.get_state()
    if current_state is None:
        await message.answer(t("cancel.nothing", lang))
        return
    await state.clear()
    await message.answer(t("cancel.done", lang))
