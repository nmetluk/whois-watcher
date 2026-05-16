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
    async def test_override_takes_precedence_over_default_mapping(
        self, captured: dict[str, object]
    ) -> None:
        result = await whois_protocol.query_whois(
            "yandex.ru",
            server_overrides={"ru": "whois.pinspb.ru"},
            timeout=5.0,
        )

        assert result == "fake-response"
        assert captured["host"] == "whois.pinspb.ru"
        assert captured["query"] == "yandex.ru"

    async def test_no_override_falls_back_to_default_mapping(
        self, captured: dict[str, object]
    ) -> None:
        await whois_protocol.query_whois(
            "yandex.ru",
            timeout=5.0,
        )

        # Без override используется встроенный mapping (.ru → whois.tcinet.ru)
        assert captured["host"] == whois_protocol.WHOIS_SERVERS["ru"]

    async def test_override_lookup_is_case_insensitive_for_domain_tld(
        self, captured: dict[str, object]
    ) -> None:
        # Ключи overrides — lowercase (нормализуется валидатором Settings).
        # TLD домена приходит в любом регистре — _tld_of приводит к lowercase.
        await whois_protocol.query_whois(
            "Example.RU",
            server_overrides={"ru": "whois.pinspb.ru"},
            timeout=5.0,
        )

        assert captured["host"] == "whois.pinspb.ru"

    async def test_explicit_server_outranks_override(self, captured: dict[str, object]) -> None:
        await whois_protocol.query_whois(
            "yandex.ru",
            server="whois.explicit.example",
            server_overrides={"ru": "whois.pinspb.ru"},
            timeout=5.0,
        )

        # Явный параметр server — высший приоритет
        assert captured["host"] == "whois.explicit.example"

    async def test_override_for_unknown_tld_uses_override(
        self, captured: dict[str, object]
    ) -> None:
        # TLD которого нет ни в WHOIS_SERVERS, ни в IANA — но есть в override
        await whois_protocol.query_whois(
            "domain.exotic",
            server_overrides={"exotic": "whois.exotic.example"},
            timeout=5.0,
        )

        assert captured["host"] == "whois.exotic.example"

    async def test_override_not_matching_tld_falls_back(self, captured: dict[str, object]) -> None:
        # Override на .ru, а домен .com → должен сработать дефолтный mapping
        await whois_protocol.query_whois(
            "example.com",
            server_overrides={"ru": "whois.pinspb.ru"},
            timeout=5.0,
        )

        assert captured["host"] == whois_protocol.WHOIS_SERVERS["com"]


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
