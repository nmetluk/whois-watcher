"""Обработчик «голого» текста.

По спецификации ``docs/commands.md`` (раздел «Обработка плоского текста»):

- Если сообщение целиком похоже на домен — сразу запускаем ``/whois``-логику.
- Если в тексте есть домен (URL, фраза «проверь example.com») — тоже извлекаем
  и показываем карточку.
- Иначе — игнорируем.

FSM-сообщения сюда не доходят: соответствующий router'у регистрируется ПОСЛЕ
``settings`` и т. п., и явный guard ``state.get_state() is not None`` страхует
на случай переопределения порядка.
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from arq import ArqRedis

from src.bot.handlers.whois import _send_whois_card
from src.bot.validators import extract_domain_from_text, looks_like_just_domain
from src.config.limits import Limits
from src.db.models import User

router = Router(name="text")


@router.message(F.text, ~F.text.startswith("/"))
async def handle_plain_text(
    message: Message,
    state: FSMContext,
    user: User,
    lang: str,
    arq_redis: ArqRedis,
    limits: Limits,
) -> None:
    """Похоже на домен → карточка ``/whois``; иначе — молчим."""
    if await state.get_state() is not None:
        return
    text = message.text or ""

    if looks_like_just_domain(text):
        candidate = text.strip()
    else:
        candidate = extract_domain_from_text(text) or ""
    if not candidate:
        return

    await _send_whois_card(
        message=message,
        domain_input=candidate,
        user=user,
        lang=lang,
        arq_redis=arq_redis,
        limits=limits,
        force_refresh=False,
    )
