"""Хэндлер команды ``/settings`` и связанных callback'ов.

UX по ``docs/commands.md``:

- Главное меню — текущие значения + 4 кнопки (TZ / время / дни / язык)
- TZ: пресеты + «ввести вручную» (FSM ``waiting_for_timezone``)
- Время: 24 кнопки 00–23, прямой выбор
- Дни напоминаний: 3 пресета + «свои» (FSM ``waiting_for_notify_days``)
- Язык: ru / en

Все изменения сохраняются через ``UserRepository.update_settings``.
"""

from __future__ import annotations

import re

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from src.bot.keyboards import (
    SettingsAction,
    settings_days,
    settings_language,
    settings_main,
    settings_time,
    settings_timezone,
)
from src.bot.states import SettingsStates
from src.db.models import User
from src.db.repositories import UserRepository
from src.db.session import get_session
from src.locales import LOCALES, t
from src.utils.timezone import is_valid_timezone

router = Router(name="settings")


# Допустимые символы при ручном вводе дней — цифры, пробелы, запятые.
# Принимаем: ``"30 7 1"``, ``"30,7,1"``, ``"30, 7, 1"``.
_NOTIFY_DAYS_SPLIT_RE = re.compile(r"[\s,]+")

# Максимум разумных значений — защита от ввода типа «1 2 3 ... 365».
_MAX_NOTIFY_DAYS_COUNT = 10
_MAX_NOTIFY_DAY_VALUE = 365


def _format_notify_days(days: list[int]) -> str:
    return ", ".join(str(d) for d in days)


def _menu_text(user: User, lang: str) -> str:
    language_label = t(f"commands.settings.lang_{user.language}_name", lang)
    return t(
        "commands.settings.menu",
        lang,
        timezone=user.timezone,
        hour=user.notify_at_hour,
        notify_days=_format_notify_days(list(user.notify_days)),
        language=language_label,
    )


async def _reload_user(telegram_id: int, fallback: User) -> User:
    """Перечитывает пользователя из БД (после ``update_settings``).

    Если в БД его внезапно нет (мог быть удалён параллельно) — возвращаем
    переданный ``fallback``, чтобы не падать в обработчике callback'а.
    """
    async with get_session() as session:
        users = UserRepository(session)
        fresh = await users.get_by_telegram_id(telegram_id)
    return fresh if fresh is not None else fallback


@router.message(Command("settings"))
async def cmd_settings(message: Message, user: User, lang: str) -> None:
    """``/settings`` — главное меню."""
    await message.answer(_menu_text(user, lang), reply_markup=settings_main(lang))


# ---------------------------------------------------------------------------
# Главное меню — переходы в подменю
# ---------------------------------------------------------------------------


@router.callback_query(SettingsAction.filter())
async def handle_settings_callback(
    query: CallbackQuery,
    callback_data: SettingsAction,
    state: FSMContext,
    user: User,
    lang: str,
) -> None:
    """Один обработчик на все ветки меню — диспетчеризация по ``action``."""
    action = callback_data.action

    if action == "tz":
        await _edit(query, t("commands.settings.choose_timezone", lang), settings_timezone(lang))
    elif action == "time":
        await _edit(query, t("commands.settings.choose_time", lang), settings_time(lang))
    elif action == "days":
        await _edit(query, t("commands.settings.choose_days", lang), settings_days(lang))
    elif action == "lang":
        await _edit(query, t("commands.settings.choose_language", lang), settings_language(lang))
    elif action == "back":
        fresh = await _reload_user(user.telegram_id, fallback=user)
        await _edit(query, _menu_text(fresh, lang), settings_main(lang))

    elif action == "tz_pick":
        await _save_timezone(query, callback_data.value, user=user, lang=lang)
    elif action == "tz_custom":
        await state.set_state(SettingsStates.waiting_for_timezone)
        await _edit(query, t("commands.settings.tz_prompt_manual", lang))

    elif action == "time_pick":
        await _save_time(query, callback_data.value, user=user, lang=lang)

    elif action == "days_pick":
        await _save_days_from_preset(query, callback_data.value, user=user, lang=lang)
    elif action == "days_custom":
        await state.set_state(SettingsStates.waiting_for_notify_days)
        await _edit(query, t("commands.settings.days_prompt_custom", lang))

    elif action == "lang_pick":
        await _save_language(query, callback_data.value, user=user)

    await query.answer()


# ---------------------------------------------------------------------------
# Сохранение значений
# ---------------------------------------------------------------------------


async def _save_timezone(
    query: CallbackQuery,
    tz_name: str,
    *,
    user: User,
    lang: str,
) -> None:
    if not is_valid_timezone(tz_name):
        await query.answer(t("errors.invalid_timezone", lang), show_alert=True)
        return
    async with get_session() as session:
        users = UserRepository(session)
        await users.update_settings(user.id, timezone=tz_name)
    await _edit(query, t("commands.settings.tz_saved", lang, timezone=tz_name))


async def _save_time(
    query: CallbackQuery,
    raw_hour: str,
    *,
    user: User,
    lang: str,
) -> None:
    try:
        hour = int(raw_hour)
    except ValueError:
        return
    if not 0 <= hour <= 23:
        return
    async with get_session() as session:
        users = UserRepository(session)
        await users.update_settings(user.id, notify_at_hour=hour)
    await _edit(query, t("commands.settings.time_saved", lang, hour=hour))


async def _save_days_from_preset(
    query: CallbackQuery,
    raw_days: str,
    *,
    user: User,
    lang: str,
) -> None:
    days = _parse_notify_days(raw_days)
    if days is None:
        return
    async with get_session() as session:
        users = UserRepository(session)
        await users.update_settings(user.id, notify_days=days)
    await _edit(
        query,
        t("commands.settings.days_saved", lang, notify_days=_format_notify_days(days)),
    )


async def _save_language(query: CallbackQuery, new_lang: str, *, user: User) -> None:
    if new_lang not in LOCALES:
        return
    async with get_session() as session:
        users = UserRepository(session)
        await users.update_settings(user.id, language=new_lang)
    # Сообщение об успехе показываем уже на новом языке — пользователь только
    # что выбрал его, ожидает увидеть результат именно так.
    label = t(f"commands.settings.lang_{new_lang}_name", new_lang)
    await _edit(query, t("commands.settings.language_saved", new_lang, language=label))


# ---------------------------------------------------------------------------
# FSM-ввод: ручная TZ и ручные дни
# ---------------------------------------------------------------------------


@router.message(SettingsStates.waiting_for_timezone)
async def manual_timezone(
    message: Message,
    state: FSMContext,
    user: User,
    lang: str,
) -> None:
    """Ручной ввод имени часового пояса (IANA)."""
    raw = (message.text or "").strip()
    if not is_valid_timezone(raw):
        await message.answer(t("errors.invalid_timezone", lang))
        return
    async with get_session() as session:
        users = UserRepository(session)
        await users.update_settings(user.id, timezone=raw)
    await state.clear()
    await message.answer(t("commands.settings.tz_saved", lang, timezone=raw))


@router.message(SettingsStates.waiting_for_notify_days)
async def manual_notify_days(
    message: Message,
    state: FSMContext,
    user: User,
    lang: str,
) -> None:
    """Ручной ввод списка дней напоминаний."""
    raw = message.text or ""
    days = _parse_notify_days(raw)
    if days is None:
        await message.answer(t("errors.invalid_notify_days", lang))
        return
    async with get_session() as session:
        users = UserRepository(session)
        await users.update_settings(user.id, notify_days=days)
    await state.clear()
    await message.answer(
        t("commands.settings.days_saved", lang, notify_days=_format_notify_days(days))
    )


# ---------------------------------------------------------------------------
# Хелперы
# ---------------------------------------------------------------------------


def _parse_notify_days(raw: str) -> list[int] | None:
    """Парсит строку ``"60 30 14 7 3 1"`` (или с запятыми) в список int.

    Возвращает ``None`` при невалидном вводе. Сортируем по убыванию: так
    напоминания идут от «далёкого» к «близкому», как принято в спеке.
    """
    if not raw or not raw.strip():
        return None
    parts = [p for p in _NOTIFY_DAYS_SPLIT_RE.split(raw.strip()) if p]
    if not parts or len(parts) > _MAX_NOTIFY_DAYS_COUNT:
        return None
    days: list[int] = []
    for part in parts:
        if not part.isdigit():
            return None
        value = int(part)
        if value < 1 or value > _MAX_NOTIFY_DAY_VALUE:
            return None
        days.append(value)
    # Уникальные значения, отсортированные по убыванию.
    return sorted(set(days), reverse=True)


async def _edit(
    query: CallbackQuery,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> None:
    """Безопасный edit_message_text: пропускает inaccessible-сообщения.

    aiogram 3.x ``CallbackQuery.message`` может быть ``InaccessibleMessage``;
    у него нет ``.edit_text``. В этом редком случае молча игнорируем — UX
    не критичный (можно было бы упасть с сообщением, но это лишний шум).
    """
    if not isinstance(query.message, Message):
        return
    await query.message.edit_text(text, reply_markup=reply_markup)
