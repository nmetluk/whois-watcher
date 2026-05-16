"""Тесты ``src.services.csv_io`` — экспорт CSV и парсинг файла для импорта."""

from __future__ import annotations

import csv
import io
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from src.config.limits import Limits
from src.services import csv_io
from src.services.csv_io import (
    _CSV_HEADER,
    ParsedFileResult,
    _row_for,
    generate_user_csv,
    parse_domain_file,
)


def _async_cm(value: object) -> MagicMock:
    """``async with``-совместимый объект, возвращающий ``value``."""
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=value)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


# ---------------------------------------------------------------------------
# Экспорт
# ---------------------------------------------------------------------------


def _make_user_domain(
    *,
    domain: str = "example.com",
    notify_expiry: bool = True,
    notify_ns_change: bool = False,
    notify_registrar_change: bool = True,
    notify_status_change: bool = True,
    note: str | None = None,
    added_at: datetime | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        domain=domain,
        notify_expiry=notify_expiry,
        notify_ns_change=notify_ns_change,
        notify_registrar_change=notify_registrar_change,
        notify_status_change=notify_status_change,
        note=note,
        added_at=added_at or datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
    )


def _make_cache(
    *,
    expires_at: datetime | None,
    registrar: str | None = "RU-CENTER",
    status: list[str] | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        expires_at=expires_at,
        registrar=registrar,
        status=status,
    )


class TestRowFor:
    def test_row_with_full_data(self) -> None:
        ud = _make_user_domain(note="my main domain")
        cache = _make_cache(
            expires_at=datetime(2027, 3, 15, tzinfo=UTC),
            registrar="RU-CENTER",
            status=["clientTransferProhibited", "clientUpdateProhibited"],
        )
        now = datetime(2026, 1, 1, tzinfo=UTC)
        row = _row_for(ud, cache, now=now)

        assert row[0] == "example.com"
        assert row[1] == "2027-03-15"
        assert int(row[2]) > 0
        assert row[3] == "RU-CENTER"
        assert row[4] == "clientTransferProhibited, clientUpdateProhibited"
        assert row[5] == "on"
        assert row[6] == "2026-01-01 12:00"
        assert row[7] == "my main domain"

    def test_row_with_no_cache(self) -> None:
        ud = _make_user_domain()
        row = _row_for(ud, None, now=datetime(2026, 1, 1, tzinfo=UTC))
        assert row[1] == ""
        assert row[2] == ""
        assert row[3] == ""
        assert row[4] == ""

    def test_notifications_off_when_all_flags_false(self) -> None:
        ud = _make_user_domain(
            notify_expiry=False,
            notify_ns_change=False,
            notify_registrar_change=False,
            notify_status_change=False,
        )
        row = _row_for(ud, None, now=datetime(2026, 1, 1, tzinfo=UTC))
        assert row[5] == "off"

    def test_domain_decoded_from_punycode(self) -> None:
        ud = _make_user_domain(domain="xn--e1afmkfd.xn--p1ai")
        row = _row_for(ud, None, now=datetime(2026, 1, 1, tzinfo=UTC))
        assert row[0] == "пример.рф"


class TestGenerateUserCsv:
    async def test_csv_has_bom_and_header(self) -> None:
        ud = _make_user_domain()
        cache = _make_cache(expires_at=datetime(2027, 3, 15, tzinfo=UTC))

        with (
            patch.object(csv_io, "get_session") as gs,
            patch.object(csv_io, "DomainRepository") as dr_cls,
        ):
            gs.return_value = _async_cm(MagicMock(name="session"))
            dr_cls.return_value.iter_all_with_whois = AsyncMock(return_value=[(ud, cache)])
            data, count = await generate_user_csv(user_id=1)

        assert count == 1
        text = data.decode("utf-8")
        # UTF-8 BOM
        assert text.startswith("﻿")
        body = text.lstrip("﻿")
        lines = body.splitlines()
        assert lines[0] == ",".join(_CSV_HEADER)
        reader = csv.reader(io.StringIO(body))
        rows = list(reader)
        assert rows[1][0] == "example.com"

    async def test_empty_portfolio(self) -> None:
        with (
            patch.object(csv_io, "get_session") as gs,
            patch.object(csv_io, "DomainRepository") as dr_cls,
        ):
            gs.return_value = _async_cm(MagicMock())
            dr_cls.return_value.iter_all_with_whois = AsyncMock(return_value=[])
            data, count = await generate_user_csv(user_id=42)

        assert count == 0
        # Только BOM + заголовок
        text = data.decode("utf-8").lstrip("﻿")
        assert text.splitlines() == [",".join(_CSV_HEADER)]


# ---------------------------------------------------------------------------
# Импорт
# ---------------------------------------------------------------------------


class TestParseDomainFile:
    def test_empty_content(self) -> None:
        result = parse_domain_file(b"", max_domains=100)
        assert isinstance(result, ParsedFileResult)
        assert result.valid_domains == []
        assert result.invalid_lines == []
        assert result.truncated is False

    def test_txt_basic(self) -> None:
        content = b"example.com\nexample.org\nexample.net\n"
        result = parse_domain_file(content, max_domains=100)
        assert result.valid_domains == ["example.com", "example.org", "example.net"]
        assert result.invalid_lines == []

    def test_skips_comments_and_blanks(self) -> None:
        content = b"# header comment\nexample.com\n\n  \n# another\nexample.org\n"
        result = parse_domain_file(content, max_domains=100)
        assert result.valid_domains == ["example.com", "example.org"]

    def test_strips_url_prefixes(self) -> None:
        content = b"https://example.com/path?x=1\nhttp://example.org:8080/\n"
        result = parse_domain_file(content, max_domains=100)
        assert "example.com" in result.valid_domains
        assert "example.org" in result.valid_domains

    def test_idn_to_punycode(self) -> None:
        content = "пример.рф\n".encode()
        result = parse_domain_file(content, max_domains=100)
        assert result.valid_domains == ["xn--e1afmkfd.xn--p1ai"]

    def test_invalid_lines_captured(self) -> None:
        content = b"example.com\nnot a domain\n@@@\nexample.org\n"
        result = parse_domain_file(content, max_domains=100)
        assert "example.com" in result.valid_domains
        assert "example.org" in result.valid_domains
        assert any("not a domain" in line for line in result.invalid_lines)

    def test_deduplicates_within_file(self) -> None:
        content = b"example.com\nEXAMPLE.com\nhttps://example.com/\n"
        result = parse_domain_file(content, max_domains=100)
        assert result.valid_domains == ["example.com"]

    def test_truncated_at_max(self) -> None:
        domains = [f"example{i}.com" for i in range(20)]
        content = ("\n".join(domains) + "\n").encode()
        result = parse_domain_file(content, max_domains=5)
        assert len(result.valid_domains) == 5
        assert result.truncated is True

    def test_csv_with_header(self) -> None:
        content = b"domain,note\nexample.com,main\nexample.org,backup\n"
        result = parse_domain_file(content, max_domains=100)
        assert result.valid_domains == ["example.com", "example.org"]

    def test_csv_without_header(self) -> None:
        content = b"example.com,note1\nexample.org,note2\n"
        result = parse_domain_file(content, max_domains=100)
        assert result.valid_domains == ["example.com", "example.org"]

    def test_bom_decoded(self) -> None:
        content = "﻿example.com\n".encode()
        result = parse_domain_file(content, max_domains=100)
        assert result.valid_domains == ["example.com"]


def test_default_limits_max_domains_per_download_present() -> None:
    limits = Limits()
    assert limits.max_domains_per_download > 0
