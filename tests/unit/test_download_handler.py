"""Тесты ``src.bot.handlers.download`` — FSM-сценарий ``/download``.

Все внешние зависимости (БД, Redis, ARQ, Bot.download) замоксены. Smoke-проверки
основных переходов и поведения при ошибках.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.types import Message

from src.bot.handlers import download as download_handler
from src.bot.states import DownloadStates
from src.config.limits import Limits


def _message_mock() -> MagicMock:
    """Mock с ``spec=Message`` и явно асинхронным ``answer``.

    Без явной подмены ``answer`` AsyncMock(spec=Message) делает его
    sync-методом (по сигнатуре в pydantic-модели) и ``await`` падает.
    """
    msg = MagicMock(spec=Message)
    msg.answer = AsyncMock()
    return msg


def _async_cm(value: object) -> MagicMock:
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=value)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


def _user(*, telegram_id: int = 999) -> SimpleNamespace:
    return SimpleNamespace(id=1, telegram_id=telegram_id, language="ru")


def _state() -> AsyncMock:
    state = AsyncMock()
    state.get_state.return_value = None
    return state


# ---------------------------------------------------------------------------
# /download — вход в FSM
# ---------------------------------------------------------------------------


class TestCmdDownload:
    async def test_enters_waiting_for_file_state(self) -> None:
        message = AsyncMock()
        state = _state()
        redis = AsyncMock()
        redis.get.return_value = None  # счётчик пуст
        limits = Limits()

        await download_handler.cmd_download(
            message=message,
            state=state,
            user=_user(),
            lang="ru",
            redis=redis,
            limits=limits,
        )

        state.set_state.assert_called_once_with(DownloadStates.waiting_for_file)
        message.answer.assert_called_once()

    async def test_rate_limit_blocks_entry(self) -> None:
        message = AsyncMock()
        state = _state()
        redis = AsyncMock()
        redis.get.return_value = "99"  # больше лимита
        limits = Limits(max_downloads_per_day=5)

        await download_handler.cmd_download(
            message=message,
            state=state,
            user=_user(),
            lang="ru",
            redis=redis,
            limits=limits,
        )

        state.set_state.assert_not_called()
        message.answer.assert_called_once()


# ---------------------------------------------------------------------------
# on_document — приём файла
# ---------------------------------------------------------------------------


class TestOnDocument:
    async def test_too_large_file(self) -> None:
        message = AsyncMock()
        message.document = SimpleNamespace(file_id="abc", file_size=10 * 1024 * 1024)
        state = _state()
        bot = AsyncMock()
        limits = Limits()

        await download_handler.on_document(
            message=message,
            state=state,
            user=_user(),
            lang="ru",
            bot=bot,
            limits=limits,
        )

        # Ответ — сообщение «too large», смены state нет.
        message.answer.assert_called_once()
        state.set_state.assert_not_called()

    async def test_parse_failed_when_empty_file(self) -> None:
        message = AsyncMock()
        message.document = SimpleNamespace(file_id="abc", file_size=10)
        state = _state()
        bot = AsyncMock()
        limits = Limits()

        with patch.object(download_handler, "_download_document", AsyncMock(return_value=None)):
            await download_handler.on_document(
                message=message,
                state=state,
                user=_user(),
                lang="ru",
                bot=bot,
                limits=limits,
            )

        message.answer.assert_called_once()
        # state не меняется — остаёмся в waiting_for_file
        state.set_state.assert_not_called()

    async def test_valid_file_shows_preview_and_advances_state(self) -> None:
        message = AsyncMock()
        message.document = SimpleNamespace(file_id="abc", file_size=10)
        state = _state()
        bot = AsyncMock()
        limits = Limits()

        content = b"example.com\nexample.org\n"

        with (
            patch.object(download_handler, "_download_document", AsyncMock(return_value=content)),
            patch.object(download_handler, "get_session") as gs,
            patch.object(download_handler, "DomainRepository") as dr_cls,
        ):
            gs.return_value = _async_cm(MagicMock())
            dr_cls.return_value.bulk_existing_for_user = AsyncMock(return_value=set())
            await download_handler.on_document(
                message=message,
                state=state,
                user=_user(),
                lang="ru",
                bot=bot,
                limits=limits,
            )

        state.set_state.assert_called_with(DownloadStates.confirming_import)
        state.update_data.assert_called_once()
        # update_data вызван с new_domains
        assert "new_domains" in state.update_data.call_args.kwargs


# ---------------------------------------------------------------------------
# on_confirm_add — подтверждение
# ---------------------------------------------------------------------------


class TestOnConfirmAdd:
    async def test_empty_payload_short_circuits(self) -> None:
        query = AsyncMock()
        query.message = _message_mock()
        state = AsyncMock()
        state.get_data.return_value = {"new_domains": []}
        arq_redis = AsyncMock()
        redis = AsyncMock()

        await download_handler.on_confirm_add(
            query=query,
            state=state,
            user=_user(),
            lang="ru",
            arq_redis=arq_redis,
            redis=redis,
            limits=Limits(),
        )

        state.clear.assert_called_once()
        query.message.answer.assert_called_once()

    async def test_full_path_inserts_and_increments_counter(self) -> None:
        query = AsyncMock()
        query.message = _message_mock()
        state = AsyncMock()
        state.get_data.return_value = {"new_domains": ["example.com", "example.org"]}
        arq_redis = AsyncMock()
        redis = AsyncMock()
        redis.incr.return_value = 1
        limits = Limits()

        with (
            patch.object(download_handler, "get_session") as gs,
            patch.object(download_handler, "DomainRepository") as dr_cls,
            patch.object(download_handler, "WhoisCacheRepository") as wr_cls,
            patch.object(
                download_handler,
                "_enqueue_checks_with_delay",
                AsyncMock(return_value=None),
            ) as enqueue_mock,
        ):
            gs.return_value = _async_cm(MagicMock())
            dr_cls.return_value.count_by_user = AsyncMock(return_value=0)
            dr_cls.return_value.bulk_add = AsyncMock(return_value=2)
            wr_cls.return_value.bulk_ensure = AsyncMock(return_value=["example.com", "example.org"])

            await download_handler.on_confirm_add(
                query=query,
                state=state,
                user=_user(),
                lang="ru",
                arq_redis=arq_redis,
                redis=redis,
                limits=limits,
            )

        state.clear.assert_called_once()
        # Дневной счётчик инкрементнут
        redis.incr.assert_called_once()
        # Сообщение об успехе
        query.message.answer.assert_called_once()
        # Постановка проверок в очередь
        enqueue_mock.assert_called_once()

    async def test_limit_exceeded_message(self) -> None:
        query = AsyncMock()
        query.message = _message_mock()
        state = AsyncMock()
        state.get_data.return_value = {"new_domains": ["example.com", "example.org", "example.net"]}
        arq_redis = AsyncMock()
        redis = AsyncMock()
        redis.incr.return_value = 1
        limits = Limits(max_domains_per_user=2)

        with (
            patch.object(download_handler, "get_session") as gs,
            patch.object(download_handler, "DomainRepository") as dr_cls,
            patch.object(download_handler, "WhoisCacheRepository") as wr_cls,
            patch.object(
                download_handler,
                "_enqueue_checks_with_delay",
                AsyncMock(return_value=None),
            ),
        ):
            gs.return_value = _async_cm(MagicMock())
            # current=0 → free_slots=2, добавится 2 из 3
            dr_cls.return_value.count_by_user = AsyncMock(return_value=0)
            dr_cls.return_value.bulk_add = AsyncMock(return_value=2)
            wr_cls.return_value.bulk_ensure = AsyncMock(return_value=["example.com", "example.org"])

            await download_handler.on_confirm_add(
                query=query,
                state=state,
                user=_user(),
                lang="ru",
                arq_redis=arq_redis,
                redis=redis,
                limits=limits,
            )

        # Сообщение должно содержать «limit_exceeded»-вариант (просто проверяем,
        # что вызвалось — конкретный текст из локали).
        query.message.answer.assert_called_once()


# ---------------------------------------------------------------------------
# Отмена
# ---------------------------------------------------------------------------


class TestOnCancel:
    async def test_cancel_clears_state(self) -> None:
        query = AsyncMock()
        query.message = _message_mock()
        state = AsyncMock()

        await download_handler.on_cancel(query=query, state=state, lang="ru")

        state.clear.assert_called_once()
        query.answer.assert_called_once()
        query.message.answer.assert_called_once()


# ---------------------------------------------------------------------------
# Не-документ в FSM
# ---------------------------------------------------------------------------


class TestOnNotDocument:
    async def test_replies_with_hint(self) -> None:
        message = AsyncMock()
        await download_handler.on_not_document(message=message, lang="ru")
        message.answer.assert_called_once()


@pytest.mark.parametrize(
    "raw, expected_count",
    [
        ("99", 0),  # больше лимита — будет True
        ("0", 1),  # ок
        ("not a number", 1),  # сломанное значение трактуется как 0
        (None, 1),  # ключа нет
    ],
)
async def test_is_rate_limited(raw: str | None, expected_count: int) -> None:
    """Корректно интерпретирует разные значения счётчика в Redis."""
    redis = AsyncMock()
    redis.get.return_value = raw
    limits = Limits(max_downloads_per_day=5)
    is_blocked = await download_handler._is_rate_limited(redis, 1, limits)
    if raw == "99":
        assert is_blocked is True
    else:
        assert is_blocked is False
    # Для статической проверки используем expected_count, чтобы не плодить веток.
    assert expected_count in (0, 1)
