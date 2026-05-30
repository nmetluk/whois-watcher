"""Тесты UX для поддоменов (TASK-0005).

Проверяем:

- /whois поддомена показывает баннер и карточку родителя
- /list помечает поддомены значком ↳
- Публичный суффикс отклоняется валидатором
"""

from __future__ import annotations

from datetime import UTC, datetime

from src.db.models import UserDomain, WhoisCache
from src.services.formatters import format_list_row
from src.utils.domains import is_public_suffix_only, is_subdomain, split_domain

NOW = datetime(2026, 5, 29, 12, 0, tzinfo=UTC)


class TestPublicSuffixValidation:
    """Проверка, что публичные суффиксы отклоняются."""

    def test_co_uk_is_public_suffix(self) -> None:
        assert is_public_suffix_only("co.uk") is True

    def test_org_uk_is_public_suffix(self) -> None:
        assert is_public_suffix_only("org.uk") is True

    def test_ru_is_public_suffix(self) -> None:
        assert is_public_suffix_only("ru") is True

    def test_plain_domain_is_not_public_suffix(self) -> None:
        assert is_public_suffix_only("example.com") is False

    def test_subdomain_is_not_public_suffix(self) -> None:
        assert is_public_suffix_only("www.example.com") is False

    def test_registrable_domain_is_not_public_suffix(self) -> None:
        assert is_public_suffix_only("example.co.uk") is False


class TestSubdomainDetection:
    """Проверка определения поддоменов."""

    def test_www_is_subdomain(self) -> None:
        assert is_subdomain("www.example.com") is True

    def test_a_pinbetting_ru_is_subdomain(self) -> None:
        assert is_subdomain("a.pinbetting.ru") is True

    def test_apex_is_not_subdomain(self) -> None:
        assert is_subdomain("example.com") is False

    def test_public_suffix_is_not_subdomain(self) -> None:
        assert is_subdomain("co.uk") is False


class TestDomainSplitting:
    """Проверка разбиения домена на компоненты."""

    def test_simple_domain_split(self) -> None:
        parts = split_domain("example.com")
        assert parts.subdomain == ""
        assert parts.registrable == "example.com"
        assert parts.suffix == "com"

    def test_subdomain_split(self) -> None:
        parts = split_domain("www.example.com")
        assert parts.subdomain == "www"
        assert parts.registrable == "example.com"
        assert parts.suffix == "com"

    def test_multi_level_subdomain_split(self) -> None:
        parts = split_domain("a.b.example.com")
        assert parts.subdomain == "a.b"
        assert parts.registrable == "example.com"
        assert parts.suffix == "com"

    def test_co_uk_split(self) -> None:
        parts = split_domain("example.co.uk")
        assert parts.subdomain == ""
        assert parts.registrable == "example.co.uk"
        assert parts.suffix == "co.uk"

    def test_subdomain_co_uk_split(self) -> None:
        parts = split_domain("www.example.co.uk")
        assert parts.subdomain == "www"
        assert parts.registrable == "example.co.uk"
        assert parts.suffix == "co.uk"


class TestListRowSubdomainMark:
    """Проверка пометки поддоменов в /list."""

    def _user_domain(self, domain: str, is_sub: bool = False) -> UserDomain:
        return UserDomain(
            id=1,
            user_id=123,
            domain=domain,
            registrable_domain="example.com",
            is_subdomain=is_sub,
            notify_days=[30, 7, 1],
            notify_expiry=True,
            notify_ns_change=False,
            notify_registrar_change=True,
            notify_status_change=True,
            notify_registrant_change=True,
            notify_problem=True,
            is_muted=False,
            track_ssl=True,
            notify_ssl_expiry=True,
            notify_ssl_change_issuer=True,
            track_dns=True,
            notify_dns_a_change=True,
            notify_dns_aaaa_change=True,
            notify_dns_ns_change=True,
            notify_dns_unreachable=True,
        )

    def _whois_cache(self, expires_at: datetime | None) -> WhoisCache:
        return WhoisCache(
            domain="example.com",
            expires_at=expires_at,
            created_at_registrar=None,
            updated_at_registrar=None,
            registrar="Example Inc.",
            status=None,
            name_servers=None,
            raw_data=None,
            registrant_name=None,
            registrant_org=None,
            registrant_country=None,
            registrant_email=None,
            registrant_is_redacted=False,
            contacts_data=None,
            fetched_at=None,
            last_successful_fetch_at=None,
            next_check_at=None,
            fail_count=0,
            last_error=None,
        )

    def test_apex_domain_no_mark(self) -> None:
        """Apex-домен не помечается значком ↳."""
        user_domain = self._user_domain("example.com", is_sub=False)
        cache = self._whois_cache(datetime(2027, 3, 15, tzinfo=UTC))
        out = format_list_row(user_domain, cache, lang="ru", now=NOW)
        assert "↳" not in out
        assert "example.com —" in out

    def test_subdomain_has_mark(self) -> None:
        """Поддомен помечается значком ↳."""
        user_domain = self._user_domain("www.example.com", is_sub=True)
        cache = self._whois_cache(datetime(2027, 3, 15, tzinfo=UTC))
        out = format_list_row(user_domain, cache, lang="ru", now=NOW)
        assert "↳ www.example.com —" in out

    def test_subdomain_shows_parent_expiry(self) -> None:
        """Поддомен показывает expiry родителя."""
        user_domain = self._user_domain("www.example.com", is_sub=True)
        cache = self._whois_cache(datetime(2027, 3, 15, tzinfo=UTC))
        out = format_list_row(user_domain, cache, lang="ru", now=NOW)
        # Формат даты в локали ru: DD.MM.YYYY
        assert "15.03.2027" in out
        assert "↳" in out

    def test_subdomain_unknown_data(self) -> None:
        """Поддомен без данных помечается значком."""
        user_domain = self._user_domain("www.example.com", is_sub=True)
        cache = self._whois_cache(None)
        out = format_list_row(user_domain, cache, lang="ru", now=NOW)
        assert "↳ www.example.com" in out
        assert "нет данных" in out
