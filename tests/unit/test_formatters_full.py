"""Тесты ``src.services.formatters_full.format_whois_full_text`` (Этап 8)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from types import SimpleNamespace

from src.services.formatters_full import (
    build_full_text_from_cache_row,
    format_whois_full_text,
)
from src.whois.types import WhoisContact, WhoisData


def _cache_row(**overrides: object) -> SimpleNamespace:
    """Простой stub WhoisCache-row через SimpleNamespace.

    ``_cache_to_data`` обращается к атрибутам через ``getattr``, поэтому
    SimpleNamespace подходит без полноценной ORM.
    """
    base: dict[str, object] = {
        "domain": "example.com",
        "expires_at": datetime(2027, 3, 15, tzinfo=UTC),
        "created_at_registrar": datetime(2020, 1, 1, tzinfo=UTC),
        "updated_at_registrar": datetime(2026, 1, 1, tzinfo=UTC),
        "registrar": "Example Registrar Inc.",
        "status": ["clientTransferProhibited", "ok"],
        "name_servers": ["ns1.example.com", "ns2.example.com"],
        "raw_data": {},
        "registrant_name": None,
        "registrant_org": None,
        "registrant_country": None,
        "registrant_email": None,
        "registrant_is_redacted": False,
        "contacts_data": None,
        "fetched_at": datetime(2026, 5, 16, 12, 0, tzinfo=UTC),
        "last_successful_fetch_at": datetime(2026, 5, 16, 12, 0, tzinfo=UTC),
    }
    base.update(overrides)
    return SimpleNamespace(**base)


# ---------------------------------------------------------------------------
# RDAP-источник
# ---------------------------------------------------------------------------


def _rdap_payload() -> dict[str, object]:
    return {
        "objectClassName": "domain",
        "ldhName": "example.com",
        "events": [
            {"eventAction": "expiration", "eventDate": "2027-03-15T00:00:00Z"},
            {"eventAction": "registration", "eventDate": "2020-01-01T00:00:00Z"},
        ],
        "entities": [
            {
                "roles": ["registrar"],
                "publicIds": [{"type": "IANA Registrar ID", "identifier": "292"}],
                "vcardArray": [
                    "vcard",
                    [
                        ["version", {}, "text", "4.0"],
                        ["fn", {}, "text", "Example Registrar Inc."],
                    ],
                ],
            },
        ],
        "secureDNS": {"delegationSigned": True, "zoneSigned": True},
    }


class TestFormatRdap:
    def test_has_header_and_sections(self) -> None:
        data = WhoisData(
            domain="example.com",
            is_registered=True,
            expires_at=datetime(2027, 3, 15, tzinfo=UTC),
            registrar="Example Registrar Inc.",
            status=["clientTransferProhibited"],
            name_servers=["ns1.example.com"],
            contacts=[
                WhoisContact(
                    role="registrant",
                    organization="Example Holdings",
                    country="US",
                )
            ],
        )
        row = _cache_row(raw_data=_rdap_payload())
        out = format_whois_full_text(data, row, lang="ru")
        assert "WHOIS information for example.com" in out
        assert "Source:    rdap" in out
        assert "[Registration timeline]" in out
        assert "[Registrar]" in out
        assert "[Registrant]" in out
        assert "Organization:   Example Holdings" in out
        assert "Country:        US" in out
        assert "[Status]" in out
        assert "Защищён от трансфера" in out  # переведённый текст
        assert "[Nameservers]" in out
        assert "[DNSSEC]" in out
        assert "Status: signed" in out

    def test_iana_id_extracted(self) -> None:
        data = WhoisData(domain="example.com", is_registered=True)
        row = _cache_row(raw_data=_rdap_payload())
        out = format_whois_full_text(data, row, lang="ru")
        assert "IANA ID:        292" in out

    def test_raw_section_is_pretty_json(self) -> None:
        data = WhoisData(domain="example.com", is_registered=True)
        payload = _rdap_payload()
        row = _cache_row(raw_data=payload)
        out = format_whois_full_text(data, row, lang="ru")
        # Raw-секция должна содержать pretty-printed JSON, не Python repr.
        assert "Raw source data" in out
        raw_section = out.split("Raw source data\n" + "=" * 60)[1]
        # Pretty-printed JSON парсится обратно.
        parsed = json.loads(raw_section.strip())
        assert parsed["objectClassName"] == "domain"
        # Никакого str(dict) с одинарными кавычками.
        assert "'objectClassName':" not in raw_section


# ---------------------------------------------------------------------------
# WHOIS:43-источник
# ---------------------------------------------------------------------------


class TestFormatWhoisText:
    def test_raw_section_is_original_text(self) -> None:
        raw = (
            "   Domain Name: EXAMPLE.COM\n"
            "   Registrar IANA ID: 376\n"
            "   Registrar Abuse Contact Email: abuse@example.com\n"
            "   DNSSEC: signedDelegation\n"
            ">>> Last update of whois database: 2026-05-15T10:23:11Z <<<\n"
        )
        data = WhoisData(
            domain="example.com",
            is_registered=True,
            registrar="Example Registrar Inc.",
            status=["ok"],
        )
        row = _cache_row(raw_data={"raw_text": raw})
        out = format_whois_full_text(data, row, lang="ru")
        assert "Source:    whois (port 43)" in out
        # raw сохранён без модификаций
        assert raw in out
        # iana id и abuse email подтянулись в шапку
        assert "IANA ID:        376" in out
        assert "Abuse contact:  abuse@example.com" in out
        assert "Status: signedDelegation" in out


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_no_contacts_section_says_not_present(self) -> None:
        data = WhoisData(domain="example.com", is_registered=True)
        row = _cache_row(raw_data={"raw_text": "Some: data\n"})
        out = format_whois_full_text(data, row, lang="ru")
        assert "[Registrant]" in out
        assert "(not present in response)" in out

    def test_admin_tech_only_when_present(self) -> None:
        data = WhoisData(
            domain="example.com",
            is_registered=True,
            contacts=[WhoisContact(role="registrant", organization="Org")],
        )
        row = _cache_row(raw_data={"raw_text": ""})
        out = format_whois_full_text(data, row, lang="ru")
        assert "[Admin Contact]" not in out
        assert "[Tech Contact]" not in out

    def test_build_helper_round_trip_from_row(self) -> None:
        """Хэлпер ``build_full_text_from_cache_row`` сам собирает WhoisData."""
        row = _cache_row(
            raw_data={"raw_text": "Some: data\n"},
            registrant_org="Hello LLC",
            registrant_country="DE",
            registrant_is_redacted=False,
        )
        out = build_full_text_from_cache_row(row, lang="ru")
        assert "Organization:   Hello LLC" in out
        assert "Country:        DE" in out
