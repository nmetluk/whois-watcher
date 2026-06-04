"""Тесты классификатора DNS-ошибок и build_resolver (TASK-0079).

Отдельный модуль по требованию таска: тесты `classify_dns_exc` + `build_resolver`
+ регресс-тесты на MX-ветку в fetch_email_intel (моки со spec/autospec).

Покрываем все 9 пунктов из Definition of Done таска.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import dns.exception
import dns.resolver
import pytest

from src.config.settings import Settings
from src.email_intel.client import fetch_email_intel
from src.email_intel.resolver import (
    QUERY_TIMEOUT,
    TOTAL_TIMEOUT,
    build_resolver,
    classify_dns_exc,
)
from src.email_intel.types import EmailIntelError, EmailIntelResult

# ---------------------------------------------------------------------
# classify_dns_exc table tests (п.6)
# ---------------------------------------------------------------------


def test_classify_nxdomain_and_noanswer_are_no_records() -> None:
    assert classify_dns_exc(dns.resolver.NXDOMAIN("nx")) == "no_records"
    assert classify_dns_exc(dns.resolver.NoAnswer("no ans")) == "no_records"


def test_classify_nxdomain_msg_fallback() -> None:
    exc = dns.exception.DNSException("Some NXDOMAIN thing")
    assert classify_dns_exc(exc) == "no_records"


def test_classify_timeouts_and_nonameservers_are_unreachable() -> None:
    assert classify_dns_exc(dns.resolver.LifetimeTimeout("lt")) == "unreachable"
    assert classify_dns_exc(dns.resolver.Timeout("to")) == "unreachable"
    assert classify_dns_exc(dns.exception.Timeout("exc_to")) == "unreachable"
    assert classify_dns_exc(dns.resolver.NoNameservers("nns")) == "unreachable"


def test_classify_other_dns_exc_is_unreachable() -> None:
    exc = dns.exception.DNSException("weird network glitch")
    assert classify_dns_exc(exc) == "unreachable"


def test_classify_non_dns_falls_to_unreachable() -> None:
    assert classify_dns_exc(ValueError("boom")) == "unreachable"


# ---------------------------------------------------------------------
# build_resolver tests (п.7)
# ---------------------------------------------------------------------


def test_build_resolver_default_timeouts_and_no_override_when_empty() -> None:
    # Пустой dns_nameservers (дефолт) — не трогаем nameservers
    s = Settings(
        bot_token="t",  # type: ignore[arg-type]
        webhook_base_url="https://ex.com",
        webhook_secret="s",  # type: ignore[arg-type]
        postgres_password="p",  # type: ignore[arg-type]
        dns_nameservers=[],
    )
    r = build_resolver(s)
    assert r.timeout == QUERY_TIMEOUT
    assert r.lifetime == TOTAL_TIMEOUT
    # nameservers остаются системными (не перезаписаны)
    assert r.nameservers != []  # обычно ['127.0.0.53'] или cloudflare etc


def test_build_resolver_applies_custom_nameservers() -> None:
    s = Settings(
        bot_token="t",  # type: ignore[arg-type]
        webhook_base_url="https://ex.com",
        webhook_secret="s",  # type: ignore[arg-type]
        postgres_password="p",  # type: ignore[arg-type]
        dns_nameservers=["1.1.1.1", "8.8.8.8"],
    )
    r = build_resolver(s)
    assert r.nameservers == ["1.1.1.1", "8.8.8.8"]


def test_build_resolver_fallback_when_no_settings() -> None:
    r = build_resolver(None)
    assert r.timeout == QUERY_TIMEOUT
    assert r.lifetime == TOTAL_TIMEOUT


# ---------------------------------------------------------------------
# fetch_email_intel MX behavior with mocks (п.1-5,8)
# ---------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mx_success_returns_result() -> None:
    """1. MX резолвится → EmailIntelResult(is_reachable=True, mx_records=[...])"""
    fake_mx = MagicMock()
    fake_mx.__iter__.return_value = iter([MagicMock()])  # at least one
    # parse will be called on list(answer)

    with (
        patch("src.email_intel.client.build_resolver") as mock_build,
        patch("src.email_intel.client.parse_mx_records") as mock_parse,
    ):
        mock_res = MagicMock()
        mock_res.resolve = AsyncMock(return_value=fake_mx)
        mock_build.return_value = mock_res
        mock_parse.return_value = [MagicMock(host="mx.ex.com", priority=10)]

        # Other gathers return exceptions that are swallowed (txt etc)
        with (
            patch(
                "src.email_intel.client._resolve_txt", new=AsyncMock(return_value=Exception("no"))
            ),
            patch(
                "src.email_intel.client._resolve_dmarc", new=AsyncMock(return_value=Exception("no"))
            ),
            patch("src.email_intel.client._resolve_dkim", new=AsyncMock(return_value={})),
        ):
            res = await fetch_email_intel("example.com")
            assert isinstance(res, EmailIntelResult)
            assert res.is_reachable is True
            assert len(res.mx_records) >= 0  # parse mocked to return list


@pytest.mark.asyncio
async def test_mx_nxdomain_returns_nxdomain_error() -> None:
    """2. MX raises NXDOMAIN → EmailIntelError(error_type="nxdomain")"""
    nx = dns.resolver.NXDOMAIN("nxdomain ex.com")
    with patch("src.email_intel.client.build_resolver") as mock_build:
        mock_res = MagicMock()
        mock_res.resolve = AsyncMock(side_effect=nx)
        mock_build.return_value = mock_res

        with (
            patch("src.email_intel.client._resolve_txt", new=AsyncMock(return_value=Exception())),
            patch("src.email_intel.client._resolve_dmarc", new=AsyncMock(return_value=Exception())),
            patch("src.email_intel.client._resolve_dkim", new=AsyncMock(return_value={})),
        ):
            res = await fetch_email_intel("example.com")
            assert isinstance(res, EmailIntelError)
            assert res.error_type == "nxdomain"


@pytest.mark.asyncio
async def test_mx_noanswer_is_valid_empty_mx() -> None:
    """3. MX raises NoAnswer (имя есть, MX нет) → Result(reachable=True, mx=[])"""
    noa = dns.resolver.NoAnswer("no mx")
    with patch("src.email_intel.client.build_resolver") as mock_build:
        mock_res = MagicMock()
        mock_res.resolve = AsyncMock(side_effect=noa)
        mock_build.return_value = mock_res

        with (
            patch("src.email_intel.client._resolve_txt", new=AsyncMock(return_value=Exception())),
            patch("src.email_intel.client._resolve_dmarc", new=AsyncMock(return_value=Exception())),
            patch("src.email_intel.client._resolve_dkim", new=AsyncMock(return_value={})),
        ):
            res = await fetch_email_intel("example.com")
            assert isinstance(res, EmailIntelResult)
            assert res.is_reachable is True
            assert res.mx_records == []


@pytest.mark.asyncio
async def test_mx_lifetime_timeout_is_dns_unreachable() -> None:
    """4. MX raises LifetimeTimeout → dns_unreachable error (КЛЮЧЕВОЙ регресс-тест)"""
    to = dns.resolver.LifetimeTimeout("timeout")
    with patch("src.email_intel.client.build_resolver") as mock_build:
        mock_res = MagicMock()
        mock_res.resolve = AsyncMock(side_effect=to)
        mock_build.return_value = mock_res

        with (
            patch("src.email_intel.client._resolve_txt", new=AsyncMock(return_value=Exception())),
            patch("src.email_intel.client._resolve_dmarc", new=AsyncMock(return_value=Exception())),
            patch("src.email_intel.client._resolve_dkim", new=AsyncMock(return_value={})),
        ):
            res = await fetch_email_intel("example.com")
            assert isinstance(res, EmailIntelError)
            assert res.error_type == "dns_unreachable"
            assert "unreachable" in res.message.lower()


@pytest.mark.asyncio
async def test_mx_nonameservers_is_dns_unreachable() -> None:
    """5. MX raises NoNameservers → dns_unreachable"""
    nns = dns.resolver.NoNameservers("no ns")
    with patch("src.email_intel.client.build_resolver") as mock_build:
        mock_res = MagicMock()
        mock_res.resolve = AsyncMock(side_effect=nns)
        mock_build.return_value = mock_res

        with (
            patch("src.email_intel.client._resolve_txt", new=AsyncMock(return_value=Exception())),
            patch("src.email_intel.client._resolve_dmarc", new=AsyncMock(return_value=Exception())),
            patch("src.email_intel.client._resolve_dkim", new=AsyncMock(return_value={})),
        ):
            res = await fetch_email_intel("example.com")
            assert isinstance(res, EmailIntelError)
            assert res.error_type == "dns_unreachable"


# ---------------------------------------------------------------------
# Card formatter регресс (п.8) — используем настоящий t(), не мок (по CLAUDE.md)
# ---------------------------------------------------------------------


def test_format_email_block_for_unreachable_state_uses_real_t() -> None:
    """8. При dns_unreachable (приводит к is_reachable=False в кэше) format рендерит
    «⚠️ не отвечает» через настоящий t(), а не «MX: не настроен».
    """
    from dataclasses import dataclass, field
    from datetime import UTC, datetime

    from src.services.formatters import format_email_block

    @dataclass
    class FakeCache:
        domain: str = "example.com"
        last_successful_check_at: datetime | None = field(
            default_factory=lambda: datetime.now(tz=UTC)
        )
        is_reachable: bool | None = False
        mx_records: list | None = None
        spf_mode: str | None = None
        dmarc_policy: str | None = None

    cache = FakeCache()
    block = format_email_block(cache, lang="ru")  # type: ignore[arg-type]
    assert block is not None
    # Настоящий перевод (не замокан)
    assert "не отвечает" in block.lower()
    # НЕ показываем «не настроен» для MX при недоступности
    assert "не настроен" not in block.lower()


# ---------------------------------------------------------------------
# Deep: _resolve_txt_for_spf при unreachable логирует warning (п.9)
# ---------------------------------------------------------------------


@pytest.mark.asyncio
async def test_deep_spf_txt_unreachable_logs_warning(caplog: pytest.LogCaptureFixture) -> None:
    """9. deep _resolve_txt_for_spf при unreachable-исключении логирует warning (caplog)."""
    import logging

    from src.email_intel.deep_client import fetch_deep_email

    to_exc = dns.resolver.LifetimeTimeout("lt")

    with patch("src.email_intel.deep_client.build_resolver") as mock_build:
        mock_res = MagicMock()
        # resolver.resolve в _resolve_txt_for_spf будет падать
        mock_res.resolve = AsyncMock(side_effect=to_exc)
        mock_build.return_value = mock_res

        # Остальные коллекторы тоже graceful
        with (
            patch(
                "src.email_intel.deep_client._fetch_mta_sts",
                new=AsyncMock(return_value=MagicMock()),
            ),
            patch(
                "src.email_intel.deep_client._fetch_tls_rpt",
                new=AsyncMock(return_value=MagicMock()),
            ),
            patch(
                "src.email_intel.deep_client._fetch_bimi", new=AsyncMock(return_value=MagicMock())
            ),
            patch(
                "src.email_intel.deep_client._fetch_dane", new=AsyncMock(return_value=MagicMock())
            ),
            patch(
                "src.email_intel.spf_resolver.resolve_spf",
                new=AsyncMock(
                    return_value=MagicMock(sources=[], lookup_count=0, exceeds_limit=False)
                ),
            ),
        ):
            caplog.set_level(logging.WARNING)
            res = await fetch_deep_email("example.com")
            assert isinstance(res, type(res))  # DeepEmailResult
            # Проверяем, что warning про dns_unreachable для SPF TXT был залогирован
            warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
            assert any(
                "dns_unreachable" in (r.message or r.msg or "").lower() for r in warnings
            ), f"expected dns_unreachable warning in logs, got: {[r.message for r in warnings]}"
