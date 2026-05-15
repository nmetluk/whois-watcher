"""Тесты ``src.utils.idn``."""

from __future__ import annotations

import idna
import pytest

from src.utils.idn import from_punycode, normalize_domain, to_punycode


class TestToPunycode:
    def test_ascii_lowercase_passthrough(self) -> None:
        assert to_punycode("example.com") == "example.com"

    def test_ascii_uppercase_normalized(self) -> None:
        assert to_punycode("Example.COM") == "example.com"

    def test_idn_cyrillic(self) -> None:
        assert to_punycode("пример.рф") == "xn--e1afmkfd.xn--p1ai"

    def test_idn_german(self) -> None:
        # Шарфес ес → punycode
        assert to_punycode("straße.de") == "xn--strae-oqa.de"

    def test_empty_raises(self) -> None:
        with pytest.raises(idna.IDNAError):
            to_punycode("")


class TestFromPunycode:
    def test_decode_cyrillic(self) -> None:
        assert from_punycode("xn--e1afmkfd.xn--p1ai") == "пример.рф"

    def test_ascii_passthrough(self) -> None:
        assert from_punycode("example.com") == "example.com"

    def test_invalid_returns_original(self) -> None:
        # На невалидном вводе — возвращаем как есть, не падаем.
        assert from_punycode("xn--invalid--") == "xn--invalid--"


class TestNormalizeDomain:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("example.com", "example.com"),
            ("Example.COM", "example.com"),
            ("  example.com  ", "example.com"),
            ("https://example.com", "example.com"),
            ("http://example.com/path/to/page", "example.com"),
            ("https://example.com:8080/path?q=1", "example.com"),
            ("example.com.", "example.com"),  # trailing dot
            ("example.com/", "example.com"),
            ("ftp://example.com#anchor", "example.com"),
        ],
    )
    def test_basic_normalization(self, raw: str, expected: str) -> None:
        assert normalize_domain(raw) == expected

    def test_idn_normalized_to_punycode(self) -> None:
        assert normalize_domain("Пример.РФ") == "xn--e1afmkfd.xn--p1ai"

    def test_strip_www_flag(self) -> None:
        assert normalize_domain("www.example.com", strip_www=True) == "example.com"
        assert normalize_domain("www.example.com") == "www.example.com"

    def test_empty_input_raises(self) -> None:
        with pytest.raises((idna.IDNAError, ValueError)):
            normalize_domain("")

    def test_only_scheme_raises(self) -> None:
        with pytest.raises((idna.IDNAError, ValueError)):
            normalize_domain("https://")

    def test_port_only_digits_stripped(self) -> None:
        assert normalize_domain("example.com:80") == "example.com"

    def test_non_digit_after_colon_kept_as_part(self) -> None:
        # ``example.com:abc`` — не порт; idna такое не примет, должна быть ошибка.
        with pytest.raises((idna.IDNAError, ValueError, UnicodeError)):
            normalize_domain("example.com:abc")
