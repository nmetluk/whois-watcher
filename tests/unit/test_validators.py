"""Тесты ``src.bot.validators``."""

from __future__ import annotations

import pytest

from src.bot.validators import (
    extract_domain_from_text,
    is_valid_domain,
    looks_like_just_domain,
)


class TestIsValidDomain:
    @pytest.mark.parametrize(
        "domain",
        [
            "example.com",
            "sub.example.com",
            "a.b.c.example.com",
            "example.co.uk",
            "пример.рф",
            "example.museum",
            "x-y.example.com",
            "1domain.com",  # цифра в начале label допустима
        ],
    )
    def test_valid(self, domain: str) -> None:
        assert is_valid_domain(domain)

    @pytest.mark.parametrize(
        "domain",
        [
            "",
            "   ",
            "localhost",  # без точки
            "example",  # без TLD
            "-example.com",  # дефис в начале
            "example-.com",  # дефис в конце label
            "exa mple.com",  # пробел
            "user@example.com",  # email
            "192.168.0.1",  # IPv4
            "2001:db8::1",  # IPv6
            "example.123",  # TLD из цифр
            ".example.com",  # пустой первый label
            "a" * 64 + ".com",  # label > 63
            "co.uk",  # публичный суффикс (PSL)
            "org.uk",  # публичный суффикс (PSL)
            "ru",  # публичный суффикс (PSL)
            "com",  # публичный суффикс (PSL)
        ],
    )
    def test_invalid(self, domain: str) -> None:
        assert not is_valid_domain(domain)

    def test_too_long_total_invalid(self) -> None:
        # 250 ASCII-символов + ".com" → 254, превышает 253.
        long = "a" * 250 + ".com"
        assert not is_valid_domain(long)

    def test_non_string(self) -> None:
        assert not is_valid_domain(None)  # type: ignore[arg-type]


class TestExtractDomainFromText:
    def test_plain_domain(self) -> None:
        assert extract_domain_from_text("example.com") == "example.com"

    def test_url(self) -> None:
        assert extract_domain_from_text("https://example.com/page") == "example.com"

    def test_inside_sentence(self) -> None:
        result = extract_domain_from_text("Привет, проверь example.com для меня")
        assert result == "example.com"

    def test_idn_extracted_as_punycode(self) -> None:
        assert extract_domain_from_text("сайт: пример.рф") == "xn--e1afmkfd.xn--p1ai"

    def test_no_domain_returns_none(self) -> None:
        assert extract_domain_from_text("привет как дела") is None

    def test_empty_returns_none(self) -> None:
        assert extract_domain_from_text("") is None

    def test_email_not_extracted(self) -> None:
        # ``user@example.com`` — это email, валидатор отсечёт целиком;
        # но `example.com` извлечётся как токен в тексте.
        # Это ожидаемое поведение: пользователь, прислав email,
        # получит WHOIS по домену (это разумно).
        assert extract_domain_from_text("user@example.com") == "example.com"


class TestLooksLikeJustDomain:
    @pytest.mark.parametrize(
        "text",
        ["example.com", "пример.рф", "sub.example.co.uk"],
    )
    def test_yes(self, text: str) -> None:
        assert looks_like_just_domain(text)

    @pytest.mark.parametrize(
        "text",
        [
            "",
            "   ",
            "example.com is great",  # есть пробелы
            "https://example.com",  # с протоколом — не "голый" домен
            "проверь example.com",  # фраза
            "не домен",
        ],
    )
    def test_no(self, text: str) -> None:
        assert not looks_like_just_domain(text)
