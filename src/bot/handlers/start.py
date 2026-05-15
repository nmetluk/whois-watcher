"""Хэндлер команды ``/start``.

Пользователь к этому моменту уже создан/обновлён ``UserRegisterMiddleware``,
так что здесь только отвечаем приветствием.
"""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.bot.keyboards import StartAction, start_keyboard
from src.locales import t

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, lang: str) -> None:
    """``/start`` — приветствие с inline-меню."""
    await state.clear()
    await message.answer(
        t("start.greeting", lang),
        reply_markup=start_keyboard(lang),
    )


@router.callback_query(StartAction.filter())
async def handle_start_button(
    query: CallbackQuery,
    callback_data: StartAction,
    lang: str,
) -> None:
    """Кнопки приветственного меню.

    На Этапе 2 кнопки ``check`` и ``list`` ведут в заглушки. ``settings``
    подсказывает соответствующую команду — open submenu рендерит уже
    хэндлер из ``settings.py``.
    """
    await query.answer()
    if not isinstance(query.message, Message):
        return
    if callback_data.action == "check":
        await query.message.answer(t("stubs.coming_soon", lang, command="/whois"))
    elif callback_data.action == "list":
        await query.message.answer(t("stubs.coming_soon", lang, command="/list"))
    elif callback_data.action == "settings":
        await query.message.answer("/settings")
