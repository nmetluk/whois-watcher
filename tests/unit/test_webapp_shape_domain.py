"""Тесты _shape_domain с РЕАЛЬНЫМИ ORM-моделями (без MagicMock).

Урок инцидента 2026-06-05: _shape_domain обращался к несуществующим полям
EmailIntelCache (email.mx вместо mx_records и т.д.) → AttributeError → 500
на /portfolio, /domain/{id}, /dashboard. WebApp показывал demo-fallback
вместо реальных доменов. Тестов на шейпер не было.

Правило (CLAUDE.md anti-drift): шейперы/форматтеры тестируем на реальных
инстансах моделей — голый MagicMock отдаёт любой атрибут и маскирует дрейф.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from src.bot.webapp.api import _shape_domain
from src.db.models import DNSCache, EmailIntelCache, SSLCache, UserDomain, WhoisCache

NOW = datetime(2026, 6, 5, 12, 0, tzinfo=UTC)


def _ud(**kw: Any) -> UserDomain:
    defaults: dict[str, Any] = {
        "id": 1,
        "user_id": 1,
        "domain": "example.com",
        "registrable_domain": "example.com",
        "note": None,
        "notify_expiry": True,
        "notify_ns_change": True,
        "notify_registrar_change": True,
        "notify_status_change": True,
        "added_at": NOW - timedelta(days=30),
    }
    defaults.update(kw)
    return UserDomain(**defaults)


def _whois(**kw: Any) -> WhoisCache:
    defaults: dict[str, Any] = {
        "domain": "example.com",
        "registrar": "Example Registrar",
        "expires_at": NOW + timedelta(days=90),
        "created_at_registrar": NOW - timedelta(days=365),
        "updated_at_registrar": NOW - timedelta(days=10),
        "status": ["clientTransferProhibited"],
        "fetched_at": NOW - timedelta(hours=1),
    }
    defaults.update(kw)
    return WhoisCache(**defaults)


def test_shape_domain_minimal_no_caches() -> None:
    """Без кэшей: noData, без падений."""
    obj = _shape_domain(_ud(), None, None, None, None, 0, now=NOW)
    assert obj["noData"] is True
    assert obj["email"] is None
    assert obj["ssl"] is None
    assert obj["dns"] is None
    assert obj["name"] == "example.com"


def test_shape_domain_with_real_email_intel_cache() -> None:
    """Регрессия инцидента: реальный EmailIntelCache не должен ронять шейпер."""
    email = EmailIntelCache(
        domain="example.com",
        mx_records=[{"priority": 10, "host": "mail.example.com"}],
        spf_record="v=spf1 include:_spf.example.com -all",
        spf_mode="fail",
        dmarc_policy="quarantine",
        dmarc_subpolicy=None,
        dmarc_pct=100,
        dkim_selectors=["default", "google"],
    )
    obj = _shape_domain(_ud(), _whois(), None, None, email, 2, now=NOW)
    assert obj["email"] == {
        "mx": "mail.example.com",
        "hasMX": True,
        "spf": True,
        "dkim": True,
        "dmarc": "quarantine",
    }
    assert obj["daysLeft"] == 90
    assert obj["registrar"] == "Example Registrar"


def test_shape_domain_email_cache_empty_records() -> None:
    """Пустая строка email-кэша (домен без почты) — корректные False/None."""
    email = EmailIntelCache(domain="example.com")
    obj = _shape_domain(_ud(), _whois(), None, None, email, 0, now=NOW)
    assert obj["email"] == {
        "mx": None,
        "hasMX": False,
        "spf": False,
        "dkim": False,
        "dmarc": None,
    }


def test_shape_domain_with_real_ssl_and_dns_caches() -> None:
    """SSL/DNS-ветки шейпера тоже на реальных моделях."""
    ssl = SSLCache(
        domain="example.com",
        has_certificate=True,
        not_after=NOW + timedelta(days=60),
        issuer_cn="R11",
        issuer_o="Let's Encrypt",
    )
    dns = DNSCache(
        domain="example.com",
        a_records=["93.184.216.34"],
        aaaa_records=[],
        ns_records=["a.iana-servers.net", "b.iana-servers.net"],
        asn_set=[15133],
    )
    obj = _shape_domain(_ud(), _whois(), ssl, dns, None, 0, now=NOW)
    assert obj["ssl"]["issuer"] == "R11"
    assert obj["ssl"]["daysLeft"] == 60
    assert obj["dns"]["a"] == ["93.184.216.34"]
    assert obj["dns"]["asn"] == 15133
