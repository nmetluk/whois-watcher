"""Тесты ``/notify`` и ``/unnotify`` команд (Этап 5, ADR 015).

Хэндлеры тонкие — основная логика в ``DomainRepository.toggle_notifications``.
Здесь проверяем тонкий слой: парсинг аргументов, ответы и наличие кнопки
"включить обратно" под ``/unnotify``.
"""

from __future__ import annotations

from collections.abc import Iterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.bot.handlers import notifications as handler


def _async_cm(value: object) -> MagicMock:
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=value)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


def _user() -> MagicMock:
    user = MagicMock()
    user.id = 1
    user.notify_days = [30, 7, 1]
    return user


@pytest.fixture
def domain_repo() -> Iterator[MagicMock]:
    with (
        patch.object(handler, "get_session") as gs,
        patch.object(handler, "DomainRepository") as dr_cls,
    ):
        session = MagicMock()
        gs.return_value = _async_cm(session)
        repo = dr_cls.return_value
        yield repo


def _state() -> AsyncMock:
    """FSMContext-мок с поддержкой set_state/update_data/clear/get_state."""
    s = AsyncMock()
    s.get_state = AsyncMock(return_value=None)
    return s


class TestCmdNotify:
    async def test_without_arg_enters_fsm_flow(self, domain_repo: MagicMock) -> None:
        """ADR 033: пустой аргумент → переход в AwaitingDomainArg.waiting."""
        message = AsyncMock()
        cmd = MagicMock(args=None)
        state = _state()

        await handler.cmd_notify(message, cmd, _user(), "ru", state)

        # State выставлен, prompt отправлен.
        state.set_state.assert_awaited_once()
        state.update_data.assert_awaited_once()
        message.answer.assert_awaited_once()
        text = message.answer.await_args.args[0]
        assert "домен" in text.lower()
        # Бизнес-логика не вызывается.
        domain_repo.toggle_notifications.assert_not_called()

    async def test_enables_all_flags(self, domain_repo: MagicMock) -> None:
        domain_repo.toggle_notifications = AsyncMock(return_value=True)
        message = AsyncMock()
        cmd = MagicMock(args="example.ru")

        await handler.cmd_notify(message, cmd, _user(), "ru", _state())

        domain_repo.toggle_notifications.assert_awaited_once_with(1, "example.ru", enabled=True)
        text = message.answer.await_args.args[0]
        assert "включены" in text

    async def test_not_in_list(self, domain_repo: MagicMock) -> None:
        domain_repo.toggle_notifications = AsyncMock(return_value=False)
        message = AsyncMock()
        cmd = MagicMock(args="example.ru")

        await handler.cmd_notify(message, cmd, _user(), "ru", _state())

        text = message.answer.await_args.args[0]
        assert "не отслеживается" in text


class TestCmdUnnotify:
    async def test_disables_all_flags(self, domain_repo: MagicMock) -> None:
        domain_repo.toggle_notifications = AsyncMock(return_value=True)
        message = AsyncMock()
        cmd = MagicMock(args="example.ru")

        await handler.cmd_unnotify(message, cmd, _user(), "ru", _state())

        domain_repo.toggle_notifications.assert_awaited_once_with(1, "example.ru", enabled=False)
        # Кнопка «🔔 Включить обратно» должна быть приложена
        kwargs = message.answer.await_args.kwargs
        assert kwargs.get("reply_markup") is not None
        text = message.answer.await_args.args[0]
        assert "выключены" in text

    async def test_invalid_domain(self, domain_repo: MagicMock) -> None:
        message = AsyncMock()
        cmd = MagicMock(args="!!! not a domain !!!")

        await handler.cmd_unnotify(message, cmd, _user(), "ru", _state())

        domain_repo.toggle_notifications.assert_not_called()
        text = message.answer.await_args.args[0]
        assert "домен" in text.lower()
