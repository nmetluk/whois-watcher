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
from sqlalchemy.ext.asyncio import AsyncSession

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


async def send_user_csv_file(
    target: Message,
    user: User,
    lang: str,
    session: AsyncSession,
) -> None:
    """Сгенерировать и отправить CSV-файл с доменами пользователя.

    Общий путь для команды ``/csv`` и для inline-кнопки «📥 CSV» в /list
    (Этап 9, баг-фикс): раньше кнопка отправляла только подсказку
    «используйте /csv», теперь делает то же самое, что и сама команда.

    :param target: куда отправлять — ``Message`` от команды или
        ``query.message`` от callback'а. Поведение одинаковое: оба умеют
        ``answer`` и ``answer_document``.
    :param session: открытая БД-сессия (используется только для подсчёта
        количества доменов перед exporto-м). Тяжёлая часть —
        ``generate_user_csv`` — открывает свою собственную сессию.
    """
    total = await DomainRepository(session).count_by_user(user.id)

    if total == 0:
        await target.answer(t("csv.empty", lang))
        return

    if total >= _LARGE_PORTFOLIO_THRESHOLD:
        await target.answer(t("csv.generating", lang, count=total))

    csv_bytes, count = await generate_user_csv(user.id)
    today = datetime.now(tz=UTC).strftime("%Y-%m-%d")
    filename = f"domains_{today}.csv"
    document = BufferedInputFile(csv_bytes, filename=filename)
    await target.answer_document(
        document,
        caption=t("csv.ready", lang, count=count),
    )


@router.message(Command("csv"))
async def cmd_csv(message: Message, user: User, lang: str) -> None:
    """``/csv`` — собрать и отправить CSV-файл со списком доменов."""
    async with get_session() as session:
        await send_user_csv_file(message, user, lang, session)


__all__ = ["cmd_csv", "router", "send_user_csv_file"]
