"""Тесты ``src.dns_monitor.client``: async DNS resolver (ADR 032).

Все сетевые операции замокированы через ``dns.asyncresolver.Resolver``.
Проверяем error categorization и success-кейсы; полагаемся на dnspython
типы исключений для прогона веток кода.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import dns.exception
import dns.resolver
import pytest

from src.config.settings import get_settings
from src.dns_monitor import DNSError, DNSRecords, resolve_records


def _make_answer(records: list[str]) -> MagicMock:
    """Имитирует ``dns.resolver.Answer``: ``rrset`` + итерация по rdata."""
    answer = MagicMock()
    answer.rrset = MagicMock() if records else None
    answer.__iter__.return_value = iter(records)
    return answer


def _patch_resolver(side_effect):
    """Возвращает контекст-менеджер, подменяющий ``Resolver`` так, что
    ``resolve(domain, rtype, ...)`` будет AsyncMock с заданным side_effect."""
    mock_resolver = MagicMock()
    mock_resolver.resolve = AsyncMock(side_effect=side_effect)
    return patch(
        "dns.asyncresolver.Resolver",
        return_value=mock_resolver,
    )


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    """Сбрасываем lru_cache для get_settings, чтобы monkeypatch env работал."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


# ---------------------------------------------------------------------
# disabled / invalid_domain — без сетевых обращений
# ---------------------------------------------------------------------


async def test_disabled_returns_dnserror_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """DNS_ENABLED=false → DNSError(disabled), без сетевых запросов."""
    monkeypatch.setenv("DNS_ENABLED", "false")
    get_settings.cache_clear()

    result = await resolve_records("example.com")
    assert isinstance(result, DNSError)
    assert result.error_type == "disabled"


async def test_invalid_idn_returns_dnserror_invalid_domain() -> None:
    """Битый IDN → DNSError(invalid_domain)."""
    result = await resolve_records("..invalid..")
    assert isinstance(result, DNSError)
    assert result.error_type == "invalid_domain"


# ---------------------------------------------------------------------
# successful resolves
# ---------------------------------------------------------------------


async def test_successful_resolve_with_a_records() -> None:
    """A-записи → DNSRecords(resolution_state=resolved)."""

    async def side_effect(domain, rtype, **kwargs):
        if rtype == "A":
            return _make_answer(["1.2.3.4", "5.6.7.8"])
        if rtype == "NS":
            return _make_answer(["ns1.example.com.", "ns2.example.com."])
        # AAAA / MX — NoAnswer
        raise dns.resolver.NoAnswer()

    with _patch_resolver(side_effect):
        result = await resolve_records("example.com")

    assert isinstance(result, DNSRecords)
    assert result.resolution_state == "resolved"
    assert result.a_records == ["1.2.3.4", "5.6.7.8"]
    assert result.aaaa_records == []
    assert result.ns_records == ["ns1.example.com.", "ns2.example.com."]
    assert result.is_reachable is True


async def test_mx_only_returns_dnsrecords_mx_only() -> None:
    """Нет A/AAAA, но есть MX → resolution_state=mx_only."""

    async def side_effect(domain, rtype, **kwargs):
        if rtype == "MX":
            return _make_answer(["10 mail.example.com."])
        raise dns.resolver.NoAnswer()

    with _patch_resolver(side_effect):
        result = await resolve_records("example.com")

    assert isinstance(result, DNSRecords)
    assert result.resolution_state == "mx_only"
    assert result.a_records == []
    assert result.aaaa_records == []


async def test_no_records_returns_dnsrecords_no_dns() -> None:
    """NoAnswer на всех типах → DNSRecords(no_dns), is_reachable=True."""

    async def side_effect(domain, rtype, **kwargs):
        raise dns.resolver.NoAnswer()

    with _patch_resolver(side_effect):
        result = await resolve_records("example.com")

    assert isinstance(result, DNSRecords)
    assert result.resolution_state == "no_dns"
    assert result.is_reachable is True


# ---------------------------------------------------------------------
# errors — NXDOMAIN, timeout, servfail
# ---------------------------------------------------------------------


async def test_nxdomain_returns_dnserror_nxdomain() -> None:
    """NXDOMAIN на первом резолвере → не идём дальше по цепочке."""

    async def side_effect(domain, rtype, **kwargs):
        raise dns.resolver.NXDOMAIN()

    with _patch_resolver(side_effect) as mock_cls:
        result = await resolve_records("nonexistent-domain-12345.test")

    assert isinstance(result, DNSError)
    assert result.error_type == "nxdomain"
    # NXDOMAIN финален — резолвер инстанциируется только один раз
    assert mock_cls.call_count == 1


async def test_all_resolvers_timeout_returns_dnserror_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Все типы — Timeout → DNSError(timeout) от последнего резолвера."""
    # Один резолвер в цепочке для предсказуемости.
    monkeypatch.setenv("DNS_RESOLVERS", '["1.1.1.1"]')
    get_settings.cache_clear()

    async def side_effect(domain, rtype, **kwargs):
        raise dns.exception.Timeout()

    with _patch_resolver(side_effect):
        result = await resolve_records("example.com")

    assert isinstance(result, DNSError)
    assert result.error_type == "timeout"


async def test_all_resolvers_servfail_returns_dnserror_servfail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Все NoNameservers → DNSError(servfail)."""
    monkeypatch.setenv("DNS_RESOLVERS", '["1.1.1.1"]')
    get_settings.cache_clear()

    async def side_effect(domain, rtype, **kwargs):
        raise dns.resolver.NoNameservers()

    with _patch_resolver(side_effect):
        result = await resolve_records("example.com")

    assert isinstance(result, DNSError)
    assert result.error_type == "servfail"


async def test_chain_fallback_to_second_resolver(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Первый резолвер timeout, второй отвечает A → DNSRecords."""
    monkeypatch.setenv("DNS_RESOLVERS", '["1.1.1.1", "8.8.8.8"]')
    get_settings.cache_clear()

    call_state = {"resolver_idx": 0}

    def factory(*args, **kwargs):
        # Каждый вызов Resolver() создаёт новый mock, который ведёт
        # себя по-разному в зависимости от порядка.
        idx = call_state["resolver_idx"]
        call_state["resolver_idx"] += 1
        mock = MagicMock()
        if idx == 0:

            async def fail(domain, rtype, **kw):
                raise dns.exception.Timeout()

            mock.resolve = AsyncMock(side_effect=fail)
        else:

            async def ok(domain, rtype, **kw):
                if rtype == "A":
                    return _make_answer(["9.9.9.9"])
                raise dns.resolver.NoAnswer()

            mock.resolve = AsyncMock(side_effect=ok)
        return mock

    with patch("dns.asyncresolver.Resolver", side_effect=factory):
        result = await resolve_records("example.com")

    assert isinstance(result, DNSRecords)
    assert result.a_records == ["9.9.9.9"]
    assert call_state["resolver_idx"] == 2  # fallback произошёл
