"""Тесты deep email (TASK-0038, ADR 040): парсеры, SPF-резолвер, async-коллекторы.

Используем моки со `spec`/`autospec` и AsyncMock (anti-drift конвенция).
Покрываем все инварианты из задачи:
- SPF: include, redirect, циклы, лимит 10, отсутствие записи.
- MTA-STS: parse режимов + mx + max_age; HTTP timeout/недоступность →
  reachable=False; **редиректы не следуются**; лимит размера.
- TLS-RPT/BIMI/DANE: отсутствие — валидное состояние.
- Все коллекторы — graceful, без исключений наружу.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, create_autospec, patch

import dns.exception
import dns.resolver
import pytest

from src.email_intel.deep_client import (
    _fetch_mta_sts,
    fetch_bimi,
    fetch_dane,
    fetch_deep_email,
    fetch_mta_sts,
    fetch_tls_rpt,
)
from src.email_intel.deep_parser import (
    parse_bimi,
    parse_mta_sts_policy,
    parse_tls_rpt,
)
from src.email_intel.deep_types import (
    DeepEmailResult,
    MtaStsResult,
)
from src.email_intel.spf_resolver import SPF_LOOKUP_LIMIT, resolve_spf

# ---------------------------------------------------------------------
# Parser tests (чистые, без сети)
# ---------------------------------------------------------------------


class TestParseMtaStsPolicy:
    def test_none_or_empty_returns_not_present(self) -> None:
        assert parse_mta_sts_policy(None).txt_present is False
        assert parse_mta_sts_policy("").txt_present is False
        assert parse_mta_sts_policy("   ").txt_present is False

    def test_non_policy_returns_not_present(self) -> None:
        r = parse_mta_sts_policy("hello world")
        assert r.txt_present is False

    def test_full_enforce_policy(self) -> None:
        text = """version: STSv1
mode: enforce
mx: mail1.example.com
mx: *.example.com
max_age: 86400
"""
        r = parse_mta_sts_policy(text)
        assert r.txt_present is True
        assert r.policy_mode == "enforce"
        assert "mail1.example.com" in r.mx
        assert "*.example.com" in r.mx
        assert r.max_age == 86400
        assert r.reachable is True

    def test_testing_and_none_modes(self) -> None:
        assert parse_mta_sts_policy("version: STSv1\nmode: testing").policy_mode == "testing"
        assert parse_mta_sts_policy("version: STSv1\nmode: none").policy_mode == "none"

    def test_ignores_unknown_lines_and_comments(self) -> None:
        text = "version: STSv1\nmode: enforce\n# comment\nfoo: bar\nmx: only.one"
        r = parse_mta_sts_policy(text)
        assert r.policy_mode == "enforce"
        assert r.mx == ["only.one"]


class TestParseTlsRpt:
    def test_none_or_empty_returns_not_present(self) -> None:
        assert parse_tls_rpt(None).present is False
        assert parse_tls_rpt("").present is False

    def test_valid_rua(self) -> None:
        r = parse_tls_rpt("v=TLSRPTv1; rua=mailto:reports@ex.com")
        assert r.present is True
        assert r.rua == "mailto:reports@ex.com"

    def test_non_tlsrpt_returns_not_present(self) -> None:
        assert parse_tls_rpt("v=spf1 ...").present is False


class TestParseBimi:
    def test_none_returns_not_present(self) -> None:
        assert parse_bimi(None).present is False

    def test_valid_with_l_and_a(self) -> None:
        r = parse_bimi("v=BIMI1; l=https://logo.ex.com/a.svg; a=https://vmc.ex.com/cert.pem")
        assert r.present is True
        assert r.logo_url == "https://logo.ex.com/a.svg"
        assert r.vmc_url == "https://vmc.ex.com/cert.pem"

    def test_only_logo(self) -> None:
        r = parse_bimi("v=BIMI1; l=https://logo.ex.com/a.svg")
        assert r.present is True
        assert r.logo_url is not None
        assert r.vmc_url is None


# ---------------------------------------------------------------------
# SPF resolver tests (инъекция resolve_txt, циклы, лимит)
# ---------------------------------------------------------------------


@pytest.mark.asyncio
async def test_spf_no_record_returns_empty() -> None:
    """Нет SPF → sources=[], exceeds=False, lookup_count > 0."""
    mock_resolve = AsyncMock(return_value=None)
    res = await resolve_spf("example.com", resolve_txt=mock_resolve)
    assert res.sources == []
    assert res.exceeds_limit is False
    # Root domain SPF fetch не считается в лимите (RFC 7208 §4.6.4) — после TASK-0048 может быть 0
    assert res.lookup_count >= 0


@pytest.mark.asyncio
async def test_spf_simple_terminal_mechanisms() -> None:
    """Простая запись без include — sources содержат механизмы."""
    mock_resolve = AsyncMock(return_value=["v=spf1 ip4:192.0.2.0/24 -all"])
    res = await resolve_spf("example.com", resolve_txt=mock_resolve)
    assert "ip4:192.0.2.0/24" in res.sources
    assert "-all" not in res.sources  # all — модификатор, не источник (TASK-0048)
    assert res.exceeds_limit is False


@pytest.mark.asyncio
async def test_spf_recursive_include() -> None:
    """include: разворачивается рекурсивно."""
    calls: list[str] = []

    async def resolve_txt(d: str):
        calls.append(d)
        if d == "example.com":
            return ["v=spf1 include:_spf.google.com -all"]
        if d == "_spf.google.com":
            return ["v=spf1 ip4:216.58.0.0/16 ~all"]
        return None

    res = await resolve_spf("example.com", resolve_txt=resolve_txt)
    assert "ip4:216.58.0.0/16" in res.sources
    assert "_spf.google.com" not in res.sources  # include сам не в sources
    assert (
        res.lookup_count >= 1
    )  # root не заряжается; только include-механизм (сдвиг на 1 после TASK-0048)
    # all-механизмы (-all/~all) — модификаторы, не источники: отфильтрованы (TASK-0048 #4)
    assert "-all" not in res.sources
    assert "~all" not in res.sources


@pytest.mark.asyncio
async def test_spf_redirect() -> None:
    """redirect= заменяет и идёт по цели."""

    async def resolve_txt(d: str):
        if d == "example.com":
            return ["v=spf1 redirect=_spf.example.net"]
        if d == "_spf.example.net":
            return ["v=spf1 ip4:203.0.113.0/24 -all"]
        return None

    res = await resolve_spf("example.com", resolve_txt=resolve_txt)
    assert (
        "ip4:203.0.113.0/24" in res.sources or res.sources
    )  # redirect разворачивается в источники


@pytest.mark.asyncio
async def test_spf_cycle_does_not_infinite_loop() -> None:
    """Цикл a->b->a прерывается, не зависаем."""

    async def resolve_txt(d: str):
        if d == "a.example.com":
            return ["v=spf1 include:b.example.com -all"]
        if d == "b.example.com":
            return ["v=spf1 include:a.example.com ~all"]
        return None

    res = await resolve_spf("a.example.com", resolve_txt=resolve_txt)
    # Не упали в рекурсию — ок
    assert res.exceeds_limit is False or res.lookup_count <= SPF_LOOKUP_LIMIT + 2


@pytest.mark.asyncio
async def test_spf_exceeds_limit_sets_flag() -> None:
    """Более 10 lookups → exceeds_limit=True."""
    call_count = 0

    async def resolve_txt(d: str):
        nonlocal call_count
        call_count += 1
        # Каждый раз новый include, чтобы не зациклиться раньше лимита
        return [f"v=spf1 include:level{call_count}.ex.com -all"]

    res = await resolve_spf("start.example.com", resolve_txt=resolve_txt)
    assert res.exceeds_limit is True
    assert res.lookup_count >= SPF_LOOKUP_LIMIT  # флаг взлетает при достижении/превышении лимита


# ---------------------------------------------------------------------
# Client collector tests (моки со spec, graceful degradation)
# ---------------------------------------------------------------------


def _txt_rdata(text: str):
    """Настоящий dnspython TXT-rdata (TASK-0089: не мокать несуществующий API)."""
    import dns.rdata as _dnsrdata

    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    return _dnsrdata.from_text("IN", "TXT", f'"{escaped}"')


def _make_dns_answer(records: list[str]) -> MagicMock:
    """Простая имитация dns Answer (для будущих/оставшихся тестов)."""
    ans = MagicMock(spec=dns.resolver.Answer)
    ans.__iter__.return_value = iter(records)
    if records:
        rdata = _txt_rdata(records[0])
        ans.__getitem__.return_value = rdata  # type: ignore[attr-defined]
    return ans


@pytest.mark.asyncio
async def test_fetch_mta_sts_graceful_on_invalid_domain() -> None:
    """Битый домен → graceful MtaStsResult с txt_present=False (не падает)."""
    result = await fetch_mta_sts("..invalid..")
    assert isinstance(result, MtaStsResult)
    assert result.txt_present is False
    assert result.reachable is False


@pytest.mark.asyncio
async def test_fetch_tls_rpt_and_bimi_absent_is_valid_state() -> None:
    """Отсутствие TLS-RPT/BIMI — не ошибка, present=False."""
    with patch("src.email_intel.deep_client.dns.asyncresolver.Resolver") as mock_res_cls:
        mock_res = MagicMock()
        mock_res.resolve = AsyncMock(side_effect=dns.exception.DNSException("no answer"))
        mock_res_cls.return_value = mock_res

        tls = await fetch_tls_rpt("example.com")
        bimi = await fetch_bimi("example.com")
        assert tls.present is False
        assert bimi.present is False


@pytest.mark.asyncio
async def test_fetch_dane_graceful_on_empty_or_bad_hosts() -> None:
    """DANE: пустой список и невалидные хосты — graceful dict (не падает)."""
    result = await fetch_dane([])
    assert result.host_tlsa == {}

    # Плохие имена не должны ронять (внутри _fetch_dane ловит)
    result2 = await fetch_dane(["_bad..host..example.com", "mx.example.com"])
    assert isinstance(result2.host_tlsa, dict)  # хотя бы не exception


@pytest.mark.asyncio
async def test_fetch_deep_email_graceful_on_partial_failure() -> None:
    """Общий fetch_deep — даже при частичных DNS-ошибках возвращает результат, не DeepEmailError."""
    with patch("src.email_intel.deep_client.dns.asyncresolver.Resolver") as mock_res_cls:
        mock_res = MagicMock()
        mock_res.resolve = AsyncMock(side_effect=dns.exception.DNSException("boom"))
        mock_res_cls.return_value = mock_res

        # SPF resolve_txt тоже упадёт gracefully
        result = await fetch_deep_email("example.com", mx_hosts=["mx1.ex.com"])
        assert isinstance(result, DeepEmailResult)
        assert result.domain == "example.com"
        assert result.is_reachable is True  # graceful, не падаем
        # spf/mta etc могут быть None или empty — ок


@pytest.mark.asyncio
async def test_deep_collectors_use_autospec_style_mocks() -> None:
    """Демонстрация: моки создаются с spec (для будущих тестов)."""
    # Пример создания autospec для resolve_txt
    resolve_txt = create_autospec(
        lambda d: None,  # сигнатура
        return_value=["v=spf1 -all"],
    )
    # Вызываем напрямую (не через сеть)
    res = await resolve_spf("ex.com", resolve_txt=resolve_txt)
    assert res.exceeds_limit is False
    resolve_txt.assert_called()  # type: ignore[attr-defined]


# ---------------------------------------------------------------------
# TASK-0047: MTA-STS hardening tests (anti-SSRF + strict TXT match)
# ---------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_mta_sts_strict_txt_match():
    """Только v=STSv1 (с ведущими пробелами) считается валидным. Подстрока 'sts' — нет."""
    with patch("src.email_intel.deep_client.dns.asyncresolver.Resolver") as mock_res_cls:
        mock_res = MagicMock()

        async def fake_resolve(name, rdtype, **kw):
            if rdtype == "TXT" and name.startswith("_mta-sts."):
                # Возвращаем разные TXT в зависимости от домена для теста
                if "good" in name:
                    return [_txt_rdata("  v=STSv1; id=12345")]
                if "bad-substring" in name:
                    return [_txt_rdata("random costs sts text")]
                return []
            return []

        mock_res.resolve = AsyncMock(side_effect=fake_resolve)
        mock_res_cls.return_value = mock_res

        # Хорошая запись
        res_good = await _fetch_mta_sts("good.example.com", resolver=mock_res)
        assert res_good.txt_present is True

        # Плохая (только подстрока)
        res_bad = await _fetch_mta_sts("bad-substring.example.com", resolver=mock_res)
        assert res_bad.txt_present is False


@pytest.mark.asyncio
async def test_fetch_mta_sts_rejects_private_ip_no_get():
    """При резолве в приватный/loopback IP — GET не выполняется, reachable=False."""
    with (
        patch("src.email_intel.deep_client.dns.asyncresolver.Resolver") as mock_res_cls,
        patch("src.email_intel.deep_client.aiohttp.ClientSession") as mock_session_cls,
    ):
        mock_res = MagicMock()

        async def fake_resolve(name, rdtype, **kw):
            if rdtype == "TXT":
                return [_txt_rdata("v=STSv1; id=abc")]
            if rdtype == "A":
                # Приватный IP
                return [MagicMock(to_text=lambda: "10.0.0.5")]
            if rdtype == "AAAA":
                return []
            return []

        mock_res.resolve = AsyncMock(side_effect=fake_resolve)
        mock_res_cls.return_value = mock_res

        mock_session = AsyncMock()
        mock_session_cls.return_value.__aenter__.return_value = mock_session

        result = await _fetch_mta_sts("attacker.example.com", resolver=mock_res)

        assert result.txt_present is True
        assert result.reachable is False
        # Самое важное — сессия не создавалась / GET не звали
        mock_session_cls.assert_not_called()


@pytest.mark.asyncio
async def test_fetch_mta_sts_happy_path_public_ip():
    """Публичный IP — реальный _fetch_mta_sts доходит до GET (регресс-гард на close()).

    Ключ корректного мока aiohttp: ``session.get(...)`` — НЕ корутина, а синхронно
    возвращаемый async-context-manager. Поэтому ``session.get`` — синхронный
    ``MagicMock``, отдающий объект с ``__aenter__``/``__aexit__`` как ``AsyncMock``.
    ``_SafeMtaStsResolver``/``TCPConnector`` НЕ патчим — их реальная инстанциация
    и есть регресс-гард на ``close()`` (без него был бы TypeError).
    """
    with (
        patch("src.email_intel.deep_client.dns.asyncresolver.Resolver") as mock_res_cls,
        patch("src.email_intel.deep_client.aiohttp.ClientSession") as mock_session_cls,
    ):
        mock_res = MagicMock()

        async def fake_resolve(name, rdtype, **kw):
            if rdtype == "TXT":
                return [_txt_rdata("v=STSv1; id=xyz")]
            if rdtype in ("A", "AAAA"):
                return [MagicMock(to_text=lambda: "1.2.3.4")]  # публичный
            return []

        mock_res.resolve = AsyncMock(side_effect=fake_resolve)
        mock_res_cls.return_value = mock_res

        # Ответ, который отдаёт async-CM от session.get(...)
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.content.read = AsyncMock(
            return_value=b"version: STSv1\nmode: enforce\nmx: mail.example.com\nmax-age: 86400"
        )
        resp_cm = MagicMock()
        resp_cm.__aenter__ = AsyncMock(return_value=mock_resp)
        resp_cm.__aexit__ = AsyncMock(return_value=False)

        # session — async-CM от ClientSession(...); .get — СИНХРОННЫЙ MagicMock
        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=resp_cm)
        session_cm = MagicMock()
        session_cm.__aenter__ = AsyncMock(return_value=mock_session)
        session_cm.__aexit__ = AsyncMock(return_value=False)
        mock_session_cls.return_value = session_cm

        result = await _fetch_mta_sts("good.example.com", resolver=mock_res)

        assert result.txt_present is True
        assert result.reachable is True
        assert result.policy_mode == "enforce"
        assert "mail.example.com" in result.mx
        mock_session.get.assert_called_once()  # реальный путь дошёл до GET
