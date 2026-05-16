"""Хэндлер команды ``/csv`` — экспорт списка доменов пользователя в файл.

Пустой портфель → короткий текстовый ответ. Иначе — генерируем CSV и
отдаём документом ``domains_YYYY-MM-DD.csv``. Для больших портфелей
заранее присылаем подсказку «Готовлю файл...», чтобы пользователь не
думал, что бот завис.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import BufferedInputFile, Message

from src.db.models import User
from src.db.repositories import DomainRepository
from src.db.session import get_session
from src.locales import t
from src.services.csv_io import generate_user_csv

logger = logging.getLogger(__name__)

router = Router(name="csv_export")

# Порог, выше которого предупреждаем «Готовлю файл…». Запрос >10K строк
# с JOIN по whois_cache занимает заметное время (секунды).
_LARGE_PORTFOLIO_THRESHOLD = 10_000


@router.message(Command("csv"))
async def cmd_csv(message: Message, user: User, lang: str) -> None:
    """``/csv`` — собрать и отправить CSV-файл со списком доменов."""
    async with get_session() as session:
        domain_repo = DomainRepository(session)
        total = await domain_repo.count_by_user(user.id)

    if total == 0:
        await message.answer(t("csv.empty", lang))
        return

    if total >= _LARGE_PORTFOLIO_THRESHOLD:
        await message.answer(t("csv.generating", lang, count=total))

    csv_bytes, count = await generate_user_csv(user.id)
    today = datetime.now(tz=UTC).strftime("%Y-%m-%d")
    filename = f"domains_{today}.csv"
    document = BufferedInputFile(csv_bytes, filename=filename)
    await message.answer_document(
        document,
        caption=t("csv.ready", lang, count=count),
    )


__all__ = ["router"]
