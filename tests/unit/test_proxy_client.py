"""Тесты ``src.whois.proxy_client`` (Этап 10 / ADR 028)."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest

from src.whois.proxy_client import (
    ProxyUnreachable,
    _parse_proxy_response,
    lookup_via_proxy,
    proxy_healthcheck,
)
from src.whois.types import WhoisData, WhoisError

# ---------------------------------------------------------------------------
# _parse_proxy_response — все ветки source
# ---------------------------------------------------------------------------


class TestParseProxyResponse:
    def test_whois_text_marked_as_proxy_whois(self) -> None:
        payload = {
            "query": "example.com",
            "source": "whois",
            "ok": True,
            "cached": False,
            "fetched_at": 1_700_000_000,
            "ttl_remaining": 80_000,
            "data": (
                "Domain Name: EXAMPLE.COM\n"
                "Registrar: Example Inc.\n"
                "Registry Expiry Date: 2027-08-13T04:00:00Z\n"
                "Name Server: NS1.EXAMPLE.COM\n"
            ),
            "error": None,
        }
        result = _parse_proxy_response(payload, "example.com")
        assert isinstance(result, WhoisData)
        assert result.source == "proxy_whois"
        assert result.is_registered is True
        assert result.registrar == "Example Inc."
        # proxy_cached флаг не выставлен потому что cached=False
        assert "proxy_cached" not in result.raw_data
        assert result.raw_data["proxy_fetched_at"] == 1_700_000_000
        assert result.raw_data["proxy_source"] == "whois"

    def test_ru_upstream_marked_as_proxy_whois_ru(self) -> None:
        payload = {
            "query": "pinspb.ru",
            "source": "whois_ru_upstream",
            "ok": True,
            "cached": True,
            "fetched_at": 1_700_000_000,
            "ttl_remaining": 80_000,
            "data": (
                "domain:        PINSPB.RU\n"
                "org:           PIN Co. Ltd\n"
                "registrar:     PIN-RU\n"
                "paid-till:     2027-05-26T21:00:00Z\n"
            ),
            "error": None,
        }
        result = _parse_proxy_response(payload, "pinspb.ru")
        assert isinstance(result, WhoisData)
        assert result.source == "proxy_whois_ru"
        assert result.raw_data["proxy_source"] == "whois_ru_upstream"
        assert result.raw_data["proxy_cached"] is True

    def test_rdap_dict_marked_as_proxy_rdap(self) -> None:
        rdap = {
            "objectClassName": "domain",
            "ldhName": "example.com",
            "events": [
                {"eventAction": "expiration", "eventDate": "2027-08-13T04:00:00Z"},
            ],
            "status": ["client transfer prohibited"],
            "entities": [
                {
                    "roles": ["registrar"],
                    "vcardArray": [
                        "vcard",
                        [
                            ["version", {}, "text", "4.0"],
                            ["fn", {}, "text", "Example Registrar"],
                        ],
                    ],
                }
            ],
        }
        payload = {
            "query": "example.com",
            "source": "rdap",
            "ok": True,
            "cached": False,
            "fetched_at": 1_700_000_000,
            "ttl_remaining": 80_000,
            "data": rdap,
            "error": None,
        }
        result = _parse_proxy_response(payload, "example.com")
        assert isinstance(result, WhoisData)
        assert result.source == "proxy_rdap"
        assert result.is_registered is True
        assert result.registrar == "Example Registrar"

    def test_none_with_no_data_marks_unregistered(self) -> None:
        payload = {
            "query": "nonexistent.com",
            "source": "none",
            "ok": False,
            "cached": False,
            "fetched_at": 1_700_000_000,
            "ttl_remaining": 300,
            "data": None,
            "error": "no_data",
        }
        result = _parse_proxy_response(payload, "nonexistent.com")
        assert isinstance(result, WhoisData)
        assert result.is_registered is False
        assert result.source == "proxy_none"

    def test_none_with_other_error_returns_whois_error(self) -> None:
        payload = {
            "source": "none",
            "ok": False,
            "data": None,
            "error": "rate_limit",
        }
        result = _parse_proxy_response(payload, "x.com")
        assert isinstance(result, WhoisError)
        assert "rate_limit" in result.message

    def test_unknown_source_returns_parse_error(self) -> None:
        payload = {"source": "telepathy", "ok": True, "data": "..."}
        result = _parse_proxy_response(payload, "x.com")
        assert isinstance(result, WhoisError)
        assert "Unknown proxy source" in result.message

    def test_rdap_with_non_dict_data_returns_parse_error(self) -> None:
        payload = {"source": "rdap", "ok": True, "data": "not a dict"}
        result = _parse_proxy_response(payload, "x.com")
        assert isinstance(result, WhoisError)
        assert "Expected dict" in result.message

    def test_whois_with_non_str_data_returns_parse_error(self) -> None:
        payload = {"source": "whois", "ok": True, "data": {"oops": 1}}
        result = _parse_proxy_response(payload, "x.com")
        assert isinstance(result, WhoisError)
        assert "Expected str" in result.message


# ---------------------------------------------------------------------------
# lookup_via_proxy — mocked aiohttp
# ---------------------------------------------------------------------------


def _make_session_mock(status: int, body: dict[str, Any]) -> MagicMock:
    """Mocked ``aiohttp.ClientSession`` отдающий заранее заданный ответ."""
    response = MagicMock()
    response.status = status
    response.json = AsyncMock(return_value=body)

    @asynccontextmanager
    async def get_cm(*_a: Any, **_kw: Any):
        yield response

    session = MagicMock(spec=aiohttp.ClientSession)
    session.get = MagicMock(side_effect=lambda *a, **kw: get_cm(*a, **kw))
    session.close = AsyncMock()
    return session


def _make_session_raising(exc: Exception) -> MagicMock:
    @asynccontextmanager
    async def get_cm(*_a: Any, **_kw: Any):
        raise exc
        yield  # pragma: no cover  (для типизации)

    session = MagicMock(spec=aiohttp.ClientSession)
    session.get = MagicMock(side_effect=lambda *a, **kw: get_cm(*a, **kw))
    session.close = AsyncMock()
    return session


def _patch_settings(monkeypatch: pytest.MonkeyPatch, **overrides: Any) -> None:
    """Подменяет ``get_settings`` для модуля proxy_client."""
    base = {
        "whois_proxy_enabled": True,
        "whois_proxy_url": "http://proxy.test:8043",
        "whois_proxy_timeout_seconds": 5,
    }
    base.update(overrides)
    stub = MagicMock()
    for k, v in base.items():
        setattr(stub, k, v)
    monkeypatch.setattr("src.whois.proxy_client.get_settings", lambda: stub)


@pytest.mark.asyncio
class TestLookupViaProxy:
    async def test_disabled_in_settings_raises_unreachable(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_settings(monkeypatch, whois_proxy_enabled=False)
        with pytest.raises(ProxyUnreachable):
            await lookup_via_proxy("example.com")

    async def test_successful_whois_response(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_settings(monkeypatch)
        body = {
            "query": "example.com",
            "source": "whois",
            "ok": True,
            "cached": False,
            "fetched_at": 1_700_000_000,
            "ttl_remaining": 80_000,
            "data": "Domain Name: EXAMPLE.COM\nRegistrar: Example Inc.\n",
            "error": None,
        }
        session = _make_session_mock(200, body)
        result = await lookup_via_proxy("example.com", session=session)
        assert isinstance(result, WhoisData)
        assert result.source == "proxy_whois"
        session.close.assert_not_called()  # не наша сессия → не закрываем

    async def test_5xx_raises_unreachable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_settings(monkeypatch)
        session = _make_session_mock(503, {})
        with pytest.raises(ProxyUnreachable):
            await lookup_via_proxy("example.com", session=session)

    async def test_400_returns_whois_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_settings(monkeypatch)
        session = _make_session_mock(400, {})
        result = await lookup_via_proxy("example.com", session=session)
        assert isinstance(result, WhoisError)
        assert result.error_type == "parse_error"
        assert "400" in result.message

    async def test_network_error_raises_unreachable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_settings(monkeypatch)
        session = _make_session_raising(aiohttp.ClientConnectionError("refused"))
        with pytest.raises(ProxyUnreachable):
            await lookup_via_proxy("example.com", session=session)

    async def test_timeout_raises_unreachable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_settings(monkeypatch)
        session = _make_session_raising(TimeoutError())
        with pytest.raises(ProxyUnreachable):
            await lookup_via_proxy("example.com", session=session)

    async def test_invalid_domain_returns_whois_error_without_calling_proxy(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_settings(monkeypatch)
        session = _make_session_mock(200, {})
        result = await lookup_via_proxy("", session=session)
        assert isinstance(result, WhoisError)
        session.get.assert_not_called()


# ---------------------------------------------------------------------------
# proxy_healthcheck
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestProxyHealthcheck:
    async def test_returns_true_on_200(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_settings(monkeypatch)
        session = _make_session_mock(200, {})
        assert await proxy_healthcheck(session=session) is True

    async def test_returns_false_on_timeout(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_settings(monkeypatch)
        session = _make_session_raising(TimeoutError())
        assert await proxy_healthcheck(session=session) is False

    async def test_returns_false_when_disabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_settings(monkeypatch, whois_proxy_enabled=False)
        assert await proxy_healthcheck() is False

    async def test_returns_false_on_5xx(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_settings(monkeypatch)
        session = _make_session_mock(503, {})
        assert await proxy_healthcheck(session=session) is False
