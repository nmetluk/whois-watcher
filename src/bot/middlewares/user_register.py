"""Middleware регистрации/обновления пользователя.

Для каждого апдейта:

- ищет пользователя по ``telegram_id``
- если нет — создаёт с дефолтами (см. ADR 013, 014)
- если есть — обновляет ``last_active_at``
- кладёт ``User`` в ``data["user"]`` для следующих middleware/handlers
- если ``is_blocked=True`` — отвечает ``errors.blocked`` и прерывает цепочку

Использование ``language_code`` из апдейта: ``ru/uk/be/kk → ru``, иначе ``en``
(ADR 014).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject
from aiogram.types import User as TgUser

from src.config.settings import Settings
from src.db.models import User
from src.db.repositories import UserRepository
from src.db.session import get_session
from src.locales import t
from src.observability import bind_log_context, clear_log_context

# Языковые коды из Telegram, которые мы считаем русскоязычной аудиторией.
_RU_LANG_CODES = frozenset({"ru", "uk", "be", "kk"})


def _resolve_language(tg_lang: str | None, default: str) -> str:
    """Конвертирует ``language_code`` из Telegram в ``"ru"|"en"`` (ADR 014)."""
    if tg_lang is None:
        return default
    code = tg_lang.lower().split("-", 1)[0]
    if code in _RU_LANG_CODES:
        return "ru"
    return "en"


def _extract_tg_user(event: TelegramObject) -> TgUser | None:
    """Достаёт ``from_user`` из ``Message`` / ``CallbackQuery``.

    Возвращает ``None``, если апдейт не от пользователя (channel post и т. п.).
    """
    if isinstance(event, Message | CallbackQuery):
        return event.from_user
    return None


def _extract_update_id(event: TelegramObject) -> int | None:
    """Возвращает ``message_id`` / ``callback_query.id`` для логов.

    Это не Telegram update_id (его middleware не видит напрямую), но
    идентификатор конкретного события — этого достаточно, чтобы связать
    логи одного запроса в трассе.
    """
    if isinstance(event, Message):
        return event.message_id
    if isinstance(event, CallbackQuery):
        try:
            return int(event.id)
        except (TypeError, ValueError):
            return None
    return None


class UserRegisterMiddleware(BaseMiddleware):
    """Регистрирует пользователя и кладёт его в ``data["user"]``.

    ``settings`` инжектируется при создании — чтобы дефолты можно было
    переопределить через env (см. ``Settings.default_*``).
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user = _extract_tg_user(event)
        if tg_user is None:
            # Системный апдейт без пользователя — пропускаем дальше как есть.
            return await handler(event, data)

        # Привязываем поля в structlog-контекст: все логи внутри обработки
        # этого апдейта получат user_id/telegram_id. Чистим в finally, иначе
        # контекст «протечёт» в соседние корутины через ContextVar.
        bind_log_context(telegram_id=tg_user.id, update_id=_extract_update_id(event))
        try:
            async with get_session() as session:
                users = UserRepository(session)
                user = await users.get_by_telegram_id(tg_user.id)
                if user is None:
                    user = await users.create(
                        telegram_id=tg_user.id,
                        username=tg_user.username,
                        language=_resolve_language(
                            tg_user.language_code, self._settings.default_language
                        ),
                        timezone=self._settings.default_timezone,
                        notify_at_hour=self._settings.default_notify_hour,
                    )
                else:
                    await users.touch_last_active(user.id)

            bind_log_context(user_id=user.id)

            if user.is_blocked:
                await _reply_blocked(event, user)
                return None

            data["user"] = user
            return await handler(event, data)
        finally:
            clear_log_context()


async def _reply_blocked(event: TelegramObject, user: User) -> None:
    """Отвечает заблокированному пользователю и завершает обработку."""
    text = t("errors.blocked", user.language)
    if isinstance(event, Message):
        await event.answer(text)
    elif isinstance(event, CallbackQuery):
        await event.answer(text, show_alert=True)
