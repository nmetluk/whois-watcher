"""Тесты выбора WHOIS-сервера в ``src.whois.whois_protocol.query_whois``.

Сетевые операции (``_query``, ``_resolve_via_iana``) мокаются — проверяем
только логику маршрутизации запроса по TLD/override/mapping/IANA.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.whois import whois_protocol


@pytest.fixture
def captured(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    """Перехватывает ``_query``: запоминает host, возвращает фейковый ответ."""
    seen: dict[str, object] = {}

    async def fake_query(*, host: str, query: str, timeout: float) -> str:
        seen["host"] = host
        seen["query"] = query
        seen["timeout"] = timeout
        return "fake-response"

    monkeypatch.setattr(whois_protocol, "_query", fake_query)
    return seen


class TestQueryWhoisServerSelection:
    async def test_default_mapping_used_when_no_explicit_server(
        self, captured: dict[str, object]
    ) -> None:
        result = await whois_protocol.query_whois("yandex.ru", timeout=5.0)
        assert result == "fake-response"
        assert captured["host"] == whois_protocol.WHOIS_SERVERS["ru"]
        assert captured["query"] == "yandex.ru"

    async def test_explicit_server_overrides_default_mapping(
        self, captured: dict[str, object]
    ) -> None:
        await whois_protocol.query_whois(
            "yandex.ru",
            server="whois.explicit.example",
            timeout=5.0,
        )
        assert captured["host"] == "whois.explicit.example"

    async def test_lookup_is_case_insensitive_for_domain_tld(
        self, captured: dict[str, object]
    ) -> None:
        # TLD домена приходит в любом регистре — _tld_of приводит к lowercase.
        await whois_protocol.query_whois("Example.RU", timeout=5.0)
        assert captured["host"] == whois_protocol.WHOIS_SERVERS["ru"]


class TestQueryWhoisIanaDiscovery:
    async def test_unknown_tld_without_override_consults_iana(
        self,
        captured: dict[str, object],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        iana_mock = AsyncMock(return_value="whois.discovered.example")
        monkeypatch.setattr(whois_protocol, "_resolve_via_iana", iana_mock)

        await whois_protocol.query_whois("domain.exotic", timeout=5.0)

        iana_mock.assert_awaited_once()
        assert captured["host"] == "whois.discovered.example"

    async def test_unknown_tld_iana_failure_raises(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        async def iana_returns_none(domain: str, *, timeout: float) -> str | None:
            return None

        monkeypatch.setattr(whois_protocol, "_resolve_via_iana", iana_returns_none)

        with pytest.raises(whois_protocol.WhoisProtocolError, match="No WHOIS server"):
            await whois_protocol.query_whois("domain.exotic", timeout=5.0)


class TestResolveViaIana:
    """Юнит-тесты для ``_resolve_via_iana`` (gTLD ``refer:``, ccTLD ``whois:``)."""

    async def test_parses_refer_line(self, monkeypatch: pytest.MonkeyPatch) -> None:
        async def fake_query(*, host: str, query: str, timeout: float) -> str:
            del host, query, timeout
            return (
                "% IANA WHOIS server\n"
                "% for more information on IANA, visit http://www.iana.org\n"
                "\n"
                "refer:        whois.nic.info\n"
                "domain:       INFO\n"
            )

        monkeypatch.setattr(whois_protocol, "_query", fake_query)
        result = await whois_protocol._resolve_via_iana("foo.info", timeout=10.0)
        assert result == "whois.nic.info"

    async def test_parses_whois_line_for_ccTLD(  # — phrasing matches doc
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """ccTLD (.us) IANA отдаёт через ``whois:``, а не ``refer:``."""

        async def fake_query(*, host: str, query: str, timeout: float) -> str:
            del host, query, timeout
            return (
                "% IANA WHOIS server\n"
                "domain:       US\n"
                "organisation: NeuStar, Inc.\n"
                "nserver:      A.CCTLD.US\n"
                "\n"
                "whois:        whois.nic.us\n"
                "\n"
                "status:       ACTIVE\n"
                "source:       IANA\n"
            )

        monkeypatch.setattr(whois_protocol, "_query", fake_query)
        result = await whois_protocol._resolve_via_iana("example.us", timeout=10.0)
        assert result == "whois.nic.us"

    async def test_refer_takes_precedence_over_whois(self, monkeypatch: pytest.MonkeyPatch) -> None:
        async def fake_query(*, host: str, query: str, timeout: float) -> str:
            del host, query, timeout
            return "refer: whois.preferred.example\nwhois: whois.other.example\n"

        monkeypatch.setattr(whois_protocol, "_query", fake_query)
        result = await whois_protocol._resolve_via_iana("foo.bar", timeout=10.0)
        assert result == "whois.preferred.example"

    async def test_no_match_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        async def fake_query(*, host: str, query: str, timeout: float) -> str:
            del host, query, timeout
            return "% IANA WHOIS server\n% nothing useful here\n"

        monkeypatch.setattr(whois_protocol, "_query", fake_query)
        result = await whois_protocol._resolve_via_iana("foo.bar", timeout=10.0)
        assert result is None

    async def test_iana_timeout_is_capped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """IANA discovery не должна ждать дольше 5 секунд."""
        captured: dict[str, float] = {}

        async def fake_query(*, host: str, query: str, timeout: float) -> str:
            captured["timeout"] = timeout
            return "refer: whois.nic.test\n"

        monkeypatch.setattr(whois_protocol, "_query", fake_query)
        # Передаём «глобальные» 30 секунд — но IANA-таймаут должен быть 5.
        await whois_protocol._resolve_via_iana("foo.bar", timeout=30.0)
        assert captured["timeout"] == 5.0

    async def test_protocol_error_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        async def fake_query(*, host: str, query: str, timeout: float) -> str:
            del host, query, timeout
            raise whois_protocol.WhoisProtocolError("network down")

        monkeypatch.setattr(whois_protocol, "_query", fake_query)
        result = await whois_protocol._resolve_via_iana("foo.bar", timeout=10.0)
        assert result is None


class TestReferralFollowing:
    """Тесты ``follow_referral=True`` — второй запрос к серверу регистратора."""

    async def test_no_referral_returns_thin_response(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Один запрос: ответ без "Registrar WHOIS Server" → возвращаем как есть.
        calls: list[str] = []

        async def fake_query(*, host: str, query: str, timeout: float) -> str:
            calls.append(host)
            return "Domain Name: example.com\nRegistrar: Verisign\n"

        monkeypatch.setattr(whois_protocol, "_query", fake_query)
        out = await whois_protocol.query_whois("example.com", timeout=5.0, follow_referral=True)
        assert "Domain Name" in out
        assert calls == [whois_protocol.WHOIS_SERVERS["com"]]

    async def test_referral_triggers_second_query(self, monkeypatch: pytest.MonkeyPatch) -> None:
        thin = (
            "Domain Name: telegram.org\n"
            "Registrar WHOIS Server: whois.markmonitor.com\n"
            "Registrar: MarkMonitor Inc.\n"
        )
        thick = (
            "Domain Name: telegram.org\n"
            "Registrar: MarkMonitor Inc.\n"
            "Creation Date: 1999-09-15T07:00:00Z\n"
            "Registry Expiry Date: 2030-09-15T07:00:00Z\n"
            "Name Server: NS1.STEALTH.NET\n"
        )
        calls: list[str] = []

        async def fake_query(*, host: str, query: str, timeout: float) -> str:
            calls.append(host)
            return thick if host == "whois.markmonitor.com" else thin

        monkeypatch.setattr(whois_protocol, "_query", fake_query)
        out = await whois_protocol.query_whois("telegram.org", timeout=5.0, follow_referral=True)
        # Получили thick-ответ
        assert "Registry Expiry Date" in out
        # Делали два запроса: сначала pir.org (для .org), потом MarkMonitor
        assert len(calls) == 2
        assert calls[1] == "whois.markmonitor.com"

    async def test_referral_to_same_host_skipped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Если referral указывает на тот же сервер — не делаем второй запрос."""
        host_used = whois_protocol.WHOIS_SERVERS["org"]
        response = f"Domain Name: example.org\nRegistrar WHOIS Server: {host_used}\n"
        calls: list[str] = []

        async def fake_query(*, host: str, query: str, timeout: float) -> str:
            calls.append(host)
            return response

        monkeypatch.setattr(whois_protocol, "_query", fake_query)
        await whois_protocol.query_whois("example.org", timeout=5.0, follow_referral=True)
        assert len(calls) == 1

    async def test_referral_failure_returns_thin_response(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Если referral-сервер упал — возвращаем thin-ответ без падения."""
        thin = "Domain Name: example.com\nRegistrar WHOIS Server: whois.broken.example\n"

        async def fake_query(*, host: str, query: str, timeout: float) -> str:
            if host == "whois.broken.example":
                raise whois_protocol.WhoisProtocolError("connect refused")
            return thin

        monkeypatch.setattr(whois_protocol, "_query", fake_query)
        out = await whois_protocol.query_whois("example.com", timeout=5.0, follow_referral=True)
        # Получили thin-ответ — не падаем
        assert "Registrar WHOIS Server" in out

    async def test_follow_referral_false_skips_second_query(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        thin = "Domain Name: example.com\nRegistrar WHOIS Server: whois.markmonitor.com\n"
        calls: list[str] = []

        async def fake_query(*, host: str, query: str, timeout: float) -> str:
            calls.append(host)
            return thin

        monkeypatch.setattr(whois_protocol, "_query", fake_query)
        # follow_referral по умолчанию False — второго запроса нет
        await whois_protocol.query_whois("example.com", timeout=5.0)
        assert len(calls) == 1
