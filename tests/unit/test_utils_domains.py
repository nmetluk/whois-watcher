"""Тесты ``src.utils.domains`` — PSL и разбор доменов."""

from __future__ import annotations

import idna
import pytest

from src.utils.domains import (
    DomainParts,
    is_public_suffix_only,
    is_subdomain,
    registrable_domain,
    split_domain,
)


class TestSplitDomain:
    @pytest.mark.parametrize(
        ("domain", "expected"),
        [
            # Простой домен
            ("example.com", DomainParts(subdomain="", registrable="example.com", suffix="com")),
            # Поддомен
            (
                "www.example.com",
                DomainParts(subdomain="www", registrable="example.com", suffix="com"),
            ),
            # Многоуровневый поддомен
            (
                "a.b.example.com",
                DomainParts(subdomain="a.b", registrable="example.com", suffix="com"),
            ),
            # ccTLD с двухуровневым суффиксом (co.uk)
            (
                "example.co.uk",
                DomainParts(subdomain="", registrable="example.co.uk", suffix="co.uk"),
            ),
            (
                "www.example.co.uk",
                DomainParts(subdomain="www", registrable="example.co.uk", suffix="co.uk"),
            ),
            (
                "a.b.foo.co.uk",
                DomainParts(subdomain="a.b", registrable="foo.co.uk", suffix="co.uk"),
            ),
            # org.uk
            (
                "example.org.uk",
                DomainParts(subdomain="", registrable="example.org.uk", suffix="org.uk"),
            ),
            # Комнаты.com (кириллица)
            (
                "пример.рф",
                DomainParts(subdomain="", registrable="xn--e1afmkfd.xn--p1ai", suffix="xn--p1ai"),
            ),
            (
                "www.пример.рф",
                DomainParts(
                    subdomain="www", registrable="xn--e1afmkfd.xn--p1ai", suffix="xn--p1ai"
                ),
            ),
            # Верхний регистр
            ("EXAMPLE.COM", DomainParts(subdomain="", registrable="example.com", suffix="com")),
            (
                "WWW.EXAMPLE.COM",
                DomainParts(subdomain="www", registrable="example.com", suffix="com"),
            ),
        ],
    )
    def test_split_domain(self, domain: str, expected: DomainParts) -> None:
        assert split_domain(domain) == expected

    def test_invalid_domain_raises(self) -> None:
        with pytest.raises(idna.IDNAError):
            split_domain("")


class TestRegistrableDomain:
    @pytest.mark.parametrize(
        ("domain", "expected"),
        [
            # Поддомен → registrable
            ("a.pinbetting.ru", "pinbetting.ru"),
            ("www.pinbetting.ru", "pinbetting.ru"),
            ("a.b.pinbetting.ru", "pinbetting.ru"),
            # Уже registrable → сам
            ("pinbetting.ru", "pinbetting.ru"),
            ("example.com", "example.com"),
            # Многоуровневые TLD
            ("a.b.foo.co.uk", "foo.co.uk"),
            ("foo.co.uk", "foo.co.uk"),
            ("foo.org.uk", "foo.org.uk"),
            # IDN
            ("www.пример.рф", "xn--e1afmkfd.xn--p1ai"),
            ("пример.рф", "xn--e1afmkfd.xn--p1ai"),
            # Публичный суффикс → пустая строка
            ("co.uk", ""),
            ("org.uk", ""),
            ("ru", ""),
            ("com", ""),
        ],
    )
    def test_registrable_domain(self, domain: str, expected: str) -> None:
        assert registrable_domain(domain) == expected


class TestIsSubdomain:
    @pytest.mark.parametrize(
        ("domain", "expected"),
        [
            # Поддомены → True
            ("www.foo.org.uk", True),
            ("a.pinbetting.ru", True),
            ("b.a.pinbetting.ru", True),
            ("www.example.com", True),
            ("a.b.example.com", True),
            # Registrable-домены → False
            ("foo.org.uk", False),
            ("pinbetting.ru", False),
            ("example.com", False),
            ("foo.co.uk", False),
            # Публичные суффиксы → False
            ("co.uk", False),
            ("org.uk", False),
            ("ru", False),
            ("com", False),
        ],
    )
    def test_is_subdomain(self, domain: str, expected: bool) -> None:
        assert is_subdomain(domain) == expected


class TestIsPublicSuffixOnly:
    @pytest.mark.parametrize(
        ("domain", "expected"),
        [
            # Публичные суффиксы → True
            ("co.uk", True),
            ("org.uk", True),
            ("ru", True),
            ("com", True),
            ("net", True),
            ("org", True),
            ("gov.uk", True),
            ("ac.uk", True),
            # Registrable-домены → False
            ("pinbetting.ru", False),
            ("example.com", False),
            ("foo.co.uk", False),
            ("foo.org.uk", False),
            # Поддомены → False
            ("www.example.com", False),
            ("a.pinbetting.ru", False),
        ],
    )
    def test_is_public_suffix_only(self, domain: str, expected: bool) -> None:
        assert is_public_suffix_only(domain) == expected


class TestOfflineMode:
    """Проверка, что tldextract не ходит в сеть."""

    def test_no_network_calls(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Блокируем все сетевые вызовы — если tldextract попытается
        # сходить в сеть, тест упадёт с явным исключением.
        def _blocking_socket(*args: object, **kwargs: object) -> None:
            raise RuntimeError("Network call blocked: tldextract must use bundled snapshot")

        monkeypatch.setattr("socket.socket", _blocking_socket)
        monkeypatch.setattr("socket.getaddrinfo", _blocking_socket)

        # Функции должны работать на bundled snapshot без сети.
        assert registrable_domain("example.com") == "example.com"
        assert is_subdomain("www.example.com")
        assert not is_public_suffix_only("example.com")

    def test_bundled_snapshot_used(self) -> None:
        # Проверяем, что PSL-данные доступны из bundled snapshot.
        # co.uk — публичный суффикс в PSL.
        assert is_public_suffix_only("co.uk")
        # example.co.uk должен считаться registrable.
        assert registrable_domain("example.co.uk") == "example.co.uk"
