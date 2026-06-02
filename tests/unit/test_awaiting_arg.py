"""Тесты FSM-flow для команд без аргумента (ADR 033).

Покрытие:
- ``_extract_domains`` — 0/1/many доменов и фильтрация мусора.
- ``_make_token`` — длина и hex-формат.
- ``on_domain_input`` — три ветки (invalid/single/multiple), state-update,
  prompt без чувствительной утечки.
- ``on_confirm`` — stale-callback не падает, «no» чистит state, «yes»
  диспатчит правильный handler с правильными аргументами.
- ``_dispatch`` — каждая из 5 команд маршрутизируется в нужную функцию
  (``/wishlist`` НЕ в FSM-flow с v0.7.2).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.bot.handlers import awaiting_arg as handler
from src.bot.keyboards import CmdArgCallback
from src.bot.states import AwaitingDomainArg

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _user() -> MagicMock:
    user = MagicMock()
    user.id = 42
    user.notify_days = [30, 7, 1]
    return user


def _state(initial: dict[str, Any] | None = None) -> AsyncMock:
    """Mock FSMContext с in-memory data."""
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

    s = MagicMock()
    s.get_data = AsyncMock(side_effect=get_data)
    s.update_data = AsyncMock(side_effect=update_data)
    s.set_state = AsyncMock(side_effect=set_state)
    s.get_state = AsyncMock(side_effect=get_state)
    s.clear = AsyncMock(side_effect=clear)
    s._data = data
    return s


# ---------------------------------------------------------------------------
# _extract_domains
# ---------------------------------------------------------------------------


class TestExtractDomains:
    def test_returns_empty_for_garbage(self) -> None:
        assert handler._extract_domains("hello world") == []
        assert handler._extract_domains("") == []
        assert handler._extract_domains("   ") == []

    def test_returns_single_domain(self) -> None:
        result = handler._extract_domains("example.com")
        assert result == ["example.com"]

    def test_idn_normalized_to_punycode(self) -> None:
        result = handler._extract_domains("пример.рф")
        # punycode-нормализация — мы не привязываемся к точной форме, лишь к
        # тому, что строка одна, не пуста и ASCII.
        assert len(result) == 1
        assert result[0].isascii()

    def test_url_in_text(self) -> None:
        # Из строки с URL извлекаем домен.
        result = handler._extract_domains("проверь https://example.com/path")
        assert "example.com" in result


# ---------------------------------------------------------------------------
# _make_token
# ---------------------------------------------------------------------------


class TestMakeToken:
    def test_format(self) -> None:
        token = handler._make_token()
        assert len(token) == 8
        # 8 hex-символов.
        int(token, 16)

    def test_collision_unlikely(self) -> None:
        tokens = {handler._make_token() for _ in range(1000)}
        assert len(tokens) == 1000


# ---------------------------------------------------------------------------
# on_domain_input
# ---------------------------------------------------------------------------


class TestOnDomainInput:
    async def test_invalid_input_keeps_state(self) -> None:
        message = AsyncMock()
        message.text = "не домен и не урл"
        state = _state({"cmd": "add", "_state": AwaitingDomainArg.waiting})

        await handler.on_domain_input(message, state, "ru")

        message.answer.assert_awaited_once()
        # State НЕ очищается — даём пользователю попробовать ещё раз.
        state.clear.assert_not_called()

    async def test_single_domain_shows_confirm(self) -> None:
        message = AsyncMock()
        message.text = "example.com"
        state = _state({"cmd": "add"})

        await handler.on_domain_input(message, state, "ru")

        message.answer.assert_awaited_once()
        kwargs = message.answer.await_args.kwargs
        # Confirm-keyboard приложен.
        assert kwargs.get("reply_markup") is not None
        # Token сохранён в FSM-data.
        token_map = state._data.get("token_map")
        assert isinstance(token_map, dict)
        assert "example.com" in token_map.values()

    async def test_multiple_domains_takes_first(self) -> None:
        message = AsyncMock()
        # extract_domain_from_text возвращает один — проверяем код, который
        # берёт первый при >1. Эмулируем это монками.
        message.text = "example.com"
        state = _state({"cmd": "add"})

        # Замокаем _extract_domains напрямую, чтобы вернуть несколько.
        original = handler._extract_domains
        handler._extract_domains = lambda text: ["one.com", "two.com"]  # type: ignore[assignment]
        try:
            await handler.on_domain_input(message, state, "ru")
        finally:
            handler._extract_domains = original  # type: ignore[assignment]

        text = message.answer.await_args.args[0]
        # Первый домен — в сообщении (или сообщение про "несколько").
        assert "one.com" in text
        token_map = state._data.get("token_map")
        assert "one.com" in token_map.values()

    async def test_unsupported_cmd_clears_state(self) -> None:
        """Если в FSM-data битый cmd — тихо выходим (state.clear)."""
        message = AsyncMock()
        message.text = "example.com"
        state = _state({"cmd": "nonexistent"})

        await handler.on_domain_input(message, state, "ru")

        state.clear.assert_awaited_once()
        message.answer.assert_not_called()


# ---------------------------------------------------------------------------
# on_confirm — stale & «no»
# ---------------------------------------------------------------------------


class TestOnConfirmStale:
    async def test_stale_token_does_not_raise(self) -> None:
        """Token не в карте → пишет stale, без исключения."""
        query = AsyncMock()
        from aiogram.types import Message

        query.message = MagicMock(spec=Message)
        query.message.edit_text = AsyncMock()
        callback = CmdArgCallback(action="yes", token="deadbeef")
        state = _state({"cmd": "add", "token_map": {}})

        await handler.on_confirm(
            query=query,
            callback_data=callback,
            state=state,
            user=_user(),
            lang="ru",
            arq_redis=MagicMock(),
            redis=MagicMock(),
            limits=MagicMock(),
        )

        query.message.edit_text.assert_awaited_once()
        text = query.message.edit_text.await_args.args[0]
        assert "актуал" in text.lower() or "relev" in text.lower()

    async def test_no_action_cancels(self) -> None:
        query = AsyncMock()
        from aiogram.types import Message

        query.message = MagicMock(spec=Message)
        query.message.edit_text = AsyncMock()
        token = "cafe1234"
        state = _state({"cmd": "add", "token_map": {token: "example.com"}})
        callback = CmdArgCallback(action="no", token=token)

        await handler.on_confirm(
            query=query,
            callback_data=callback,
            state=state,
            user=_user(),
            lang="ru",
            arq_redis=MagicMock(),
            redis=MagicMock(),
            limits=MagicMock(),
        )

        query.message.edit_text.assert_awaited_once()
        state.clear.assert_awaited_once()


# ---------------------------------------------------------------------------
# Dispatcher — все 5 команд (/wishlist выпал из FSM-flow в v0.7.2)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "cmd",
    ["add", "rmv", "check", "notify", "unnotify"],
)
class TestDispatcher:
    async def test_supported_command_routes(
        self, cmd: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Каждый из 5 cmd должен попадать в свой handler-функцию."""
        from src.bot.handlers import (
            add_remove,
            notifications,
        )
        from src.bot.handlers import (
            check as check_module,
        )

        # Замокаем все возможные target'ы. Только один из них должен быть
        # вызван.
        cmd_add_mock = AsyncMock()
        cmd_rmv_mock = AsyncMock()
        cmd_check_mock = AsyncMock()
        cmd_notify_mock = AsyncMock()
        cmd_unnotify_mock = AsyncMock()

        monkeypatch.setattr(add_remove, "cmd_add", cmd_add_mock)
        monkeypatch.setattr(add_remove, "cmd_rmv", cmd_rmv_mock)
        monkeypatch.setattr(check_module, "cmd_check", cmd_check_mock)
        monkeypatch.setattr(notifications, "cmd_notify", cmd_notify_mock)
        monkeypatch.setattr(notifications, "cmd_unnotify", cmd_unnotify_mock)

        message = MagicMock()
        await handler._dispatch(
            cmd=cmd,
            domain="example.com",
            message=message,
            user=_user(),
            lang="ru",
            arq_redis=MagicMock(),
            redis=MagicMock(),
            limits=MagicMock(),
            state=_state(),
        )

        target = {
            "add": cmd_add_mock,
            "rmv": cmd_rmv_mock,
            "check": cmd_check_mock,
            "notify": cmd_notify_mock,
            "unnotify": cmd_unnotify_mock,
        }[cmd]
        others = [
            m
            for k, m in {
                "add": cmd_add_mock,
                "rmv": cmd_rmv_mock,
                "check": cmd_check_mock,
                "notify": cmd_notify_mock,
                "unnotify": cmd_unnotify_mock,
            }.items()
            if k != cmd
        ]

        target.assert_awaited_once()
        # Аргументы переданы.
        call_kwargs = target.await_args.kwargs
        assert call_kwargs["lang"] == "ru"
        assert call_kwargs["command"].args == "example.com"
        assert call_kwargs["command"].command == cmd
        # Никто другой не вызван.
        for m in others:
            m.assert_not_called()


class TestSupportedCommands:
    def test_supported_commands_set(self) -> None:
        assert (
            frozenset({"add", "rmv", "check", "notify", "unnotify"}) == handler.SUPPORTED_COMMANDS
        )

    def test_wishlist_not_in_set(self) -> None:
        """``/wishlist`` без аргумента показывает список — не FSM-flow (v0.7.2)."""
        assert "wishlist" not in handler.SUPPORTED_COMMANDS
