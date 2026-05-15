"""Middleware языка пользователя.

Кладёт в ``data["lang"]``:

- язык из ``User.language`` (если пользователь уже в БД)
- иначе fallback по ``language_code`` из Telegram-апдейта (ADR 014)

Ставится ПОСЛЕ ``UserRegisterMiddleware``: к моменту вызова ``user`` уже
в ``data``. Fallback на ``language_code`` нужен для апдейтов, где
``user`` не появился (channel post и т. п.) — там нам нужен хоть какой-то
язык для интерфейсных строк.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from src.db.models import User
from src.locales import DEFAULT_LANG

_RU_LANG_CODES = frozenset({"ru", "uk", "be", "kk"})


def _resolve_language(tg_lang: str | None) -> str:
    if tg_lang is None:
        return DEFAULT_LANG
    code = tg_lang.lower().split("-", 1)[0]
    return "ru" if code in _RU_LANG_CODES else "en"


class LocaleMiddleware(BaseMiddleware):
    """Прокидывает язык пользователя в ``data["lang"]``."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("user")
        if isinstance(user, User):
            data["lang"] = user.language
        else:
            tg_lang: str | None = None
            if isinstance(event, Message | CallbackQuery) and event.from_user is not None:
                tg_lang = event.from_user.language_code
            data["lang"] = _resolve_language(tg_lang)
        return await handler(event, data)
