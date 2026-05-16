"""Хэндлер команды ``/start`` и колбэков приветственного меню.

Пользователь к этому моменту уже создан/обновлён ``UserRegisterMiddleware``.
"""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from arq import ArqRedis

from src.bot.handlers.list_domains import cmd_list
from src.bot.handlers.settings import cmd_settings
from src.bot.keyboards import StartAction, start_keyboard
from src.config.limits import Limits
from src.db.models import User
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
    user: User,
    lang: str,
    arq_redis: ArqRedis,
    limits: Limits,
) -> None:
    """Кнопки приветственного меню.

    ``check``    — подсказка отправить домен сообщением (plain-text-хэндлер
                   уже распознаёт домены и показывает WHOIS).
    ``list``     — переиспользуем хэндлер ``cmd_list`` напрямую.
    ``settings`` — переиспользуем ``cmd_settings`` напрямую.
    """
    await query.answer()
    if not isinstance(query.message, Message):
        return
    if callback_data.action == "check":
        await query.message.answer(t("start.check_prompt", lang))
    elif callback_data.action == "list":
        await cmd_list(query.message, user=user, lang=lang, arq_redis=arq_redis, limits=limits)
    elif callback_data.action == "settings":
        await cmd_settings(query.message, user=user, lang=lang)
