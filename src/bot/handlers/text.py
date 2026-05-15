"""Обработчик «голого» текста: домен без команды.

Согласно ``docs/commands.md`` (раздел «Обработка плоского текста»):

- если сообщение похоже на домен — должны были бы запустить ``/whois``-логику
- на Этапе 2 WHOIS-логики нет, поэтому отвечаем заглушкой
- если это не домен и не URL — игнорируем
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from src.bot.validators import extract_domain_from_text, looks_like_just_domain
from src.locales import t

router = Router(name="text")


@router.message(F.text, ~F.text.startswith("/"))
async def handle_plain_text(message: Message, state: FSMContext, lang: str) -> None:
    """Не-команда: похоже на домен → заглушка, иначе игнорируем."""
    # Если пользователь в FSM — не перехватываем; ввод пойдёт в соответствующий
    # FSM-хэндлер. ``Router`` всё равно отдаёт приоритет более специфичным
    # фильтрам, но явный guard читается яснее.
    if await state.get_state() is not None:
        return
    text = message.text or ""
    if looks_like_just_domain(text) or extract_domain_from_text(text):
        await message.answer(t("stubs.coming_soon_text", lang))
