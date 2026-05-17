"""Тесты ``src.ssl.scheduler``: adaptive TTL для SSL-проверок."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from src.ssl.scheduler import calculate_next_ssl_check

NOW = datetime(2026, 5, 17, 12, 0, tzinfo=UTC)


class TestCalculateNextSslCheck:
    def test_no_data_returns_4_hours(self) -> None:
        result = calculate_next_ssl_check(None, now=NOW)
        assert result == NOW + timedelta(hours=4)

    @pytest.mark.parametrize(
        ("days_ahead", "expected"),
        [
            (365, timedelta(days=1)),
            (90, timedelta(days=1)),
            (31, timedelta(days=1)),
            (30, timedelta(hours=6)),
            (10, timedelta(hours=6)),
            (8, timedelta(hours=6)),
            (7, timedelta(hours=1)),
            (5, timedelta(hours=1)),
            (2, timedelta(hours=1)),
            (1, timedelta(hours=4)),  # ровно сутки → ветка ≤ 1
            (0, timedelta(hours=4)),
        ],
    )
    def test_ttl_buckets(self, days_ahead: int, expected: timedelta) -> None:
        not_after = NOW + timedelta(days=days_ahead)
        assert calculate_next_ssl_check(not_after, now=NOW) == NOW + expected

    def test_expired_returns_4_hours(self) -> None:
        # Срок прошёл — продолжаем проверять, вдруг ротация уже на подходе.
        not_after = NOW - timedelta(days=3)
        assert calculate_next_ssl_check(not_after, now=NOW) == NOW + timedelta(hours=4)

    def test_high_fail_count_caps_to_24h(self) -> None:
        not_after = NOW + timedelta(days=10)  # обычно 6h
        result = calculate_next_ssl_check(not_after, fail_count=10, now=NOW)
        assert result == NOW + timedelta(hours=24)

    def test_high_fail_count_overrides_no_data(self) -> None:
        result = calculate_next_ssl_check(None, fail_count=20, now=NOW)
        assert result == NOW + timedelta(hours=24)

    def test_low_fail_count_does_not_throttle(self) -> None:
        not_after = NOW + timedelta(days=10)
        result = calculate_next_ssl_check(not_after, fail_count=3, now=NOW)
        assert result == NOW + timedelta(hours=6)

    def test_default_now_is_utc(self) -> None:
        # Без now — должен взять текущее UTC и не упасть.
        result = calculate_next_ssl_check(None)
        assert result.tzinfo is UTC

    def test_naive_now_raises(self) -> None:
        with pytest.raises(ValueError, match="timezone-aware"):
            calculate_next_ssl_check(None, now=datetime(2026, 5, 17, 12, 0))

    def test_naive_not_after_raises(self) -> None:
        naive = datetime(2026, 5, 17, 12, 0)
        with pytest.raises(ValueError, match="timezone-aware"):
            calculate_next_ssl_check(naive, now=NOW)
