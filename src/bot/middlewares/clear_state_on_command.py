"""Middleware: сбрасывает FSM-state ``AwaitingDomainArg.waiting`` если
пользователь шлёт любую команду посреди FSM-flow (ADR 033).

Без этого middleware ``/list`` (или любая другая команда) в state'е
``AwaitingDomainArg.waiting`` ушла бы в FSM-text-handler как «не похоже
на домен» — пользователь застрял бы.

Состояния других FSM (``ListSearchStates``, ``NotifyDaysStates``,
``NotifySslDaysStates``, ``DownloadStates``, ``SettingsStates``) этот
middleware НЕ трогает — у них собственная логика обработки команд
(``/cancel``, ``/default``, etc.) и собственные ожидания.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, TelegramObject

from src.bot.states import AwaitingDomainArg


class ClearAwaitingArgOnCommand(BaseMiddleware):
    """Очищает только ``AwaitingDomainArg.waiting``, если пришла команда."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if isinstance(event, Message):
            text = event.text or ""
            if text.startswith("/"):
                state = data.get("state")
                if isinstance(state, FSMContext):
                    current = await state.get_state()
                    if current == AwaitingDomainArg.waiting.state:
                        await state.clear()
        return await handler(event, data)
