"""Хэндлер команды ``/start`` и колбэков приветственного меню.

Пользователь к этому моменту уже создан/обновлён ``UserRegisterMiddleware``.
"""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from arq import ArqRedis
from redis.asyncio import Redis

from src.bot.handlers.list_domains import cmd_list
from src.bot.handlers.settings import cmd_settings
from src.bot.keyboards import StartAction, start_keyboard, webapp_open_keyboard
from src.config.limits import Limits
from src.config.settings import Settings
from src.db.models import User
from src.locales import t

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, lang: str, settings: Settings) -> None:
    """``/start`` — приветствие с inline-меню (+ кнопка WebApp, ADR 043)."""
    await state.clear()
    await message.answer(
        t("start.greeting", lang),
        reply_markup=start_keyboard(lang, webapp_url=settings.webapp_url),
    )


@router.message(Command("webapp", "app", "dashboard"))
async def cmd_webapp(message: Message, lang: str, settings: Settings) -> None:
    """``/webapp`` / ``/app`` / ``/dashboard`` — кнопка запуска mini-app (ADR 043)."""
    await message.answer(
        t("webapp.open_prompt", lang),
        reply_markup=webapp_open_keyboard(lang, settings.webapp_url),
    )


@router.callback_query(StartAction.filter())
async def handle_start_button(
    query: CallbackQuery,
    callback_data: StartAction,
    user: User,
    lang: str,
    arq_redis: ArqRedis,
    limits: Limits,
    state: FSMContext,
    redis: Redis[str],
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
        await cmd_list(
            query.message,
            user=user,
            lang=lang,
            arq_redis=arq_redis,
            limits=limits,
            redis=redis,
            state=state,
        )
    elif callback_data.action == "settings":
        await cmd_settings(query.message, user=user, lang=lang)
