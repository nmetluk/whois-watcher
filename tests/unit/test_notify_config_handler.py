"""Тесты UI-конфигуратора уведомлений (Этап 11, ADR 029)."""

from __future__ import annotations

from src.bot.handlers.notify_config import _parse_days


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
