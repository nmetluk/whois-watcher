"""Тесты ``calculate_next_dns_check`` (ADR 032)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from src.dns_monitor.scheduler import (
    BACKOFF_INTERVAL,
    CDN_LIKELY_INTERVAL,
    FRESH_INTERVAL,
    NS_MISMATCH_INTERVAL,
    STABLE_INTERVAL,
    calculate_next_dns_check,
)

NOW = datetime(2026, 5, 20, 12, 0, 0, tzinfo=UTC)


def test_new_domain_gets_fresh_interval() -> None:
    """last_successful_at=None → FRESH_INTERVAL (1h)."""
    next_at = calculate_next_dns_check(
        last_successful_at=None,
        last_changed_at=None,
        fail_count=0,
        ns_mismatch_active=False,
        last_change_was_asn=False,
        now=NOW,
    )
    assert next_at == NOW + FRESH_INTERVAL


def test_high_fail_count_backoff() -> None:
    """fail_count >= 10 → BACKOFF_INTERVAL (24h)."""
    next_at = calculate_next_dns_check(
        last_successful_at=NOW - timedelta(days=2),
        last_changed_at=None,
        fail_count=15,
        ns_mismatch_active=False,
        last_change_was_asn=False,
        now=NOW,
    )
    assert next_at == NOW + BACKOFF_INTERVAL


def test_high_fail_count_overrides_ns_mismatch() -> None:
    """Backoff приоритетнее NS-mismatch (защита от спама на мёртвый хост)."""
    next_at = calculate_next_dns_check(
        last_successful_at=None,
        last_changed_at=None,
        fail_count=20,
        ns_mismatch_active=True,
        last_change_was_asn=False,
        now=NOW,
    )
    assert next_at == NOW + BACKOFF_INTERVAL


def test_ns_mismatch_overrides_stable() -> None:
    """NS-mismatch active → NS_MISMATCH_INTERVAL (30 min)."""
    next_at = calculate_next_dns_check(
        last_successful_at=NOW - timedelta(days=30),
        last_changed_at=None,
        fail_count=0,
        ns_mismatch_active=True,
        last_change_was_asn=False,
        now=NOW,
    )
    assert next_at == NOW + NS_MISMATCH_INTERVAL


def test_recent_change_without_asn_is_cdn_likely() -> None:
    """Recent change last 24h без ASN-смены → CDN_LIKELY_INTERVAL (6h)."""
    next_at = calculate_next_dns_check(
        last_successful_at=NOW,
        last_changed_at=NOW - timedelta(hours=2),
        fail_count=0,
        ns_mismatch_active=False,
        last_change_was_asn=False,
        now=NOW,
    )
    assert next_at == NOW + CDN_LIKELY_INTERVAL


def test_recent_asn_change_is_fresh() -> None:
    """Recent ASN-смена → FRESH_INTERVAL (1h, плотно)."""
    next_at = calculate_next_dns_check(
        last_successful_at=NOW,
        last_changed_at=NOW - timedelta(hours=2),
        fail_count=0,
        ns_mismatch_active=False,
        last_change_was_asn=True,
        now=NOW,
    )
    assert next_at == NOW + FRESH_INTERVAL


def test_stable_domain_gets_stable_interval() -> None:
    """Successful, no recent changes → STABLE_INTERVAL (1 day)."""
    next_at = calculate_next_dns_check(
        last_successful_at=NOW - timedelta(days=10),
        last_changed_at=None,
        fail_count=0,
        ns_mismatch_active=False,
        last_change_was_asn=False,
        now=NOW,
    )
    assert next_at == NOW + STABLE_INTERVAL


def test_old_change_outside_window_stable() -> None:
    """Change > 24h назад → не CDN-likely, обычный stable."""
    next_at = calculate_next_dns_check(
        last_successful_at=NOW - timedelta(days=5),
        last_changed_at=NOW - timedelta(days=3),
        fail_count=0,
        ns_mismatch_active=False,
        last_change_was_asn=False,
        now=NOW,
    )
    assert next_at == NOW + STABLE_INTERVAL


def test_default_now_is_timezone_aware() -> None:
    """Когда now не передан — используется ``datetime.now(UTC)``."""
    next_at = calculate_next_dns_check(
        last_successful_at=None,
        last_changed_at=None,
        fail_count=0,
        ns_mismatch_active=False,
        last_change_was_asn=False,
    )
    assert next_at.tzinfo is not None
