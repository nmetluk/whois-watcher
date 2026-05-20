"""Тесты ``format_dns_block`` (Этап 14, ADR 032).

Используем dataclass-фейк вместо ORM-объекта — ``format_dns_block``
принимает структурный объект (DNSCache | None), а ``detect_ns_mismatch``
работает с list[str]. Никакой БД и SQLAlchemy в этих тестах.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from src.services.formatters import format_dns_block


@dataclass
class FakeDNSCache:
    """Мок ``DNSCache`` для тестов формата.

    Поля совпадают с реальной моделью (``src.db.models.DNSCache``) —
    ``format_dns_block`` обращается к ним через atomic attribute access.
    """

    last_checked_at: datetime | None = field(default_factory=lambda: datetime.now(tz=UTC))
    last_successful_check_at: datetime | None = field(default_factory=lambda: datetime.now(tz=UTC))
    a_records: list[str] | None = None
    aaaa_records: list[str] | None = None
    ns_records: list[str] | None = None
    resolution_state: str = "resolved"
    is_reachable: bool | None = True
    ns_mismatch_active: bool = False


def test_returns_none_for_unchecked_cache() -> None:
    cache = FakeDNSCache(last_checked_at=None)
    assert format_dns_block(cache, whois_ns=None, lang="ru") is None  # type: ignore[arg-type]


def test_returns_none_for_unknown_state() -> None:
    cache = FakeDNSCache(resolution_state="unknown")
    assert format_dns_block(cache, whois_ns=None, lang="ru") is None  # type: ignore[arg-type]


def test_returns_none_for_resolved_without_any_records() -> None:
    # resolution_state='resolved' но списки пусты — по контракту dns_monitor
    # такого не должно быть, но format_dns_block устойчив к мусору.
    cache = FakeDNSCache(a_records=None, aaaa_records=None, ns_records=None)
    assert format_dns_block(cache, whois_ns=None, lang="ru") is None  # type: ignore[arg-type]


def test_resolved_with_a_and_ns_match() -> None:
    cache = FakeDNSCache(
        a_records=["1.2.3.4"],
        ns_records=["ns1.example.com.", "ns2.example.com."],
    )
    result = format_dns_block(
        cache,  # type: ignore[arg-type]
        whois_ns=["ns1.example.com", "ns2.example.com"],
        lang="ru",
    )
    assert result is not None
    assert "1.2.3.4" in result
    assert "✓" in result
    assert "🚨" not in result
    # Tree оформление: первая строка-заголовок, A в `├`, NS в `└`.
    lines = result.splitlines()
    assert lines[1].startswith("├ ")
    assert lines[-1].startswith("└ ")


def test_resolved_with_ns_mismatch_highlights() -> None:
    cache = FakeDNSCache(
        a_records=["1.2.3.4"],
        ns_records=["ns1.suspicious.com."],
    )
    result = format_dns_block(
        cache,  # type: ignore[arg-type]
        whois_ns=["ns1.legit.com"],
        lang="ru",
    )
    assert result is not None
    assert "🚨" in result
    assert "ns1.suspicious.com" in result
    # Registry-NS появляется отдельной строкой для контекста.
    assert "ns1.legit.com" in result


def test_unreachable_returns_compact_line() -> None:
    cache = FakeDNSCache(resolution_state="error", is_reachable=False)
    result = format_dns_block(cache, whois_ns=None, lang="ru")  # type: ignore[arg-type]
    assert result is not None
    assert "не отвечает" in result.lower()
    # Compact-формат — никакого tree.
    assert "├" not in result and "└" not in result


def test_mx_only_returns_compact_line() -> None:
    cache = FakeDNSCache(resolution_state="mx_only")
    result = format_dns_block(cache, whois_ns=None, lang="ru")  # type: ignore[arg-type]
    assert result is not None
    assert "├" not in result and "└" not in result
    assert "MX" in result.upper()


def test_no_dns_returns_compact_line() -> None:
    cache = FakeDNSCache(resolution_state="no_dns")
    result = format_dns_block(cache, whois_ns=None, lang="ru")  # type: ignore[arg-type]
    assert result is not None
    assert "├" not in result and "└" not in result


def test_long_a_records_list_truncated_with_count() -> None:
    cache = FakeDNSCache(a_records=[f"10.0.0.{i}" for i in range(1, 11)])
    result = format_dns_block(cache, whois_ns=None, lang="ru")  # type: ignore[arg-type]
    assert result is not None
    # Первые 5 IP отображаются + индикатор остальных.
    assert "10.0.0.1" in result
    assert "10.0.0.5" in result
    assert "(+5)" in result
    # 6-й IP не показывается.
    assert "10.0.0.6" not in result


def test_a_only_without_ns_closes_tree_correctly() -> None:
    cache = FakeDNSCache(a_records=["1.2.3.4"], ns_records=None)
    result = format_dns_block(cache, whois_ns=None, lang="ru")  # type: ignore[arg-type]
    assert result is not None
    # Должна быть закрывающая `└`, не висящая `├`.
    lines = result.splitlines()
    assert lines[-1].startswith("└ ")
    assert "├" not in result


def test_english_locale_for_translatable_state() -> None:
    # Используем mx_only — описательная строка, у которой RU/EN расходятся.
    # У "resolved"-формата A/NS-метки одинаковы в обоих языках (это features).
    cache = FakeDNSCache(resolution_state="mx_only")
    ru = format_dns_block(cache, whois_ns=None, lang="ru")  # type: ignore[arg-type]
    en = format_dns_block(cache, whois_ns=None, lang="en")  # type: ignore[arg-type]
    assert ru is not None and en is not None
    assert ru != en
    assert "только MX" in ru
    assert "MX only" in en
