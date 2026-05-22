"""Smoke-тесты сборки бота: создание Dispatcher, регистрация роутеров,
наличие ожидаемых хэндлеров и команд.

Реальный обмен апдейтами с Telegram и БД здесь не воспроизводим — это
будет в e2e-тестах Этапа 4 с docker-compose. Цель этих тестов — поймать
ломающие изменения в композиции хэндлеров/middleware/команд.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

from src.bot.app import create_bot, create_dispatcher
from src.bot.commands import COMMANDS_EN, COMMANDS_RU
from src.bot.handlers import ROUTERS
from src.bot.middlewares import (
    ClearAwaitingArgOnCommand,
    LocaleMiddleware,
    RateLimitMiddleware,
    UserRegisterMiddleware,
)
from src.config.limits import get_limits
from src.config.settings import get_settings


@pytest.fixture(scope="session")
def _session_redis() -> AsyncMock:
    """Session-scoped Redis-мок: ``create_dispatcher`` инжектит его в Dispatcher.

    Нужен session-scope, потому что роутеры aiogram — singletons и могут быть
    включены ровно в один Dispatcher. Поэтому Dispatcher тоже один на сессию.
    """
    from redis.asyncio import Redis

    return AsyncMock(spec=Redis)


@pytest.fixture(scope="session")
def dispatcher(_session_redis: AsyncMock) -> Dispatcher:
    return create_dispatcher(
        settings=get_settings(),
        limits=get_limits(),
        redis=_session_redis,
    )


class TestBotFactory:
    def test_create_bot_default_parse_mode_is_html(self) -> None:
        bot = create_bot("123456:fake-token")
        assert isinstance(bot, Bot)
        assert isinstance(bot.default, DefaultBotProperties)
        assert bot.default.parse_mode == ParseMode.HTML


class TestDispatcherComposition:
    def test_all_routers_included(self, dispatcher: Dispatcher) -> None:
        included = {r.name for r in dispatcher.sub_routers}
        expected = {r.name for r in ROUTERS}
        assert expected <= included

    def test_workflow_data_has_dependencies(
        self, dispatcher: Dispatcher, _session_redis: AsyncMock
    ) -> None:
        # Зависимости проброшены — aiogram сможет инжектировать их в хэндлеры.
        assert dispatcher["settings"] is get_settings()
        assert dispatcher["limits"] is get_limits()
        assert dispatcher["redis"] is _session_redis

    def test_middleware_chain_order(self, dispatcher: Dispatcher) -> None:
        """``dp.message``: user_register → locale → rate_limit → clear_awaiting (ADR 033)."""
        chain = list(dispatcher.message.middleware._middlewares)
        # Проверяем именно типы — экземпляры создаются внутри create_dispatcher.
        types_in_order = [type(m) for m in chain]
        assert types_in_order == [
            UserRegisterMiddleware,
            LocaleMiddleware,
            RateLimitMiddleware,
            ClearAwaitingArgOnCommand,
        ]


class TestCommandsList:
    def test_ru_en_commands_have_same_keys(self) -> None:
        ru_keys = {c.command for c in COMMANDS_RU}
        en_keys = {c.command for c in COMMANDS_EN}
        assert ru_keys == en_keys

    def test_no_internal_commands_in_menu(self) -> None:
        # cancel и delete_me_confirm НЕ выводим в меню BotFather (ADR 017).
        for commands in (COMMANDS_RU, COMMANDS_EN):
            names = {c.command for c in commands}
            assert "cancel" not in names
            assert "delete_me_confirm" not in names

    def test_expected_commands_present(self) -> None:
        names = {c.command for c in COMMANDS_RU}
        for expected in (
            "start",
            "whois",
            "add",
            "rmv",
            "list",
            "csv",
            "download",
            "notify",
            "unnotify",
            "settings",
            "stats",
            "check",
            "help",
            "delete_me",
        ):
            assert expected in names

    def test_descriptions_non_empty(self) -> None:
        for cmd in (*COMMANDS_RU, *COMMANDS_EN):
            assert isinstance(cmd, BotCommand)
            assert cmd.description.strip()
