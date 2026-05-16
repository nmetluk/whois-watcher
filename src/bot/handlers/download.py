"""Хэндлер команды ``/download`` — массовый импорт доменов из файла.

FSM:

1. ``/download`` → ``DownloadStates.waiting_for_file`` + инструкция.
2. ``Message.document`` → парсинг, превью, ``DownloadStates.confirming_import``.
3. Callback ``DownloadAction(action="add")`` → bulk INSERT и постановка
   фоновых проверок.
4. Callback ``DownloadAction(action="cancel")`` / ``/cancel`` → state.clear().

Лимиты:

- ``MAX_DOWNLOADS_PER_DAY`` через Redis-счётчик ``rate:user:{id}:download_day``.
- ``5 МБ`` на размер файла (грубая защита — Telegram сам режет document'ы).
- ``MAX_DOMAINS_PER_DOWNLOAD`` на число доменов внутри файла.
- ``MAX_DOMAINS_PER_USER`` суммарно — если превышен, добавляем сколько влезет.

Постановка фоновой проверки распределена с задержкой между jobs, чтобы
не положить WHOIS-серверы при импорте больших списков.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, cast

from aiogram import Bot, F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    Document,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from arq import ArqRedis
from redis.asyncio import Redis

from src.bot.keyboards import DownloadAction
from src.bot.states import DownloadStates
from src.config.limits import Limits
from src.db.models import User
from src.db.repositories import DomainRepository, WhoisCacheRepository
from src.db.session import get_session
from src.locales import t
from src.services.csv_io import parse_domain_file

logger = logging.getLogger(__name__)

router = Router(name="download")

# Лимит размера файла (5 МБ ≈ 100K строк).
_MAX_FILE_BYTES = 5 * 1024 * 1024
_MAX_FILE_MB = 5

# Сколько домена показываем в превью.
_PREVIEW_SAMPLE_SIZE = 10
# Окно дневного лимита /download — 24 часа.
_DOWNLOAD_WINDOW_SECONDS = 24 * 60 * 60

# Задержка между постановками check_domain в очередь (защита WHOIS-серверов).
# Не блокирует, использует ARQ-defer: ``_in`` секунд.
_PER_DOMAIN_ENQUEUE_DELAY_SECONDS = 1.0


# ---------------------------------------------------------------------------
# Клавиатуры
# ---------------------------------------------------------------------------


def _cancel_keyboard(lang: str) -> InlineKeyboardMarkup:
    """Одна кнопка «Отмена» под подсказкой ожидания файла."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t("download.cancel_button", lang),
                    callback_data=DownloadAction(action="cancel").pack(),
                )
            ]
        ]
    )


def _preview_keyboard(*, new_count: int, lang: str) -> InlineKeyboardMarkup:
    """Кнопки превью: «Добавить N» и «Отмена»."""
    rows: list[list[InlineKeyboardButton]] = []
    if new_count > 0:
        rows.append(
            [
                InlineKeyboardButton(
                    text=t("download.confirm_button", lang, count=new_count),
                    callback_data=DownloadAction(action="add").pack(),
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text=t("download.cancel_button", lang),
                callback_data=DownloadAction(action="cancel").pack(),
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ---------------------------------------------------------------------------
# Шаг 1: /download
# ---------------------------------------------------------------------------


@router.message(Command("download"))
async def cmd_download(
    message: Message,
    state: FSMContext,
    user: User,
    lang: str,
    redis: Redis[str],
    limits: Limits,
) -> None:
    """``/download`` — войти в режим ожидания файла."""
    # Дневной лимит проверяем ДО входа в FSM, чтобы не блокировать пользователя
    # лишним состоянием.
    if await _is_rate_limited(redis, user.id, limits):
        await message.answer(t("download.rate_limit", lang, limit=limits.max_downloads_per_day))
        return

    await state.clear()
    await state.set_state(DownloadStates.waiting_for_file)
    await message.answer(
        t("download.intro", lang, limit=limits.max_domains_per_download),
        reply_markup=_cancel_keyboard(lang),
    )


# ---------------------------------------------------------------------------
# Шаг 2: приём файла
# ---------------------------------------------------------------------------


@router.message(StateFilter(DownloadStates.waiting_for_file), F.document)
async def on_document(
    message: Message,
    state: FSMContext,
    user: User,
    lang: str,
    bot: Bot,
    limits: Limits,
) -> None:
    """Принимает документ от пользователя в state ``waiting_for_file``."""
    document = message.document
    if document is None:  # pragma: no cover — фильтр выше уже отсёк
        await message.answer(t("download.no_file", lang))
        return

    if document.file_size is not None and document.file_size > _MAX_FILE_BYTES:
        await message.answer(t("download.too_large", lang, max_mb=_MAX_FILE_MB))
        return

    content = await _download_document(bot, document)
    if content is None:
        await message.answer(t("download.parse_failed", lang))
        return

    parsed = parse_domain_file(content, max_domains=limits.max_domains_per_download)
    if not parsed.valid_domains and not parsed.invalid_lines:
        await message.answer(t("download.parse_failed", lang))
        await state.clear()
        return

    async with get_session() as session:
        domain_repo = DomainRepository(session)
        already = await domain_repo.bulk_existing_for_user(user.id, parsed.valid_domains)

    new_domains = [d for d in parsed.valid_domains if d not in already]

    preview = t(
        "download.preview",
        lang,
        total=len(parsed.valid_domains) + len(parsed.invalid_lines),
        new=len(new_domains),
        already=len(already),
        invalid=len(parsed.invalid_lines),
    )
    if parsed.truncated:
        preview += t("download.preview_truncated", lang, limit=limits.max_domains_per_download)

    await state.set_state(DownloadStates.confirming_import)
    await state.update_data(new_domains=new_domains)

    await message.answer(
        preview, reply_markup=_preview_keyboard(new_count=len(new_domains), lang=lang)
    )


@router.message(StateFilter(DownloadStates.waiting_for_file))
async def on_not_document(message: Message, lang: str) -> None:
    """В ожидании файла, а пришло что-то другое (текст и т. п.)."""
    await message.answer(t("download.no_file", lang))


# ---------------------------------------------------------------------------
# Шаг 3: подтверждение / отмена
# ---------------------------------------------------------------------------


@router.callback_query(
    StateFilter(DownloadStates.confirming_import),
    DownloadAction.filter(F.action == "add"),
)
async def on_confirm_add(
    query: CallbackQuery,
    state: FSMContext,
    user: User,
    lang: str,
    arq_redis: ArqRedis,
    redis: Redis[str],
    limits: Limits,
) -> None:
    """Подтверждение импорта: bulk INSERT + постановка проверок."""
    data = await state.get_data()
    new_domains: list[str] = list(data.get("new_domains") or [])
    if not new_domains:
        await state.clear()
        await query.answer()
        if query.message is not None and isinstance(query.message, Message):
            await query.message.answer(t("download.nothing_to_add", lang))
        return

    async with get_session() as session:
        domain_repo = DomainRepository(session)
        cache_repo = WhoisCacheRepository(session)

        current = await domain_repo.count_by_user(user.id)
        free_slots = max(0, limits.max_domains_per_user - current)
        to_add = new_domains[:free_slots]
        was_truncated_by_limit = len(to_add) < len(new_domains)

        inserted = await domain_repo.bulk_add(user.id, to_add) if to_add else 0
        # Заводим строки в whois_cache только для тех, кого ещё нет —
        # bulk_ensure возвращает домены, для которых строка была создана.
        if to_add:
            created_cache = await cache_repo.bulk_ensure(to_add)
        else:
            created_cache = []

    # Считаем дневной счётчик ТОЛЬКО когда реально что-то добавили.
    if inserted > 0:
        await _increment_download_counter(redis, user.id)

    # Очереди ставим распределённо — без блокировки текущего ответа.
    if created_cache:
        asyncio.create_task(  # noqa: RUF006
            _enqueue_checks_with_delay(arq_redis, list(created_cache))
        )

    await state.clear()
    await query.answer()

    if query.message is not None and isinstance(query.message, Message):
        if was_truncated_by_limit and inserted > 0:
            await query.message.answer(
                t(
                    "download.limit_exceeded",
                    lang,
                    fits=inserted,
                    requested=len(new_domains),
                    limit=limits.max_domains_per_user,
                )
            )
        else:
            await query.message.answer(t("download.success", lang, count=inserted))


@router.callback_query(
    StateFilter(DownloadStates.waiting_for_file, DownloadStates.confirming_import),
    DownloadAction.filter(F.action == "cancel"),
)
async def on_cancel(query: CallbackQuery, state: FSMContext, lang: str) -> None:
    """Отмена через inline-кнопку из любого состояния импорта."""
    await state.clear()
    await query.answer()
    if query.message is not None and isinstance(query.message, Message):
        await query.message.answer(t("download.cancel", lang))


# ---------------------------------------------------------------------------
# Вспомогательное
# ---------------------------------------------------------------------------


async def _download_document(bot: Bot, document: Document) -> bytes | None:
    """Скачивает содержимое документа через ``bot.download``.

    Возвращает ``None`` на любых ошибках — хэндлер просто покажет
    «не удалось разобрать файл».
    """
    try:
        buffer = await bot.download(document.file_id)
    except Exception:  # — границы внешней API
        logger.exception("Failed to download document %s", document.file_id)
        return None
    if buffer is None:
        return None
    data = buffer.read()
    return data if isinstance(data, bytes) else bytes(data)


async def _is_rate_limited(redis: Redis[str], user_id: int, limits: Limits) -> bool:
    """True, если дневной лимит ``/download`` уже исчерпан.

    Сам инкремент делаем только в случае фактического добавления — так
    отмена/невалидный файл не съедают квоту.
    """
    key = _download_counter_key(user_id)
    raw = await redis.get(key)
    try:
        count = int(raw) if raw is not None else 0
    except (TypeError, ValueError):
        count = 0
    return count >= limits.max_downloads_per_day


async def _increment_download_counter(redis: Redis[str], user_id: int) -> None:
    """Инкремент счётчика дневного лимита (после успешной операции)."""
    key = _download_counter_key(user_id)
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, _DOWNLOAD_WINDOW_SECONDS)


def _download_counter_key(user_id: int) -> str:
    return f"rate:user:{user_id}:download_day"


async def _enqueue_checks_with_delay(arq_redis: ArqRedis, domains: list[str]) -> None:
    """Ставит ``check_domain`` для каждого домена с растущим defer-смещением.

    ARQ умеет ``_defer_by`` через ``defer_until`` или ``_defer_by`` — мы
    используем ``_defer_by`` (timedelta) на каждый job. Это не блокирует
    воркера и не плодит ``asyncio.sleep`` в хэндлере.
    """
    from datetime import timedelta

    for index, domain in enumerate(domains):
        defer_by = timedelta(seconds=_PER_DOMAIN_ENQUEUE_DELAY_SECONDS * index)
        try:
            await cast(Any, arq_redis).enqueue_job("check_domain", domain, _defer_by=defer_by)
        except Exception:
            logger.exception("Failed to enqueue check_domain for %s", domain)


__all__ = ["router"]
