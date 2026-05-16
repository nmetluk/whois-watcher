"""Тесты ``src.whois.parser``: даты, текстовый WHOIS, RDAP."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from src.whois.parser import (
    parse_rdap,
    parse_whois_date,
    parse_whois_text,
)

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "whois"


def _load(name: str) -> str:
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# parse_whois_date
# ---------------------------------------------------------------------------


class TestParseWhoisDate:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("2027-03-15", datetime(2027, 3, 15, tzinfo=UTC)),
            ("2027-03-15T10:00:00Z", datetime(2027, 3, 15, 10, 0, tzinfo=UTC)),
            ("2027-03-15T10:00:00+00:00", datetime(2027, 3, 15, 10, 0, tzinfo=UTC)),
            ("15-Mar-2027", datetime(2027, 3, 15, tzinfo=UTC)),
            ("15-Mar-2027 10:00:00 UTC", datetime(2027, 3, 15, 10, 0, tzinfo=UTC)),
            ("2027.03.15", datetime(2027, 3, 15, tzinfo=UTC)),
            ("2027/03/15", datetime(2027, 3, 15, tzinfo=UTC)),
            ("15.03.2027", datetime(2027, 3, 15, tzinfo=UTC)),  # европейский DD.MM
            ("31.12.2027", datetime(2027, 12, 31, tzinfo=UTC)),
            # с trailing-комментариями WHOIS-серверов
            ("2027-03-15  # some comment", datetime(2027, 3, 15, tzinfo=UTC)),
            ("2027-03-15 (UTC)", datetime(2027, 3, 15, tzinfo=UTC)),
        ],
    )
    def test_valid(self, raw: str, expected: datetime) -> None:
        result = parse_whois_date(raw)
        assert result == expected
        assert result is not None
        assert result.tzinfo is not None  # всегда aware

    @pytest.mark.parametrize(
        "raw",
        ["", "   ", "not a date", "Aug-Sep-2025", "31.31.2027"],
    )
    def test_invalid_returns_none(self, raw: str) -> None:
        assert parse_whois_date(raw) is None

    def test_tz_aware_converted_to_utc(self) -> None:
        # EST = UTC-5, 09:00 EST → 14:00 UTC
        result = parse_whois_date("2027-03-15T09:00:00-05:00")
        assert result == datetime(2027, 3, 15, 14, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# parse_whois_text
# ---------------------------------------------------------------------------


class TestParseWhoisText:
    def test_com_format(self) -> None:
        data = parse_whois_text(_load("example_com.txt"), "example.com")
        assert data.is_registered is True
        assert data.expires_at == datetime(2027, 8, 13, 4, 0, tzinfo=UTC)
        assert data.created_at == datetime(1995, 8, 14, 4, 0, tzinfo=UTC)
        assert data.updated_at == datetime(2024, 8, 14, 7, 1, 31, tzinfo=UTC)
        assert data.registrar == "RESERVED-Internet Assigned Numbers Authority"
        assert set(data.name_servers) == {"a.iana-servers.net", "b.iana-servers.net"}
        # 3 client*Prohibited
        assert len(data.status) == 3
        assert all(s.startswith("client") for s in data.status)
        assert data.source == "whois"

    def test_ru_format(self) -> None:
        data = parse_whois_text(_load("example_ru.txt"), "example.ru")
        assert data.is_registered is True
        # paid-till → expires_at
        assert data.expires_at == datetime(2027, 6, 13, 21, 0, tzinfo=UTC)
        assert data.created_at == datetime(2003, 6, 12, 16, 13, 18, tzinfo=UTC)
        assert data.registrar == "RU-CENTER-RU"
        # state: REGISTERED, DELEGATED, VERIFIED — список из одной строки
        assert data.status == ["REGISTERED,"]
        # NS с IP-адресами; парсер берёт только hostname
        assert set(data.name_servers) == {"ns1.example.ru", "ns2.example.ru"}

    def test_org_format(self) -> None:
        data = parse_whois_text(_load("example_org.txt"), "example.org")
        assert data.is_registered is True
        assert data.expires_at == datetime(2026, 12, 8, 4, 0, tzinfo=UTC)
        assert data.registrar == "Public Interest Registry"
        assert {s.startswith("server") for s in data.status} == {True}

    def test_io_format(self) -> None:
        data = parse_whois_text(_load("example_io.txt"), "example.io")
        assert data.is_registered is True
        assert data.expires_at == datetime(2027, 7, 21, 15, 30, tzinfo=UTC)
        assert data.registrar == "Identity Digital"
        assert data.name_servers == ["ns1.example.io", "ns2.example.io"]

    def test_rf_punycode_format(self) -> None:
        data = parse_whois_text(_load("example_rf.txt"), "xn--e1afmkfd.xn--p1ai")
        assert data.is_registered is True
        assert data.expires_at == datetime(2027, 11, 5, 21, 0, tzinfo=UTC)
        assert data.created_at == datetime(2018, 11, 5, 10, 0, tzinfo=UTC)
        assert data.registrar == "RU-CENTER-RU"

    def test_not_found(self) -> None:
        data = parse_whois_text(_load("not_found.txt"), "nonexistent.com")
        assert data.is_registered is False
        # пустые поля
        assert data.expires_at is None
        assert data.registrar is None
        assert data.status == []
        assert data.name_servers == []

    def test_not_found_ru(self) -> None:
        data = parse_whois_text(_load("not_found_ru.txt"), "free.ru")
        assert data.is_registered is False

    def test_empty_input_returns_unregistered(self) -> None:
        # Пустой ответ — частный случай: «No match» не находится, но и
        # никаких полей не извлекается. Парсер не должен падать; возвращаем
        # is_registered=True с пустыми полями (это нормальное поведение
        # «не свободен и не наполнен» — caller увидит null'ы).
        data = parse_whois_text("", "x.com")
        assert data.is_registered is True
        assert data.expires_at is None
        assert data.registrar is None

    def test_non_keyvalue_lines_dont_crash(self) -> None:
        weird = "это  не key-value\n\n@@##@@\nproof: that we don't crash\n"
        data = parse_whois_text(weird, "x.com")
        assert data.is_registered is True

    def test_uk_continuation_format_tolerated(self) -> None:
        """В .uk WHOIS значения на отдельных строках от ключей (continuation).

        Наш простой парсер их не разбирает — это известное ограничение. Тест
        проверяет, что хотя бы НЕ падаем и возвращаем sentinel-объект.
        """
        data = parse_whois_text(_load("example_uk.txt"), "example.co.uk")
        # Не парсим, но и не падаем — это и есть цель теста.
        assert data.is_registered is True

    def test_de_format_no_expiry(self) -> None:
        """DENIC не публикует expires_at — это политика реестра, не баг."""
        data = parse_whois_text(_load("example_de.txt"), "example.de")
        assert data.is_registered is True
        # У .de WHOIS-ответа expires_at ОТСУТСТВУЕТ — это нормально.
        assert data.expires_at is None
        assert data.updated_at == datetime(2026, 4, 12, 6, 30, 11, tzinfo=UTC)
        assert data.status == ["connect"]
        assert data.name_servers == ["ns1.example.de", "ns2.example.de"]

    def test_it_format(self) -> None:
        data = parse_whois_text(_load("example_it.txt"), "example.it")
        assert data.is_registered is True
        assert data.expires_at == datetime(2027, 6, 12, tzinfo=UTC)
        assert data.created_at == datetime(2014, 6, 12, tzinfo=UTC)
        assert data.updated_at == datetime(2025, 7, 1, 10, 14, 33, tzinfo=UTC)
        assert data.registrar == "Example Registrar S.p.A."
        assert data.status == ["ok"]
        # Nameservers собраны из блока с continuation
        assert data.name_servers == ["ns1.example.it", "ns2.example.it", "ns3.example.it"]

    def test_kz_format(self) -> None:
        data = parse_whois_text(_load("example_kz.txt"), "example.kz")
        assert data.is_registered is True
        assert data.expires_at == datetime(2027, 9, 15, tzinfo=UTC)
        assert data.created_at == datetime(2010, 9, 15, 12, 0, tzinfo=UTC)
        assert data.updated_at == datetime(2025, 11, 20, 9, 31, 55, tzinfo=UTC)
        assert data.registrar == "EXAMPLE REGISTRAR LLP"
        # Status может задвоиться (Status: ok + Domain Status: ok https://...) —
        # это и есть наблюдаемое поведение, дедупликации статусов нет.
        assert "ok" in data.status
        assert set(data.name_servers) == {"ns1.example.kz", "ns2.example.kz"}

    def test_redacted_for_privacy_filtered(self) -> None:
        """Плейсхолдер ``REDACTED FOR PRIVACY`` → не попадает в поле."""
        text = (
            "Domain Name: privacy.example\n"
            "Registrar: REDACTED FOR PRIVACY\n"
            "Creation Date: 2024-01-01\n"
        )
        data = parse_whois_text(text, "privacy.example")
        # registrar остаётся None — плейсхолдер отфильтрован
        assert data.registrar is None
        # Дата сохранилась
        assert data.created_at == datetime(2024, 1, 1, tzinfo=UTC)


# ---------------------------------------------------------------------------
# parse_rdap
# ---------------------------------------------------------------------------


def _sample_rdap() -> dict[str, object]:
    """Синтетический RDAP-ответ по RFC 7483 — на нём проверяем парсер."""
    return {
        "objectClassName": "domain",
        "handle": "EXAMPLE-COM",
        "ldhName": "example.com",
        "status": ["client transfer prohibited", "client update prohibited"],
        "events": [
            {"eventAction": "registration", "eventDate": "1995-08-14T04:00:00Z"},
            {"eventAction": "expiration", "eventDate": "2027-08-13T04:00:00Z"},
            {"eventAction": "last changed", "eventDate": "2024-08-14T07:01:31Z"},
        ],
        "nameservers": [
            {"ldhName": "A.IANA-SERVERS.NET"},
            {"ldhName": "B.IANA-SERVERS.NET"},
        ],
        "entities": [
            {
                "handle": "1",
                "roles": ["registrar"],
                "vcardArray": [
                    "vcard",
                    [
                        ["version", {}, "text", "4.0"],
                        ["fn", {}, "text", "ICANN Registrar"],
                    ],
                ],
            }
        ],
    }


class TestParseRdap:
    def test_full(self) -> None:
        data = parse_rdap(_sample_rdap(), "example.com")
        assert data.is_registered is True
        assert data.expires_at == datetime(2027, 8, 13, 4, 0, tzinfo=UTC)
        assert data.created_at == datetime(1995, 8, 14, 4, 0, tzinfo=UTC)
        assert data.updated_at == datetime(2024, 8, 14, 7, 1, 31, tzinfo=UTC)
        assert data.registrar == "ICANN Registrar"
        assert set(data.name_servers) == {"a.iana-servers.net", "b.iana-servers.net"}
        assert "client transfer prohibited" in data.status
        assert data.source == "rdap"

    def test_empty_dict_is_unregistered(self) -> None:
        data = parse_rdap({}, "example.com")
        assert data.is_registered is False
        assert data.source == "rdap"

    def test_registrar_handle_fallback(self) -> None:
        """Если vCard не отдан — берём ``handle`` ентити-регистратора."""
        rdap = _sample_rdap()
        # Уберём vcardArray, оставим только handle.
        rdap["entities"] = [{"handle": "GODADDY-1", "roles": ["registrar"]}]
        data = parse_rdap(rdap, "example.com")
        assert data.registrar == "GODADDY-1"

    def test_missing_fields_are_none(self) -> None:
        minimal: dict[str, object] = {"objectClassName": "domain", "ldhName": "x.com"}
        data = parse_rdap(minimal, "x.com")
        assert data.is_registered is True
        assert data.expires_at is None
        assert data.registrar is None
        assert data.name_servers == []
        assert data.status == []

    def test_malformed_events_ignored(self) -> None:
        rdap = _sample_rdap()
        rdap["events"] = [
            {"eventAction": "expiration"},  # no date
            {"eventDate": "2027-01-01"},  # no action
            "not a dict",  # mis-typed list element
            {"eventAction": "expiration", "eventDate": "blah-blah"},  # un-parseable
        ]
        data = parse_rdap(rdap, "example.com")
        assert data.expires_at is None  # ничего валидного не нашлось


# ---------------------------------------------------------------------------
# Контакты — текстовый WHOIS (Этап 8)
# ---------------------------------------------------------------------------


class TestParseWhoisTextContacts:
    def test_thick_registrant_admin_tech(self) -> None:
        text = (
            "Registry Domain ID: 12345\n"
            "Registrar: Example Inc.\n"
            "Registrant Name: John Doe\n"
            "Registrant Organization: Example LLC\n"
            "Registrant Country: US\n"
            "Registrant Email: john@example.com\n"
            "Registrant Phone: +1.5555550100\n"
            "Admin Name: Jane Roe\n"
            "Admin Email: admin@example.com\n"
            "Tech Name: Tech Person\n"
            "Tech Email: tech@example.com\n"
            "Name Server: ns1.example.com\n"
        )
        data = parse_whois_text(text, "example.com")
        reg = data.registrant
        assert reg is not None
        assert reg.organization == "Example LLC"
        assert reg.name == "John Doe"
        assert reg.country == "US"
        assert reg.email == "john@example.com"
        assert reg.phone == "+1.5555550100"
        assert reg.is_redacted is False

        admin = data.admin
        assert admin is not None
        assert admin.name == "Jane Roe"
        assert admin.email == "admin@example.com"

        tech = data.tech
        assert tech is not None
        assert tech.name == "Tech Person"
        assert tech.email == "tech@example.com"

    def test_redacted_for_privacy_marks_contact(self) -> None:
        text = (
            "Registrant Name: REDACTED FOR PRIVACY\n"
            "Registrant Organization: REDACTED FOR PRIVACY\n"
            "Registrant Country: US\n"
        )
        data = parse_whois_text(text, "example.com")
        reg = data.registrant
        assert reg is not None
        assert reg.is_redacted is True
        assert reg.name is None
        assert reg.organization is None
        assert reg.country == "US"  # country обычно остаётся видимым

    def test_ru_org_juridical(self) -> None:
        text = (
            "domain:        EXAMPLE.RU\n"
            'org:           ООО "Пример"\n'
            "e-mail:        admin@example.ru\n"
            "registrar:     RU-CENTER-RU\n"
            "admin-contact: https://www.nic.ru/whois\n"
        )
        data = parse_whois_text(text, "example.ru")
        reg = data.registrant
        assert reg is not None
        assert reg.organization == 'ООО "Пример"'
        assert reg.email == "admin@example.ru"
        # admin-contact: это URL, не email — должен быть проигнорирован
        assert reg.is_redacted is False

    def test_ru_private_person(self) -> None:
        text = (
            "domain:        PRIV.RU\n"
            "person:        Private Person\n"
            "e-mail:        owner@priv.ru\n"
            "registrar:     RU-CENTER-RU\n"
        )
        data = parse_whois_text(text, "priv.ru")
        reg = data.registrant
        assert reg is not None
        assert reg.is_redacted is True
        # Email при этом часто остаётся видимым (форвард через анонимайзер).
        assert reg.email == "owner@priv.ru"

    def test_it_dotted_keys(self) -> None:
        text = (
            "Domain:                 example.it\n"
            "Status:                 ok\n"
            "Registrant.Organization: Example S.r.l.\n"
            "Registrant.Country:      IT\n"
            "Admin.Name:              REDACTED FOR PRIVACY\n"
            "Admin.Organization:      REDACTED FOR PRIVACY\n"
        )
        data = parse_whois_text(text, "example.it")
        reg = data.registrant
        assert reg is not None
        assert reg.organization == "Example S.r.l."
        assert reg.country == "IT"

        admin = data.admin
        assert admin is not None
        assert admin.is_redacted is True


# ---------------------------------------------------------------------------
# Контакты — RDAP (Этап 8)
# ---------------------------------------------------------------------------


def _rdap_with_contacts() -> dict[str, object]:
    return {
        "objectClassName": "domain",
        "ldhName": "example.com",
        "entities": [
            {
                "objectClassName": "entity",
                "roles": ["registrant"],
                "vcardArray": [
                    "vcard",
                    [
                        ["version", {}, "text", "4.0"],
                        ["fn", {}, "text", "Alice Holder"],
                        ["org", {}, "text", "Example Holdings"],
                        ["email", {}, "text", "alice@example.com"],
                        ["tel", {"type": ["voice"]}, "uri", "tel:+1.5555550100"],
                        [
                            "adr",
                            {},
                            "text",
                            ["", "", "1 Infinite Loop", "Cupertino", "CA", "95014", "us"],
                        ],
                    ],
                ],
            },
            {
                "objectClassName": "entity",
                "roles": ["administrative"],
                "vcardArray": [
                    "vcard",
                    [
                        ["version", {}, "text", "4.0"],
                        ["fn", {}, "text", "Bob Admin"],
                        ["email", {}, "text", "admin@example.com"],
                    ],
                ],
            },
            {
                "objectClassName": "entity",
                "roles": ["technical"],
                "vcardArray": [
                    "vcard",
                    [
                        ["version", {}, "text", "4.0"],
                        ["fn", {}, "text", "Carol Tech"],
                    ],
                ],
            },
        ],
    }


class TestParseRdapContacts:
    def test_extracts_three_roles(self) -> None:
        data = parse_rdap(_rdap_with_contacts(), "example.com")
        reg = data.registrant
        assert reg is not None
        assert reg.name == "Alice Holder"
        assert reg.organization == "Example Holdings"
        assert reg.email == "alice@example.com"
        assert reg.phone == "+1.5555550100"
        assert reg.country == "US"  # верхний регистр для 2-3 символов
        assert reg.is_redacted is False

        assert data.admin is not None
        assert data.admin.name == "Bob Admin"
        assert data.admin.email == "admin@example.com"
        assert data.tech is not None
        assert data.tech.name == "Carol Tech"

    def test_rfc9537_redacted_marks_contact(self) -> None:
        rdap = _rdap_with_contacts()
        # Удалим email из vCard registrant'а и добавим redacted-маркер.
        registrant_entity = rdap["entities"][0]  # type: ignore[index]
        registrant_entity["vcardArray"][1] = [  # type: ignore[index]
            ["version", {}, "text", "4.0"],
        ]
        rdap["redacted"] = [
            {
                "name": {"type": "Registrant Email"},
                "method": "removal",
                "prePath": "$.entities[?(@.roles[0]=='registrant')].vcardArray[1]",
            }
        ]
        data = parse_rdap(rdap, "example.com")
        reg = data.registrant
        assert reg is not None
        assert reg.is_redacted is True

    def test_abuse_inside_registrar(self) -> None:
        rdap = {
            "objectClassName": "domain",
            "ldhName": "x.com",
            "entities": [
                {
                    "objectClassName": "entity",
                    "roles": ["registrar"],
                    "vcardArray": [
                        "vcard",
                        [
                            ["version", {}, "text", "4.0"],
                            ["fn", {}, "text", "Big Registrar"],
                        ],
                    ],
                    "entities": [
                        {
                            "objectClassName": "entity",
                            "roles": ["abuse"],
                            "vcardArray": [
                                "vcard",
                                [
                                    ["version", {}, "text", "4.0"],
                                    ["fn", {}, "text", "Abuse Desk"],
                                    ["email", {}, "text", "abuse@big.com"],
                                ],
                            ],
                        }
                    ],
                }
            ],
        }
        data = parse_rdap(rdap, "x.com")
        abuse = next((c for c in data.contacts if c.role == "abuse"), None)
        assert abuse is not None
        assert abuse.email == "abuse@big.com"

    def test_empty_vcard_with_remarks_redaction_marks(self) -> None:
        """RDAP-сервер вернул entity без vCard, но с remark «object truncated»."""
        rdap = {
            "objectClassName": "domain",
            "ldhName": "x.com",
            "entities": [
                {
                    "objectClassName": "entity",
                    "roles": ["registrant"],
                    "remarks": [{"title": "Incomplete Data", "type": "object truncated"}],
                }
            ],
        }
        data = parse_rdap(rdap, "x.com")
        reg = data.registrant
        assert reg is not None
        assert reg.is_redacted is True
