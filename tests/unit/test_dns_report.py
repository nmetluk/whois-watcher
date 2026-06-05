"""Тесты DNS-отчёта (ADR 044, TASK-0090).

Форматтер — на синтетических DnsReportResult (чистая функция).
TXT-извлечение в client — через реальные dnspython rdata (урок TASK-0089:
не мокать несуществующий API).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import dns.rdata
import pytest
from aiogram import Bot

from src.dns_report.client import _rdata_to_str
from src.dns_report.formatter import format_dns_report
from src.dns_report.types import DnsRecord, DnsReportResult


def _result(**kw: object) -> DnsReportResult:
    base = DnsReportResult(domain="example.com", unicode_domain="example.com")
    for k, v in kw.items():
        setattr(base, k, v)
    return base


def test_txt_via_real_rdata_not_to_unicode() -> None:
    """TXT-значение берётся через txt_to_str (rdata.strings), не to_unicode."""
    r = dns.rdata.from_text("IN", "TXT", '"v=spf1 -all"')
    assert _rdata_to_str("TXT", r) == "v=spf1 -all"
    assert not hasattr(r, "to_unicode")  # тот самый инцидент 0089


def test_a_record_to_text() -> None:
    r = dns.rdata.from_text("IN", "A", "93.184.216.34")
    assert _rdata_to_str("A", r) == "93.184.216.34"


def test_format_groups_by_type_in_order() -> None:
    res = _result(
        records=[
            DnsRecord("TXT", "example.com", "v=spf1 -all", 300),
            DnsRecord("A", "example.com", "1.2.3.4", 300),
            DnsRecord("NS", "example.com", "ns1.example.com.", 3600),
            DnsRecord("MX", "example.com", "10 mail.example.com.", 3600),
        ],
        dnssec=True,
        axfr_open=False,
    )
    out = format_dns_report(res)
    # секции идут в SECTION_ORDER: NS раньше A раньше MX раньше TXT
    assert out.index("NS —") < out.index("A —") < out.index("MX —") < out.index("TXT —")
    assert "DNSSEC:   да" in out
    assert "AXFR:     закрыт" in out
    assert "Всего записей: 4" in out
    assert "ttl=300" in out


def test_format_axfr_open_is_flagged() -> None:
    res = _result(
        records=[DnsRecord("NS", "example.com", "ns1.example.com.", 3600)],
        axfr_open=True,
        axfr_detail="ns1 (1.2.3.4) → зона передана, 42 rrset",
    )
    out = format_dns_report(res)
    assert "ОТКРЫТ ТРАНСФЕР ЗОНЫ" in out
    assert "42 rrset" in out


def test_format_ptr_arrow_layout() -> None:
    res = _result(records=[DnsRecord("PTR", "1.2.3.4", "host.example.net")])
    out = format_dns_report(res)
    assert "1.2.3.4" in out
    assert "→ host.example.net" in out


def test_format_lists_missing_types() -> None:
    res = _result(records=[DnsRecord("A", "example.com", "1.2.3.4", 300)])
    out = format_dns_report(res)
    assert "Не найдено записей типов" in out
    assert "MX" in out  # MX отсутствует → перечислен как missing


def test_format_errors_section() -> None:
    res = _result(
        records=[DnsRecord("A", "example.com", "1.2.3.4", 300)],
        errors={"SRV": "timeout"},
    )
    out = format_dns_report(res)
    assert "Ошибки резолва" in out
    assert "SRV: timeout" in out


def test_unicode_domain_shows_ascii_line() -> None:
    res = DnsReportResult(domain="xn--e1afmkfd.xn--p1ai", unicode_domain="пример.рф")
    out = format_dns_report(res)
    assert "пример.рф" in out
    assert "xn--e1afmkfd.xn--p1ai" in out


# ── ARQ-задача check_dns_report (wiring) ────────────────────────────


@pytest.mark.asyncio
async def test_task_success_sends_document() -> None:
    from src.tasks.check_dns_report import check_dns_report

    bot = AsyncMock(spec=Bot)
    ctx = {"sync_redis": AsyncMock(), "bot": bot}
    ctx["sync_redis"].set = AsyncMock(return_value=True)

    res = _result(records=[DnsRecord("A", "example.com", "1.2.3.4", 300)])
    with patch("src.tasks.check_dns_report.fetch_dns_report", AsyncMock(return_value=res)):
        out = await check_dns_report(ctx, "example.com", deliver_chat_id=555, deliver_lang="ru")

    assert out["status"] == "success"
    bot.send_document.assert_awaited_once()
    assert bot.send_document.await_args.args[0] == 555


@pytest.mark.asyncio
async def test_task_error_sends_failure_notice_not_document() -> None:
    from src.dns_report.types import DnsReportError
    from src.tasks.check_dns_report import check_dns_report

    bot = AsyncMock(spec=Bot)
    ctx = {"sync_redis": AsyncMock(), "bot": bot}
    ctx["sync_redis"].set = AsyncMock(return_value=True)

    err = DnsReportError(domain="example.com", error_type="unreachable", message="dead")
    with patch("src.tasks.check_dns_report.fetch_dns_report", AsyncMock(return_value=err)):
        out = await check_dns_report(ctx, "example.com", deliver_chat_id=555, deliver_lang="ru")

    assert out["status"] == "error"
    bot.send_document.assert_not_awaited()
    bot.send_message.assert_awaited_once()  # «⚠️ Не удалось…» (TASK-0086)


@pytest.mark.asyncio
async def test_task_in_progress_guard() -> None:
    from src.tasks.check_dns_report import check_dns_report

    ctx = {"sync_redis": AsyncMock(), "bot": AsyncMock(spec=Bot)}
    ctx["sync_redis"].set = AsyncMock(return_value=None)  # уже идёт
    out = await check_dns_report(ctx, "example.com", deliver_chat_id=1)
    assert out["status"] == "already_in_progress"
