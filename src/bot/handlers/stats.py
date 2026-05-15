"""Хэндлер команды ``/stats``.

На Этапе 2 у нас нет WHOIS-данных в БД: пока воркеры не наполнят
``whois_cache``, поля «с данными» и «истекает за N» будут нулевыми.
Команда уже рабочая — выборка живая через ``DomainRepository``.
"""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from src.db.models import User
from src.db.repositories import DomainRepository
from src.db.session import get_session
from src.locales import t

router = Router(name="stats")


@router.message(Command("stats"))
async def cmd_stats(message: Message, user: User, lang: str) -> None:
    """``/stats`` — статистика портфеля пользователя."""
    async with get_session() as session:
        domains = DomainRepository(session)
        stats = await domains.get_user_stats(user.id)
    body = t(
        "commands.stats.body",
        lang,
        total=stats.total,
        with_data=stats.with_data,
        without_data=stats.without_data,
        exp_7=stats.expiring_7,
        exp_30=stats.expiring_30,
        exp_90=stats.expiring_90,
        muted=stats.muted,
        added_month=stats.added_month,
    )
    await message.answer(body)
