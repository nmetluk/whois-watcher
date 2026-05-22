"""Integration-тесты FSM-flow для команд без аргумента (ADR 033).

Не поднимаем реальный Telegram/PostgreSQL — мокаем шину и БД. Цель:
проверить полный путь от ``/add`` без args до вызова бизнес-логики, и
side-эффекты (state-clear на команду, отсутствие plaintext-доменов в
структурированных INFO-логах).
"""

from __future__ import annotations

import logging
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.fsm.context import FSMContext

from src.bot.handlers import add_remove
from src.bot.handlers import awaiting_arg as awaiting_handler
from src.bot.keyboards import CmdArgCallback
from src.bot.middlewares.clear_state_on_command import ClearAwaitingArgOnCommand
from src.bot.states import AwaitingDomainArg


def _state(initial: dict[str, Any] | None = None) -> MagicMock:
    data = dict(initial or {})

    async def get_data() -> dict[str, Any]:
        return dict(data)

    async def update_data(**kwargs: Any) -> dict[str, Any]:
        data.update(kwargs)
        return dict(data)

    async def set_state(state: Any) -> None:
        data["_state"] = state

    async def get_state() -> Any:
        return data.get("_state")

    async def clear() -> None:
        data.clear()

    # spec=FSMContext важен — middleware фильтрует по isinstance.
    s = MagicMock(spec=FSMContext)
    s.get_data = AsyncMock(side_effect=get_data)
    s.update_data = AsyncMock(side_effect=update_data)
    s.set_state = AsyncMock(side_effect=set_state)
    s.get_state = AsyncMock(side_effect=get_state)
    s.clear = AsyncMock(side_effect=clear)
    s._data = data
    return s


def _user() -> MagicMock:
    user = MagicMock()
    user.id = 99
    user.notify_days = [30, 7, 1]
    return user


class TestEndToEndAddFlow:
    async def test_full_flow_from_prompt_to_business_logic(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """``/add`` без args → prompt → ввод example.com → confirm → ✅ → cmd_add."""
        state = _state()
        lang = "ru"

        # ---- Шаг 1: пустая команда → state установлен, prompt отправлен.
        message1 = AsyncMock()
        cmd1 = MagicMock(args=None)

        await add_remove.cmd_add(
            message=message1,
            command=cmd1,
            user=_user(),
            lang=lang,
            arq_redis=MagicMock(),
            redis=MagicMock(),
            limits=MagicMock(),
            state=state,
        )
        assert await state.get_state() == AwaitingDomainArg.waiting
        assert state._data["cmd"] == "add"
        message1.answer.assert_awaited_once()

        # ---- Шаг 2: пользователь шлёт домен → confirm с кнопкой.
        message2 = AsyncMock()
        message2.text = "example.com"
        await awaiting_handler.on_domain_input(message2, state, lang)
        message2.answer.assert_awaited_once()
        kwargs = message2.answer.await_args.kwargs
        assert kwargs.get("reply_markup") is not None
        token_map = state._data["token_map"]
        token = next(iter(token_map))

        # ---- Шаг 3: «Да» → cmd_add вызван с domain.
        cmd_add_mock = AsyncMock()
        monkeypatch.setattr(add_remove, "cmd_add", cmd_add_mock)

        query = AsyncMock()
        from aiogram.types import Message

        query.message = MagicMock()
        query.message.__class__ = Message
        query.message.edit_text = AsyncMock()
        callback = CmdArgCallback(action="yes", token=token)

        await awaiting_handler.on_confirm(
            query=query,
            callback_data=callback,
            state=state,
            user=_user(),
            lang=lang,
            arq_redis=MagicMock(),
            redis=MagicMock(),
            limits=MagicMock(),
        )

        cmd_add_mock.assert_awaited_once()
        call_kwargs = cmd_add_mock.await_args.kwargs
        assert call_kwargs["command"].args == "example.com"
        assert call_kwargs["command"].command == "add"
        # State очищен — повторный confirm не сработает.
        # Внутри clear() data.clear(); проверяем что cmd отсутствует.
        assert "cmd" not in state._data


class TestClearStateMiddleware:
    async def test_command_clears_awaiting_state(self) -> None:
        """В state AwaitingDomainArg.waiting любая `/cmd` сбрасывает state."""
        from aiogram.types import Message

        state = _state({"_state": AwaitingDomainArg.waiting.state, "cmd": "add"})
        message = MagicMock(spec=Message)
        message.text = "/list"

        mw = ClearAwaitingArgOnCommand()
        next_called: list[bool] = []

        async def next_handler(event: Any, data: dict[str, Any]) -> None:
            next_called.append(True)

        await mw(next_handler, message, {"state": state})

        state.clear.assert_awaited_once()
        assert next_called == [True]

    async def test_non_command_does_not_clear(self) -> None:
        from aiogram.types import Message

        state = _state({"_state": AwaitingDomainArg.waiting.state, "cmd": "add"})
        message = MagicMock(spec=Message)
        message.text = "example.com"

        mw = ClearAwaitingArgOnCommand()

        async def next_handler(event: Any, data: dict[str, Any]) -> None:
            pass

        await mw(next_handler, message, {"state": state})

        state.clear.assert_not_called()

    async def test_other_state_not_cleared(self) -> None:
        """Не наш state (например, DownloadStates) middleware не трогает."""
        from aiogram.types import Message

        state = _state({"_state": "DownloadStates:waiting_for_file"})
        message = MagicMock(spec=Message)
        message.text = "/list"

        mw = ClearAwaitingArgOnCommand()

        async def next_handler(event: Any, data: dict[str, Any]) -> None:
            pass

        await mw(next_handler, message, {"state": state})

        state.clear.assert_not_called()


class TestPrivacy:
    async def test_domain_not_in_info_logs(self, caplog: pytest.LogCaptureFixture) -> None:
        """Введённый домен НЕ попадает в structlog INFO-логи (privacy, см. ADR 025/033).

        Мы не логируем plaintext-доменов из пользовательского ввода через
        ``logger.info``. Это та же гарантия, что для search-query.
        """
        state = _state({"cmd": "add"})
        message = AsyncMock()
        message.text = "secretdomain.example"

        caplog.set_level(logging.INFO, logger="src.bot.handlers.awaiting_arg")
        await awaiting_handler.on_domain_input(message, state, "ru")

        for record in caplog.records:
            assert "secretdomain.example" not in record.getMessage()
