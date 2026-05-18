"""Тесты ``src.rir_client`` (Этап 13 / ADR 031)."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest

from src.rir_client import (
    ASNAllocation,
    IPAllocation,
    RIRError,
    RIRUnreachable,
    get_status,
    healthcheck,
    lookup_asn,
    lookup_ip,
)

# ---------------------------------------------------------------------------
# Helpers — мокаем aiohttp.ClientSession (зеркало test_proxy_client.py)
# ---------------------------------------------------------------------------


def _make_session_mock(status: int, body: Any, body_kind: str = "json") -> MagicMock:
    """Mocked ``aiohttp.ClientSession`` отдающий заранее заданный ответ.

    ``body_kind="json"`` → ответит ``resp.json()``,
    ``body_kind="text"`` → ответит ``resp.text()`` (для 4xx/5xx веток).
    """
    response = MagicMock()
    response.status = status
    if body_kind == "json":
        response.json = AsyncMock(return_value=body)
        response.text = AsyncMock(return_value="")
    else:
        response.json = AsyncMock(side_effect=ValueError("not json"))
        response.text = AsyncMock(return_value=body if isinstance(body, str) else "")

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
    """Подменяет ``get_settings`` для модуля rir_client.client."""
    base = {
        "rir2localdb_enabled": True,
        "rir2localdb_url": "http://rir.test:18000",
        "rir2localdb_timeout_seconds": 5.0,
        "rir2localdb_connect_timeout_seconds": 1.0,
    }
    base.update(overrides)
    stub = MagicMock()
    for k, v in base.items():
        setattr(stub, k, v)
    monkeypatch.setattr("src.rir_client.client.get_settings", lambda: stub)


# Реальные JSON-ответы из подэтапа 3a smoke-теста (rir2localdb v0.1.1).

_IP_888_BODY: dict[str, Any] = {
    "address": "8.8.8.8",
    "family": 4,
    "rir": "arin",
    "cc": "US",
    "start": "8.8.8.0",
    "value": 256,
    "prefix_length": 24,
    "status": "allocated",
    "allocated_on": "2023-12-28",
    "opaque_id": "9d99e3f7d38d1b8026f2ebbea4017c9f",
    "first_seen_run": 1,
    "last_seen_run": 2,
    "is_stale": False,
    "rpsl": {
        "inetnum": {
            "rir": "apnic",
            "start": "8.0.0.0",
            "value": 16777216,
            "netname": "IANA-NETBLOCK-8",
            "country": "AU",
            "descr": "This network range is not allocated to APNIC.",
            "org": None,
            "admin_c": ["IANA1-AP"],
            "tech_c": ["IANA1-AP"],
            "status": "ALLOCATED PORTABLE",
            "mnt_by": ["MAINT-APNIC-AP"],
            "created": None,
            "last_modified": "2008-09-04T06:51:28Z",
            "source": "APNIC",
            "is_stale": False,
        },
        "organisation": None,
    },
}

_ASN_15169_BODY: dict[str, Any] = {
    "asn": 15169,
    "rir": "arin",
    "cc": "US",
    "start_asn": 15169,
    "count": 1,
    "status": "assigned",
    "allocated_on": "2000-03-30",
    "opaque_id": "9d99e3f7d38d1b8026f2ebbea4017c9f",
    "first_seen_run": 1,
    "last_seen_run": 2,
    "is_stale": False,
    "rpsl": {"aut_num": None, "organisation": None},
}


# ---------------------------------------------------------------------------
# lookup_ip
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestLookupIp:
    async def test_disabled_returns_disabled_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_settings(monkeypatch, rir2localdb_enabled=False)
        result = await lookup_ip("8.8.8.8")
        assert isinstance(result, RIRError)
        assert result.kind == "disabled"

    async def test_success_parses_into_ip_allocation(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_settings(monkeypatch)
        session = _make_session_mock(200, _IP_888_BODY)
        result = await lookup_ip("8.8.8.8", session=session)
        assert isinstance(result, IPAllocation)
        assert result.address == "8.8.8.8"
        assert result.family == 4
        assert result.rir == "arin"
        assert result.cc == "US"
        assert result.prefix_length == 24
        assert result.is_stale is False
        assert result.rpsl is not None
        session.close.assert_not_called()  # не наша сессия — не закрываем

    async def test_404_returns_not_found(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_settings(monkeypatch)
        session = _make_session_mock(404, "no allocation", body_kind="text")
        result = await lookup_ip("0.0.0.1", session=session)
        assert isinstance(result, RIRError)
        assert result.kind == "not_found"
        assert result.status_code == 404

    async def test_400_returns_bad_request(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_settings(monkeypatch)
        session = _make_session_mock(400, '{"detail":"invalid IP"}', body_kind="text")
        result = await lookup_ip("not-an-ip", session=session)
        assert isinstance(result, RIRError)
        assert result.kind == "bad_request"
        assert result.status_code == 400

    async def test_500_returns_server_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_settings(monkeypatch)
        session = _make_session_mock(500, "internal", body_kind="text")
        result = await lookup_ip("8.8.8.8", session=session)
        assert isinstance(result, RIRError)
        assert result.kind == "server_error"
        assert result.status_code == 500

    async def test_invalid_json_returns_invalid_response(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_settings(monkeypatch)
        # 200 + JSON где не хватает обязательных полей IPAllocation
        broken_body = {"address": "8.8.8.8"}  # нет family/rir/...
        session = _make_session_mock(200, broken_body)
        result = await lookup_ip("8.8.8.8", session=session)
        assert isinstance(result, RIRError)
        assert result.kind == "invalid_response"
        assert result.status_code == 200

    async def test_timeout_returns_unreachable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_settings(monkeypatch)
        session = _make_session_raising(TimeoutError())
        result = await lookup_ip("8.8.8.8", session=session)
        assert isinstance(result, RIRError)
        assert result.kind == "unreachable"

    async def test_connect_error_returns_unreachable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_settings(monkeypatch)
        session = _make_session_raising(aiohttp.ClientConnectionError("refused"))
        result = await lookup_ip("8.8.8.8", session=session)
        assert isinstance(result, RIRError)
        assert result.kind == "unreachable"

    async def test_unexpected_status_returns_server_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_settings(monkeypatch)
        session = _make_session_mock(418, "I'm a teapot", body_kind="text")
        result = await lookup_ip("8.8.8.8", session=session)
        assert isinstance(result, RIRError)
        assert result.kind == "server_error"
        assert result.status_code == 418


# ---------------------------------------------------------------------------
# lookup_asn
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestLookupAsn:
    async def test_disabled_returns_disabled_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_settings(monkeypatch, rir2localdb_enabled=False)
        result = await lookup_asn(15169)
        assert isinstance(result, RIRError)
        assert result.kind == "disabled"

    async def test_success_parses_into_asn_allocation(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_settings(monkeypatch)
        session = _make_session_mock(200, _ASN_15169_BODY)
        result = await lookup_asn(15169, session=session)
        assert isinstance(result, ASNAllocation)
        assert result.asn == 15169
        assert result.rir == "arin"
        assert result.cc == "US"
        assert result.count == 1
        assert result.is_stale is False

    async def test_404_returns_not_found(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_settings(monkeypatch)
        session = _make_session_mock(404, "no allocation", body_kind="text")
        result = await lookup_asn(4294967294, session=session)
        assert isinstance(result, RIRError)
        assert result.kind == "not_found"

    async def test_500_returns_server_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_settings(monkeypatch)
        session = _make_session_mock(503, "down", body_kind="text")
        result = await lookup_asn(15169, session=session)
        assert isinstance(result, RIRError)
        assert result.kind == "server_error"
        assert result.status_code == 503

    async def test_timeout_returns_unreachable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_settings(monkeypatch)
        session = _make_session_raising(TimeoutError())
        result = await lookup_asn(15169, session=session)
        assert isinstance(result, RIRError)
        assert result.kind == "unreachable"

    async def test_connect_error_returns_unreachable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_settings(monkeypatch)
        session = _make_session_raising(aiohttp.ClientConnectionError("refused"))
        result = await lookup_asn(15169, session=session)
        assert isinstance(result, RIRError)
        assert result.kind == "unreachable"

    async def test_invalid_json_returns_invalid_response(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_settings(monkeypatch)
        broken_body = {"asn": 15169}
        session = _make_session_mock(200, broken_body)
        result = await lookup_asn(15169, session=session)
        assert isinstance(result, RIRError)
        assert result.kind == "invalid_response"


# ---------------------------------------------------------------------------
# healthcheck
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestHealthcheck:
    async def test_returns_true_on_status_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_settings(monkeypatch)
        session = _make_session_mock(200, {"status": "ok"})
        assert await healthcheck(session=session) is True

    async def test_returns_false_on_status_not_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_settings(monkeypatch)
        session = _make_session_mock(200, {"status": "degraded"})
        assert await healthcheck(session=session) is False

    async def test_returns_false_when_disabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_settings(monkeypatch, rir2localdb_enabled=False)
        assert await healthcheck() is False

    async def test_raises_on_500(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_settings(monkeypatch)
        session = _make_session_mock(500, "")
        with pytest.raises(RIRUnreachable):
            await healthcheck(session=session)

    async def test_raises_on_timeout(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_settings(monkeypatch)
        session = _make_session_raising(TimeoutError())
        with pytest.raises(RIRUnreachable):
            await healthcheck(session=session)

    async def test_raises_on_network_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_settings(monkeypatch)
        session = _make_session_raising(aiohttp.ClientConnectionError("refused"))
        with pytest.raises(RIRUnreachable):
            await healthcheck(session=session)


# ---------------------------------------------------------------------------
# get_status
# ---------------------------------------------------------------------------


_STATUS_OK_BODY: dict[str, Any] = {
    "latest_sync_run": {
        "id": 5,
        "tier": "core",
        "started_at": "2026-05-18T17:39:39.339261Z",
        "finished_at": "2026-05-18T17:39:43.941291Z",
        "status": "success",
        "stats": {"duration_ms": 4650, "files_total": 5},
        "error": None,
    },
    "sources": [
        {
            "url": "https://ftp.ripe.net/pub/stats/ripencc/delegated-ripencc-extended-latest",
            "rir": "ripencc",
            "kind": "delegated",
            "last_status": "unchanged",
            "last_fetched_at": "2026-05-18T17:39:43.933472Z",
            "last_parsed_at": "2026-05-18T11:06:06.261994Z",
            "last_size": 17847204,
        }
    ],
    "db_alive": True,
}


@pytest.mark.asyncio
class TestGetStatus:
    async def test_success_with_latest_sync_run(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_settings(monkeypatch)
        session = _make_session_mock(200, _STATUS_OK_BODY)
        status = await get_status(session=session)
        assert status.db_alive is True
        assert status.latest_sync_run is not None
        assert status.latest_sync_run.status == "success"
        assert status.latest_sync_run.id == 5
        assert len(status.sources) == 1
        assert status.sources[0].rir == "ripencc"

    async def test_success_without_sync_run(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_settings(monkeypatch)
        body = {"latest_sync_run": None, "sources": [], "db_alive": True}
        session = _make_session_mock(200, body)
        status = await get_status(session=session)
        assert status.latest_sync_run is None
        assert status.sources == []

    async def test_disabled_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_settings(monkeypatch, rir2localdb_enabled=False)
        with pytest.raises(RIRUnreachable):
            await get_status()

    async def test_500_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_settings(monkeypatch)
        session = _make_session_mock(500, "")
        with pytest.raises(RIRUnreachable):
            await get_status(session=session)

    async def test_invalid_json_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_settings(monkeypatch)
        broken = {"db_alive": "not a bool"}  # схема не валидируется
        session = _make_session_mock(200, broken)
        with pytest.raises(RIRUnreachable):
            await get_status(session=session)

    async def test_timeout_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_settings(monkeypatch)
        session = _make_session_raising(TimeoutError())
        with pytest.raises(RIRUnreachable):
            await get_status(session=session)
