"""Тесты парсера дней напоминаний в ``src.bot.handlers.settings``.

``_parse_notify_days`` — единственная содержательная функция этого хэндлера,
которую можно изолированно проверить без mocking aiogram/redis/DB.
"""

from __future__ import annotations

import pytest

from src.bot.handlers.settings import _parse_notify_days


class TestParseNotifyDays:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("30 7 1", [30, 7, 1]),
            ("30,7,1", [30, 7, 1]),
            ("30, 7, 1", [30, 7, 1]),
            ("  60   30 14 7 3 1 ", [60, 30, 14, 7, 3, 1]),
            ("1 30 7", [30, 7, 1]),  # сортируется по убыванию
            ("30 30 7 7 1", [30, 7, 1]),  # дубликаты схлопываются
        ],
    )
    def test_valid(self, raw: str, expected: list[int]) -> None:
        assert _parse_notify_days(raw) == expected

    @pytest.mark.parametrize(
        "raw",
        [
            "",
            "   ",
            "abc",
            "30 abc 7",
            "0 7 1",  # 0 запрещён
            "-1 7",  # отрицательные запрещены
            "1000",  # > 365 — запрет
            "30 " * 11,  # слишком много значений
        ],
    )
    def test_invalid(self, raw: str) -> None:
        assert _parse_notify_days(raw) is None
