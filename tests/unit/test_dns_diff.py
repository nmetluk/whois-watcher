"""Тесты ``compute_dns_diff`` и ``detect_ns_mismatch`` (ADR 032)."""

from __future__ import annotations

from dataclasses import dataclass

from src.dns_monitor import (
    DNSError,
    DNSRecords,
    compute_dns_diff,
    detect_ns_mismatch,
)


@dataclass
class FakeDNSCache:
    """Минимальный фейк ``DNSCache`` — только поля, нужные diff'у."""

    a_records: list[str] | None = None
    aaaa_records: list[str] | None = None
    ns_records: list[str] | None = None
    asn_set: list[int] | None = None
    is_reachable: bool | None = True


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
