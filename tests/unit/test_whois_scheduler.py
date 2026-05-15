"""Тесты ``src.whois.scheduler``: адаптивный TTL и retry."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from src.config.limits import Limits
from src.whois.scheduler import calculate_next_check, calculate_retry_after_failure

NOW = datetime(2026, 5, 15, 12, 0, tzinfo=UTC)


@pytest.fixture
def limits() -> Limits:
    """Дефолтные лимиты — те же значения, что в проде."""
    return Limits()


class TestCalculateNextCheck:
    def test_none_expires_at_returns_in_1_day(self, limits: Limits) -> None:
        result = calculate_next_check(None, now=NOW, limits=limits)
        assert result == NOW + timedelta(days=1)

    @pytest.mark.parametrize(
        ("days_ahead", "expected_interval_days"),
        [
            (200, 30),  # > 90 → ttl_far_days
            (91, 30),  # граница
            (90, 7),  # ровно 90 → ttl_mid_days
            (60, 7),
            (31, 7),  # граница
            (30, 2),  # ровно 30 → ttl_near_days
            (10, 2),
            (8, 2),  # граница
            (7, 1),  # ровно 7 → ttl_critical_days
            (1, 1),
        ],
    )
    def test_ttl_buckets(
        self,
        days_ahead: int,
        expected_interval_days: int,
        limits: Limits,
    ) -> None:
        expires = NOW + timedelta(days=days_ahead)
        result = calculate_next_check(expires, now=NOW, limits=limits)
        assert result == NOW + timedelta(days=expected_interval_days)

    def test_recently_expired_returns_1_day(self, limits: Limits) -> None:
        # Истёк 5 дней назад — в окне ttl_after_expiry_days, проверяем ежедневно.
        expires = NOW - timedelta(days=5)
        result = calculate_next_check(expires, now=NOW, limits=limits)
        assert result == NOW + timedelta(days=1)

    def test_long_expired_returns_none(self, limits: Limits) -> None:
        # Истёк больше ttl_after_expiry_days (45) дней назад — перестаём.
        expires = NOW - timedelta(days=50)
        result = calculate_next_check(expires, now=NOW, limits=limits)
        assert result is None

    def test_exactly_at_expiry_boundary(self, limits: Limits) -> None:
        # Истёк РОВНО ``ttl_after_expiry_days`` назад — граница.
        # Условие в коде: ``days_left < -ttl_after_expiry_days``. Здесь
        # days_left == -45 → НЕ строго меньше → ещё проверяем.
        expires = NOW - timedelta(days=limits.ttl_after_expiry_days)
        result = calculate_next_check(expires, now=NOW, limits=limits)
        assert result == NOW + timedelta(days=1)

    def test_naive_expires_at_raises(self, limits: Limits) -> None:
        naive = datetime(2027, 1, 1)
        with pytest.raises(ValueError, match="timezone-aware"):
            calculate_next_check(naive, now=NOW, limits=limits)

    def test_naive_now_raises(self, limits: Limits) -> None:
        with pytest.raises(ValueError, match="timezone-aware"):
            calculate_next_check(
                NOW + timedelta(days=10),
                now=datetime(2026, 5, 15),
                limits=limits,
            )

    def test_uses_default_limits_when_omitted(self) -> None:
        # Не падает без явных limits — берёт синглтон.
        result = calculate_next_check(NOW + timedelta(days=100), now=NOW)
        assert result is not None
        # На дефолтах ttl_far_days=30.
        assert result == NOW + timedelta(days=30)


class TestRetryAfterFailure:
    @pytest.mark.parametrize(
        ("fail_count", "expected_minutes"),
        [
            (0, 15),  # 0 трактуется как 1
            (1, 15),
            (2, 60),
            (3, 120),
            (4, 360),
            (5, 720),
            (6, 1440),  # 6+ → каждые 24 часа
            (10, 1440),
        ],
    )
    def test_retry_intervals(self, fail_count: int, expected_minutes: int) -> None:
        result = calculate_retry_after_failure(fail_count, now=NOW)
        assert result == NOW + timedelta(minutes=expected_minutes)
