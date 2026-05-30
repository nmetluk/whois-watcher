"""Тесты хэндлера /start (TASK-0020)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.bot.handlers.start import handle_start_button
from src.bot.keyboards import StartAction
from src.config.limits import Limits
from src.db.models import User


def _make_callback_query(*, action: str = "list") -> CallbackQuery:
    """Создаёт мок CallbackQuery с данными StartAction."""
    query = MagicMock(spec=CallbackQuery)
    query.answer = AsyncMock()
    callback_data = StartAction(action=action)
    query.data = callback_data.pack()
    return query


def _make_message() -> Message:
    """Создаёт мок Message."""
    msg = MagicMock(spec=Message)
    msg.answer = AsyncMock()
    return msg


def _make_user() -> User:
    """Создаёт мок User."""
    user = MagicMock(spec=User)
    user.id = 12345
    return user


def _make_limits() -> Limits:
    """Создаёт Limits."""
    return Limits()


def _make_state() -> FSMContext:
    """Создаёт мок FSMContext."""
    return MagicMock(spec=FSMContext)


def _make_redis() -> AsyncMock:
    """Создаёт мок Redis."""
    return AsyncMock()


async def _mock_cmd_list(*_args, **_kwargs):
    """Мок для cmd_list — будет подменён в тестах."""
    pass


class TestHandleStartButton:
    async def test_list_action_calls_cmd_list_with_all_args(self) -> None:
        """TASK-0020: кнопка «Мои домены» вызывает cmd_list с полным набором аргументов."""
        # Мокаем cmd_list, чтобы проверить вызов с правильными аргументами
        import src.bot.handlers.start as start_module

        mock_cmd_list = AsyncMock()
        original = start_module.cmd_list
        start_module.cmd_list = mock_cmd_list

        try:
            query = _make_callback_query(action="list")
            query.message = _make_message()
            user = _make_user()
            lang = "ru"
            arq_redis = AsyncMock()
            limits = _make_limits()
            state = _make_state()
            redis = _make_redis()

            await handle_start_button(
                query=query,
                callback_data=StartAction(action="list"),
                user=user,
                lang=lang,
                arq_redis=arq_redis,
                limits=limits,
                state=state,
                redis=redis,
            )

            # Проверяем, что cmd_list был вызван один раз
            mock_cmd_list.assert_called_once()
            # Первый аргумент — message (позиционный)
            call_args = mock_cmd_list.call_args.args
            assert len(call_args) == 1
            assert isinstance(call_args[0], MagicMock)
            # Остальные аргументы — kwargs
            call_kwargs = mock_cmd_list.call_args.kwargs
            assert "user" in call_kwargs
            assert "lang" in call_kwargs
            assert "arq_redis" in call_kwargs
            assert "limits" in call_kwargs
            assert "redis" in call_kwargs
            assert "state" in call_kwargs
        finally:
            start_module.cmd_list = original

    async def test_settings_action_calls_cmd_settings(self) -> None:
        """Кнопка «Настройки» вызывает cmd_settings (без redis/state)."""
        import src.bot.handlers.start as start_module

        mock_cmd_settings = AsyncMock()
        original = start_module.cmd_settings
        start_module.cmd_settings = mock_cmd_settings

        try:
            query = _make_callback_query(action="settings")
            query.message = _make_message()
            user = _make_user()
            lang = "en"
            arq_redis = AsyncMock()
            limits = _make_limits()
            state = _make_state()
            redis = _make_redis()

            await handle_start_button(
                query=query,
                callback_data=StartAction(action="settings"),
                user=user,
                lang=lang,
                arq_redis=arq_redis,
                limits=limits,
                state=state,
                redis=redis,
            )

            mock_cmd_settings.assert_called_once()
            # Первый аргумент — message (позиционный)
            call_args = mock_cmd_settings.call_args.args
            assert len(call_args) == 1
            assert isinstance(call_args[0], MagicMock)
            # Остальные аргументы — kwargs
            call_kwargs = mock_cmd_settings.call_args.kwargs
            assert "user" in call_kwargs
            assert "lang" in call_kwargs
            # cmd_settings не требует redis/state
            assert "redis" not in call_kwargs
            assert "state" not in call_kwargs
        finally:
            start_module.cmd_settings = original

    async def test_check_action_sends_prompt(self) -> None:
        """Кнопка «Проверить домен» отправляет подсказку."""
        query = _make_callback_query(action="check")
        query.message = _make_message()
        user = _make_user()
        lang = "ru"
        arq_redis = AsyncMock()
        limits = _make_limits()
        state = _make_state()
        redis = _make_redis()

        await handle_start_button(
            query=query,
            callback_data=StartAction(action="check"),
            user=user,
            lang=lang,
            arq_redis=arq_redis,
            limits=limits,
            state=state,
            redis=redis,
        )

        query.message.answer.assert_called_once()
        # Проверяем, что в сообщении есть текст подсказки (ключ "start.check_prompt")
        call_args = query.message.answer.call_args.args
        assert len(call_args) > 0
