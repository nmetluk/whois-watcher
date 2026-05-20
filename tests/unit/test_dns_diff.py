"""Тесты ``compute_dns_diff`` и ``detect_ns_mismatch`` (ADR 032)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from src.dns_monitor import (
    DNSError,
    DNSRecords,
    compute_dns_diff,
    detect_ns_mismatch,
)

# Дефолт last_checked_at — непустой, чтобы существующие тесты
# с реальным diff'ом продолжали работать. Bootstrap-тест передаёт
# None явно.
_DEFAULT_LAST_CHECKED = datetime(2026, 1, 1, tzinfo=UTC)


@dataclass
class FakeDNSCache:
    """Минимальный фейк ``DNSCache`` — только поля, нужные diff'у."""

    a_records: list[str] | None = None
    aaaa_records: list[str] | None = None
    ns_records: list[str] | None = None
    asn_set: list[int] | None = None
    is_reachable: bool | None = True
    last_checked_at: datetime | None = _DEFAULT_LAST_CHECKED


def _records(**kwargs) -> DNSRecords:
    defaults: dict = {"domain": "example.com", "is_reachable": True}
    defaults.update(kwargs)
    return DNSRecords(**defaults)


# ---------------------------------------------------------------------
# first-fetch guard
# ---------------------------------------------------------------------


def test_first_fetch_old_none_returns_empty_diff() -> None:
    new = _records(a_records=["1.2.3.4"])
    diff = compute_dns_diff(None, new, [])
    assert not diff.has_any_changes
    assert not diff.has_critical_changes


def test_bootstrap_row_with_null_last_checked_no_changes() -> None:
    """Sparse bootstrap-строка (``last_checked_at=None``) не триггерит
    change-флаги при первой реальной проверке.

    Регрессия 14e: ``dns_scheduler_tick`` bootstrap создавал строки
    с NULL-записями и NULL ``last_checked_at``. ``compute_dns_diff``
    видел ``old is not None`` и сравнивал ``sorted(None or []) = []``
    с реальными записями → ложные ``a_changed`` / ``ns_changed`` /
    ``aaaa_changed`` (в проде 38 уведомлений за один тик).
    """
    bootstrap_row = FakeDNSCache(
        a_records=None,
        aaaa_records=None,
        ns_records=None,
        last_checked_at=None,  # ключевой маркер bootstrap-строки
        is_reachable=None,
    )
    new = _records(
        a_records=["1.2.3.4"],
        aaaa_records=["2001:db8::1"],
        ns_records=["ns1.example.com."],
    )
    diff = compute_dns_diff(bootstrap_row, new, [])
    assert not diff.has_any_changes, "bootstrap row must not trigger change notifications"


# ---------------------------------------------------------------------
# A / AAAA / NS changes
# ---------------------------------------------------------------------


def test_a_records_changed_sets_a_changed() -> None:
    old = FakeDNSCache(a_records=["1.2.3.4"])
    new = _records(a_records=["5.6.7.8"])
    diff = compute_dns_diff(old, new, [])
    assert diff.a_changed
    assert not diff.aaaa_changed
    assert not diff.ns_changed


def test_aaaa_records_changed_sets_aaaa_changed() -> None:
    old = FakeDNSCache(aaaa_records=["2001:db8::1"])
    new = _records(aaaa_records=["2001:db8::2"])
    diff = compute_dns_diff(old, new, [])
    assert diff.aaaa_changed
    assert not diff.a_changed


def test_ns_records_changed_sets_ns_changed() -> None:
    old = FakeDNSCache(ns_records=["ns1.old.com"])
    new = _records(ns_records=["ns1.new.com"])
    diff = compute_dns_diff(old, new, [])
    assert diff.ns_changed


def test_no_changes_returns_empty_diff() -> None:
    old = FakeDNSCache(
        a_records=["1.2.3.4"],
        ns_records=["ns1.com"],
    )
    new = _records(a_records=["1.2.3.4"], ns_records=["ns1.com"])
    diff = compute_dns_diff(old, new, [])
    assert not diff.has_any_changes


def test_sorted_comparison_ignores_order() -> None:
    """Список IP в разном порядке — не считается изменением."""
    old = FakeDNSCache(a_records=["1.2.3.4", "5.6.7.8"])
    new = _records(a_records=["5.6.7.8", "1.2.3.4"])
    diff = compute_dns_diff(old, new, [])
    assert not diff.a_changed


# ---------------------------------------------------------------------
# reachability transitions
# ---------------------------------------------------------------------


def test_became_unreachable_only_when_was_reachable() -> None:
    old = FakeDNSCache(is_reachable=True)
    new = DNSError(domain="example.com", error_type="timeout", message="...")
    diff = compute_dns_diff(old, new, [])
    assert diff.became_unreachable

    # А если уже был unreachable — не дублируем
    old_unreachable = FakeDNSCache(is_reachable=False)
    diff2 = compute_dns_diff(old_unreachable, new, [])
    assert not diff2.became_unreachable


def test_became_reachable_after_outage() -> None:
    old = FakeDNSCache(is_reachable=False)
    new = _records(a_records=["1.2.3.4"])
    diff = compute_dns_diff(old, new, [])
    assert diff.became_reachable


def test_invalid_domain_error_does_not_trigger_became_unreachable() -> None:
    """invalid_domain / disabled — конфигурационные, не сетевые."""
    old = FakeDNSCache(is_reachable=True)

    new = DNSError(domain="example.com", error_type="invalid_domain", message="...")
    diff = compute_dns_diff(old, new, [])
    assert not diff.became_unreachable

    new2 = DNSError(domain="example.com", error_type="disabled", message="...")
    diff2 = compute_dns_diff(old, new2, [])
    assert not diff2.became_unreachable


# ---------------------------------------------------------------------
# ASN-set (true critical signal)
# ---------------------------------------------------------------------


def test_asn_change_sets_both_a_and_aaaa_asn_changed() -> None:
    """ASN-смена — один сигнал на обе семейки (общий ASN-set)."""
    old = FakeDNSCache(a_records=["1.2.3.4"], asn_set=[13335])
    new = _records(a_records=["5.6.7.8"])
    diff = compute_dns_diff(old, new, [16509])
    assert diff.a_asn_changed
    assert diff.aaaa_asn_changed
    assert diff.has_critical_changes


def test_empty_asn_set_does_not_trigger_asn_change() -> None:
    """В v0.8.0 ASN всегда [] — критичности нет."""
    old = FakeDNSCache(a_records=["1.2.3.4"], asn_set=[])
    new = _records(a_records=["5.6.7.8"])
    diff = compute_dns_diff(old, new, [])
    assert not diff.a_asn_changed
    assert diff.a_changed  # IP всё-таки сменился
    assert not diff.has_critical_changes


# ---------------------------------------------------------------------
# detect_ns_mismatch
# ---------------------------------------------------------------------


def test_detect_ns_mismatch_case_insensitive() -> None:
    assert not detect_ns_mismatch(["NS1.Example.COM"], ["ns1.example.com"])


def test_detect_ns_mismatch_trailing_dot_normalized() -> None:
    assert not detect_ns_mismatch(["ns1.example.com."], ["ns1.example.com"])


def test_detect_ns_mismatch_actual_difference() -> None:
    assert detect_ns_mismatch(["ns1.suspicious.com"], ["ns1.legit.com"])


def test_detect_ns_mismatch_empty_list_returns_false() -> None:
    """Если хоть один список пуст — False (insufficient data)."""
    assert not detect_ns_mismatch([], ["ns1.com"])
    assert not detect_ns_mismatch(["ns1.com"], [])
    assert not detect_ns_mismatch([], [])
