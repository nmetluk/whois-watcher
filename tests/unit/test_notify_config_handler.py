"""Тесты UI-конфигуратора уведомлений (Этап 11, ADR 029)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from src.bot.handlers.notify_config import _parse_days, on_subdomain_interval_input
from src.config.limits import Limits
from src.db.models import User


class TestParseDays:
    def test_valid_csv(self) -> None:
        assert _parse_days("60,30,7,1") == [60, 30, 7, 1]

    def test_with_spaces_and_semicolons(self) -> None:
        assert _parse_days(" 30 ; 7,1 ") == [30, 7, 1]

    def test_dedup_and_sort_desc(self) -> None:
        assert _parse_days("7,30,7,1,30") == [30, 7, 1]

    def test_single_value(self) -> None:
        assert _parse_days("1") == [1]

    def test_empty_returns_none(self) -> None:
        assert _parse_days("") is None
        assert _parse_days(",,") is None

    def test_non_int_returns_none(self) -> None:
        assert _parse_days("30,abc,7") is None

    def test_out_of_range_returns_none(self) -> None:
        assert _parse_days("0,7,30") is None
        assert _parse_days("366") is None
        assert _parse_days("-1") is None

    def test_too_many_values_returns_none(self) -> None:
        # 11 значений — больше предельных 10
        assert _parse_days(",".join(str(i) for i in range(1, 12))) is None

    def test_exactly_10_values_accepted(self) -> None:
        assert _parse_days(",".join(str(i) for i in range(1, 11))) == list(range(10, 0, -1))


# ---------------------------------------------------------------------------
# FSM interval cap tests (TASK-0037)
# ---------------------------------------------------------------------------


def _make_message(text: str | None = None) -> Message:
    """Мок Message с .text и .answer (AsyncMock)."""
    msg = MagicMock(spec=Message)
    msg.text = text
    msg.answer = AsyncMock()
    return msg


def _make_user() -> User:
    """Мок User со spec."""
    u = MagicMock(spec=User)
    u.id = 42
    return u


def _make_state(data: dict | None = None) -> FSMContext:
    """Мок FSMContext со spec и async-методами."""
    st = MagicMock(spec=FSMContext)
    st.get_data = AsyncMock(return_value=data or {"domain": "example.com"})
    st.clear = AsyncMock()
    return st


class TestOnSubdomainIntervalInputCap:
    """Проверка верхнего капа интервала FSM (TASK-0037, ADR 038).

    Инвариант: 1 и 365 → persist с override; 0 и 366 → invalid, persist не вызван.
    Моки со spec/autospec, per CLAUDE.md anti-drift.
    """

    async def test_interval_1_accepted_and_persisted(self) -> None:
        """Граница 1 (min) → override записан, FSM очищён, saved-ответ."""
        msg = _make_message("1")
        user = _make_user()
        state = _make_state()
        mock_limits = MagicMock(spec=Limits)
        mock_limits.max_subdomain_check_interval_days = 365

        with (
            patch("src.bot.handlers.notify_config.get_limits", return_value=mock_limits),
            patch(
                "src.bot.handlers.notify_config._persist", new_callable=AsyncMock
            ) as mock_persist,
            patch(
                "src.bot.handlers.notify_config._send_refreshed_config", new_callable=AsyncMock
            ) as mock_refresh,
        ):
            await on_subdomain_interval_input(msg, user, "ru", state)

            mock_persist.assert_awaited_once_with(
                42, "example.com", subdomain_check_interval_override=1
            )
            state.clear.assert_awaited_once()
            mock_refresh.assert_awaited_once()
            # Успешный путь: ответ с saved (refresh замокан, его answer не выполняется)
            msg.answer.assert_awaited_once()

    async def test_interval_365_accepted_and_persisted(self) -> None:
        """Граница 365 (max) → override записан."""
        msg = _make_message("365")
        user = _make_user()
        state = _make_state()
        mock_limits = MagicMock(spec=Limits)
        mock_limits.max_subdomain_check_interval_days = 365

        with (
            patch("src.bot.handlers.notify_config.get_limits", return_value=mock_limits),
            patch(
                "src.bot.handlers.notify_config._persist", new_callable=AsyncMock
            ) as mock_persist,
            patch("src.bot.handlers.notify_config._send_refreshed_config", new_callable=AsyncMock),
        ):
            await on_subdomain_interval_input(msg, user, "ru", state)

            mock_persist.assert_awaited_once_with(
                42, "example.com", subdomain_check_interval_override=365
            )
            state.clear.assert_awaited_once()

    async def test_interval_366_rejected_no_persist(self) -> None:
        """366 > max → invalid, _persist НЕ вызван, state не очищён."""
        msg = _make_message("366")
        user = _make_user()
        state = _make_state()
        mock_limits = MagicMock(spec=Limits)
        mock_limits.max_subdomain_check_interval_days = 365

        with (
            patch("src.bot.handlers.notify_config.get_limits", return_value=mock_limits),
            patch(
                "src.bot.handlers.notify_config._persist", new_callable=AsyncMock
            ) as mock_persist,
        ):
            await on_subdomain_interval_input(msg, user, "ru", state)

            mock_persist.assert_not_called()
            state.clear.assert_not_called()
            msg.answer.assert_awaited_once()
            text = msg.answer.await_args.args[0]
            assert "1" in text and "365" in text  # сообщение об ошибке с диапазоном

    async def test_interval_0_rejected_no_persist(self) -> None:
        """0 < min → invalid, _persist НЕ вызван."""
        msg = _make_message("0")
        user = _make_user()
        state = _make_state()
        mock_limits = MagicMock(spec=Limits)
        mock_limits.max_subdomain_check_interval_days = 365

        with (
            patch("src.bot.handlers.notify_config.get_limits", return_value=mock_limits),
            patch(
                "src.bot.handlers.notify_config._persist", new_callable=AsyncMock
            ) as mock_persist,
        ):
            await on_subdomain_interval_input(msg, user, "ru", state)

            mock_persist.assert_not_called()
            msg.answer.assert_awaited_once()
            text = msg.answer.await_args.args[0]
            assert "Неверный" in text or "Invalid" in text  # ru/en tolerant
