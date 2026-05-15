"""Тесты ``src.utils.formatting``."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from src.utils.formatting import (
    EMOJI_CRITICAL,
    EMOJI_OK,
    EMOJI_UNKNOWN,
    EMOJI_WARNING,
    days_until,
    format_date,
    format_days_until,
    format_domain_for_display,
    get_expiry_emoji,
)

NOW = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)


class TestDaysUntil:
    def test_future(self) -> None:
        target = NOW + timedelta(days=10, hours=3)
        assert days_until(target, now=NOW) == 10

    def test_past(self) -> None:
        target = NOW - timedelta(days=5)
        assert days_until(target, now=NOW) == -5

    def test_same_day(self) -> None:
        # ровно сутки в обе стороны округляются по дельте
        target = NOW + timedelta(hours=12)
        assert days_until(target, now=NOW) == 0

    def test_naive_target_raises(self) -> None:
        with pytest.raises(ValueError):
            days_until(datetime(2026, 5, 25), now=NOW)


class TestFormatDaysUntilRu:
    @pytest.mark.parametrize(
        ("days_offset", "expected_text_substring"),
        [
            (1, "через 1 день"),
            (2, "через 2 дня"),
            (4, "через 4 дня"),
            (5, "через 5 дней"),
            (11, "через 11 дней"),
            (21, "через 21 день"),
            (22, "через 22 дня"),
            (100, "через 100 дней"),
        ],
    )
    def test_plural(self, days_offset: int, expected_text_substring: str) -> None:
        target = NOW + timedelta(days=days_offset, hours=1)
        days, text = format_days_until(target, lang="ru", now=NOW)
        # из-за hours=1 ровно days_offset дней
        assert days == days_offset
        assert text == expected_text_substring

    def test_today(self) -> None:
        target = NOW + timedelta(hours=3)
        _, text = format_days_until(target, lang="ru", now=NOW)
        assert text == "сегодня"

    def test_past_ru(self) -> None:
        target = NOW - timedelta(days=3)
        days, text = format_days_until(target, lang="ru", now=NOW)
        assert days == -3
        assert "истёк" in text and "3 дня" in text


class TestFormatDaysUntilEn:
    @pytest.mark.parametrize(
        ("days_offset", "expected"),
        [
            (1, "in 1 day"),
            (2, "in 2 days"),
            (100, "in 100 days"),
        ],
    )
    def test_plural(self, days_offset: int, expected: str) -> None:
        target = NOW + timedelta(days=days_offset, hours=1)
        _, text = format_days_until(target, lang="en", now=NOW)
        assert text == expected

    def test_past_en(self) -> None:
        target = NOW - timedelta(days=1)
        _, text = format_days_until(target, lang="en", now=NOW)
        assert text == "expired 1 day ago"


class TestFormatDate:
    def test_ru_format(self) -> None:
        dt = datetime(2027, 3, 15, tzinfo=UTC)
        assert format_date(dt, lang="ru") == "15.03.2027"

    def test_en_format(self) -> None:
        dt = datetime(2027, 3, 15, tzinfo=UTC)
        assert format_date(dt, lang="en") == "2027-03-15"


class TestFormatDomainForDisplay:
    def test_idn_decoded(self) -> None:
        assert format_domain_for_display("xn--e1afmkfd.xn--p1ai") == "пример.рф"

    def test_ascii_passthrough(self) -> None:
        assert format_domain_for_display("example.com") == "example.com"


class TestGetExpiryEmoji:
    @pytest.mark.parametrize(
        ("days_left", "expected"),
        [
            (None, EMOJI_UNKNOWN),
            (-5, EMOJI_CRITICAL),
            (0, EMOJI_CRITICAL),
            (6, EMOJI_CRITICAL),
            (7, EMOJI_WARNING),
            (15, EMOJI_WARNING),
            (30, EMOJI_WARNING),
            (31, EMOJI_OK),
            (365, EMOJI_OK),
        ],
    )
    def test_mapping(self, days_left: int | None, expected: str) -> None:
        assert get_expiry_emoji(days_left) == expected
