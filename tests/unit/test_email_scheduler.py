"""Тесты ``src.email_intel.scheduler``: adaptive TTL для email-intel проверок."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from src.email_intel.scheduler import calculate_next_email_check

NOW = datetime(2026, 5, 30, 12, 0, tzinfo=UTC)


class TestCalculateNextEmailCheck:
    def test_no_data_returns_1_day(self) -> None:
        """Нет DMARC/SPF — проверяем раз в день."""
        result = calculate_next_email_check(
            has_dmarc=False,
            has_spf=False,
            now=NOW,
        )
        assert result == NOW + timedelta(days=1)

    def test_only_dmarc_returns_1_day(self) -> None:
        """Есть DMARC но нет SPF — проверяем раз в день."""
        result = calculate_next_email_check(
            has_dmarc=True,
            has_spf=False,
            now=NOW,
        )
        assert result == NOW + timedelta(days=1)

    def test_only_spf_returns_1_day(self) -> None:
        """Есть SPF но нет DMARC — проверяем раз в день."""
        result = calculate_next_email_check(
            has_dmarc=False,
            has_spf=True,
            now=NOW,
        )
        assert result == NOW + timedelta(days=1)

    def test_has_both_returns_7_days(self) -> None:
        """Есть и DMARC и SPF — проверяем раз в неделю."""
        result = calculate_next_email_check(
            has_dmarc=True,
            has_spf=True,
            now=NOW,
        )
        assert result == NOW + timedelta(days=7)

    def test_high_fail_count_caps_to_1_day(self) -> None:
        """После 10 фейлов — раз в день независимо от данных."""
        result = calculate_next_email_check(
            has_dmarc=True,
            has_spf=True,
            fail_count=10,
            now=NOW,
        )
        assert result == NOW + timedelta(days=1)

    def test_high_fail_count_overrides_no_data(self) -> None:
        """High fail_count применяется даже без данных."""
        result = calculate_next_email_check(
            has_dmarc=False,
            has_spf=False,
            fail_count=15,
            now=NOW,
        )
        assert result == NOW + timedelta(days=1)

    def test_low_fail_count_does_not_throttle(self) -> None:
        """Малый fail_count не влияет на интервал."""
        result = calculate_next_email_check(
            has_dmarc=True,
            has_spf=True,
            fail_count=3,
            now=NOW,
        )
        assert result == NOW + timedelta(days=7)

    def test_default_now_is_utc(self) -> None:
        """Без now — должен взять текущее UTC."""
        result = calculate_next_email_check(
            has_dmarc=True,
            has_spf=True,
        )
        assert result.tzinfo is UTC

    def test_naive_now_raises(self) -> None:
        """Naive datetime должен падать."""
        naive = datetime(2026, 5, 30, 12, 0)
        with pytest.raises(ValueError, match="timezone-aware"):
            calculate_next_email_check(
                has_dmarc=True,
                has_spf=True,
                now=naive,
            )
