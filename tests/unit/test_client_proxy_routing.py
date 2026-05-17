"""Тесты роутинга ``lookup_domain`` (proxy → direct fallback, Этап 10)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.whois.client import lookup_direct, lookup_domain
from src.whois.proxy_client import ProxyUnreachable
from src.whois.types import WhoisData, WhoisError


def _settings(enabled: bool = True) -> MagicMock:
    s = MagicMock()
    s.whois_proxy_enabled = enabled
    s.whois_referral_following = False
    return s


@pytest.mark.asyncio
class TestLookupDomainRouting:
    async def test_proxy_enabled_and_alive_returns_proxy_result(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("src.whois.client.get_settings", lambda: _settings(enabled=True))

        proxy_result = WhoisData(
            domain="yandex.ru",
            is_registered=True,
            registrar="RU-CENTER-RU",
            source="proxy_whois_ru",
        )
        proxy_mock = AsyncMock(return_value=proxy_result)
        monkeypatch.setattr("src.whois.client.lookup_via_proxy", proxy_mock)

        # Direct не должен дёргаться при работающем прокси.
        direct_mock = AsyncMock(
            return_value=WhoisError(domain="x", error_type="timeout", message="x")
        )
        monkeypatch.setattr("src.whois.client.lookup_direct", direct_mock)

        result = await lookup_domain("yandex.ru")
        assert result is proxy_result
        proxy_mock.assert_awaited_once_with("yandex.ru")
        direct_mock.assert_not_called()

    async def test_proxy_unreachable_falls_back_to_direct(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("src.whois.client.get_settings", lambda: _settings(enabled=True))

        proxy_mock = AsyncMock(side_effect=ProxyUnreachable("simulated"))
        monkeypatch.setattr("src.whois.client.lookup_via_proxy", proxy_mock)

        direct_result = WhoisData(domain="example.com", is_registered=True, source="rdap")
        direct_mock = AsyncMock(return_value=direct_result)
        monkeypatch.setattr("src.whois.client.lookup_direct", direct_mock)

        result = await lookup_domain("example.com")
        assert result is direct_result
        proxy_mock.assert_awaited_once_with("example.com")
        direct_mock.assert_awaited_once()

    async def test_proxy_disabled_goes_straight_to_direct(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("src.whois.client.get_settings", lambda: _settings(enabled=False))

        # proxy_client.lookup_via_proxy не должен быть вызван вообще.
        proxy_mock = AsyncMock(side_effect=AssertionError("must not be called"))
        monkeypatch.setattr("src.whois.client.lookup_via_proxy", proxy_mock)

        direct_result = WhoisData(domain="example.com", is_registered=True, source="rdap")
        direct_mock = AsyncMock(return_value=direct_result)
        monkeypatch.setattr("src.whois.client.lookup_direct", direct_mock)

        result = await lookup_domain("example.com")
        assert result is direct_result
        proxy_mock.assert_not_called()
        direct_mock.assert_awaited_once()

    async def test_proxy_unreachable_and_direct_fails_returns_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("src.whois.client.get_settings", lambda: _settings(enabled=True))

        proxy_mock = AsyncMock(side_effect=ProxyUnreachable("dead"))
        monkeypatch.setattr("src.whois.client.lookup_via_proxy", proxy_mock)

        direct_err = WhoisError(domain="z.com", error_type="network_error", message="boom")
        direct_mock = AsyncMock(return_value=direct_err)
        monkeypatch.setattr("src.whois.client.lookup_direct", direct_mock)

        result = await lookup_domain("z.com")
        assert isinstance(result, WhoisError)
        assert result.error_type == "network_error"


@pytest.mark.asyncio
class TestLookupDirectInvalidInput:
    async def test_invalid_domain_returns_parse_error(self) -> None:
        result = await lookup_direct("")
        assert isinstance(result, WhoisError)
        assert result.error_type == "parse_error"
