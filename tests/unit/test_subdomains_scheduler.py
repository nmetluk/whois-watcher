"""Тесты ``src.subdomains.scheduler``: adaptive TTL для subdomain enumeration (ADR 037)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from src.subdomains.scheduler import calculate_next_subdomain_check

NOW = datetime(2026, 5, 30, 12, 0, tzinfo=UTC)


class TestCalculateNextSubdomainCheck:
    """Тесты функции calculate_next_subdomain_check."""

    def test_has_subdomains_returns_7_days(self) -> None:
        """Есть поддомены → 7 дней."""
        result = calculate_next_subdomain_check(has_subdomains=True, now=NOW)
        assert result == NOW + timedelta(days=7)

    def test_no_subdomains_returns_30_days(self) -> None:
        """Нет поддоменов → 30 дней."""
        result = calculate_next_subdomain_check(has_subdomains=False, now=NOW)
        assert result == NOW + timedelta(days=30)

    @pytest.mark.parametrize(
        ("fail_count", "expected_hours"),
        [
            (1, 1),
            (2, 1),
        ],
    )
    def test_low_fail_count_returns_1_hour(self, fail_count: int, expected_hours: int) -> None:
        """fail_count 1-2 → 1 час."""
        result = calculate_next_subdomain_check(has_subdomains=True, fail_count=fail_count, now=NOW)
        assert result == NOW + timedelta(hours=expected_hours)

    @pytest.mark.parametrize(
        ("fail_count", "expected_days"),
        [
            (3, 1),
            (4, 1),
            (10, 1),
        ],
    )
    def test_high_fail_count_returns_1_day(self, fail_count: int, expected_days: int) -> None:
        """fail_count ≥ 3 → 1 день."""
        result = calculate_next_subdomain_check(has_subdomains=True, fail_count=fail_count, now=NOW)
        assert result == NOW + timedelta(days=expected_days)

    def test_fail_count_overrides_no_subdomains(self) -> None:
        """При ошибке интервал короткий, даже если нет поддоменов."""
        result = calculate_next_subdomain_check(has_subdomains=False, fail_count=1, now=NOW)
        assert result == NOW + timedelta(hours=1)

    def test_zero_fail_count_is_success_path(self) -> None:
        """fail_count=0 трактуется как успех (нет ошибок)."""
        result = calculate_next_subdomain_check(has_subdomains=True, fail_count=0, now=NOW)
        assert result == NOW + timedelta(days=7)

    def test_default_now_is_utc(self) -> None:
        """Без now — должен взять текущее UTC и не упасть."""
        result = calculate_next_subdomain_check(has_subdomains=True)
        assert result.tzinfo is UTC

    def test_naive_now_raises(self) -> None:
        """naive datetime должен вызывать ValueError."""
        naive = datetime(2026, 5, 30, 12, 0)
        with pytest.raises(ValueError, match="timezone-aware"):
            calculate_next_subdomain_check(has_subdomains=True, now=naive)


class TestCalculateNextSubdomainCheckSuccessInterval:
    """Тесты параметра success_interval_days (TASK-0028, ADR 038)."""

    def test_custom_success_interval_used(self) -> None:
        """При success_interval_days=14 используется 14 дней вместо 7."""
        result = calculate_next_subdomain_check(
            has_subdomains=True, success_interval_days=14, now=NOW
        )
        assert result == NOW + timedelta(days=14)

    def test_success_interval_floor_at_1(self) -> None:
        """success_interval_days с floor 1 день."""
        result = calculate_next_subdomain_check(
            has_subdomains=True, success_interval_days=0, now=NOW
        )
        assert result == NOW + timedelta(days=1)  # floor 1

    def test_default_success_interval_is_7(self) -> None:
        """По умолчанию success_interval_days=7."""
        result = calculate_next_subdomain_check(has_subdomains=True, now=NOW)
        assert result == NOW + timedelta(days=7)

    def test_fail_count_overrides_success_interval(self) -> None:
        """При фейлах success_interval_days игнорируется."""
        result = calculate_next_subdomain_check(
            has_subdomains=True, fail_count=1, success_interval_days=14, now=NOW
        )
        assert result == NOW + timedelta(hours=1)  # фейл — 1 час

    def test_no_subdomains_overrides_success_interval(self) -> None:
        """При отсутствии поддоменов success_interval_days игнорируется."""
        result = calculate_next_subdomain_check(
            has_subdomains=False, success_interval_days=14, now=NOW
        )
        assert result == NOW + timedelta(days=30)  # нет поддоменов — 30 дней
