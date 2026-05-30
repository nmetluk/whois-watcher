"""Тесты парсера crt.sh ответов (TASK-0023, ADR 037)."""

from __future__ import annotations

from src.subdomains.parser import parse_crtsh_response


class TestParseCrtShResponse:
    """Тесты функции parse_crtsh_response."""

    def test_empty_response(self) -> None:
        """Пустой ответ → пустой список."""
        result = parse_crtsh_response("example.com", [])
        assert result == []

    def test_single_subdomain(self) -> None:
        """Один поддомен → список с одним элементом."""
        response = [{"name_value": "www.example.com"}]
        result = parse_crtsh_response("example.com", response)
        assert result == ["www.example.com"]

    def test_multiline_name_value(self) -> None:
        """Многострочное name_value (разделено \\n) → разворачивается."""
        response = [{"name_value": "www.example.com\\nmail.example.com\\napi.example.com"}]
        result = parse_crtsh_response("example.com", response)
        assert result == ["api.example.com", "mail.example.com", "www.example.com"]

    def test_dedup(self) -> None:
        """Дубликаты удаляются."""
        response = [
            {"name_value": "www.example.com\\nmail.example.com"},
            {"name_value": "www.example.com\\napi.example.com"},
        ]
        result = parse_crtsh_response("example.com", response)
        assert result == ["api.example.com", "mail.example.com", "www.example.com"]

    def test_lowercase(self) -> None:
        """Все домены приводятся к lowercase."""
        response = [{"name_value": "WWW.Example.Com\\nMail.EXAMPLE.COM"}]
        result = parse_crtsh_response("example.com", response)
        assert result == ["mail.example.com", "www.example.com"]

    def test_wildcard_filtered(self) -> None:
        """Wildcard-записи (*.example.com) отбрасываются."""
        response = [{"name_value": "*.example.com\\nwww.example.com"}]
        result = parse_crtsh_response("example.com", response)
        assert result == ["www.example.com"]

    def test_registrable_excluded(self) -> None:
        """Сам registrable домен не включается в результат."""
        response = [{"name_value": "example.com\\nwww.example.com"}]
        result = parse_crtsh_response("example.com", response)
        assert result == ["www.example.com"]

    def test_only_subdomains_of_registrable(self) -> None:
        """Только поддомены запрошенного registrable."""
        response = [
            {"name_value": "www.example.com"},
            {"name_value": "mail.another.com"},  # чужой домен
            {"name_value": "api.example.com"},
        ]
        result = parse_crtsh_response("example.com", response)
        assert result == ["api.example.com", "www.example.com"]

    def test_punycode_idn(self) -> None:
        """IDN-домены конвертируются в punycode."""
        response = [{"name_value": "www.пример.рф\\nmail.пример.рф"}]
        result = parse_crtsh_response("xn--e1afmkfd.xn--p1ai", response)
        # В ASCII punycode
        assert "www.xn--e1afmkfd.xn--p1ai" in result
        assert "mail.xn--e1afmkfd.xn--p1ai" in result

    def test_missing_name_value(self) -> None:
        """Отсутствие name_value игнорируется."""
        response = [{"name_value": "www.example.com"}, {}]
        result = parse_crtsh_response("example.com", response)
        assert result == ["www.example.com"]

    def test_empty_name_value(self) -> None:
        """Пустая строка name_value игнорируется."""
        response = [{"name_value": ""}, {"name_value": "www.example.com"}]
        result = parse_crtsh_response("example.com", response)
        assert result == ["www.example.com"]

    def test_multiple_entries_sorted(self) -> None:
        """Результат сортируется."""
        response = [
            {"name_value": "zebra.example.com"},
            {"name_value": "alpha.example.com"},
            {"name_value": "beta.example.com"},
        ]
        result = parse_crtsh_response("example.com", response)
        assert result == ["alpha.example.com", "beta.example.com", "zebra.example.com"]

    def test_subdomain_of_subdomain(self) -> None:
        """Поддомены поддоменов включаются (api.v1.example.com)."""
        response = [{"name_value": "api.v1.example.com\\nwww.example.com"}]
        result = parse_crtsh_response("example.com", response)
        assert result == ["api.v1.example.com", "www.example.com"]

    def test_deeply_nested_subdomain(self) -> None:
        """Глубоко вложенные поддомены включаются."""
        response = [{"name_value": "a.b.c.d.example.com"}]
        result = parse_crtsh_response("example.com", response)
        assert result == ["a.b.c.d.example.com"]


class TestIsSubdomainOf:
    """Тесты вспомогательной функции _is_subdomain_of."""

    def test_exact_match_not_subdomain(self) -> None:
        """Точное совпадение не считается поддоменом."""
        from src.subdomains.parser import _is_subdomain_of

        result = _is_subdomain_of("example.com", "example.com")
        assert result is False

    def test_direct_subdomain(self) -> None:
        """Прямой поддомен."""
        from src.subdomains.parser import _is_subdomain_of

        result = _is_subdomain_of("www.example.com", "example.com")
        assert result is True

    def test_deep_subdomain(self) -> None:
        """Глубокий поддомен."""
        from src.subdomains.parser import _is_subdomain_of

        result = _is_subdomain_of("api.v1.example.com", "example.com")
        assert result is True

    def test_different_domain(self) -> None:
        """Чужой домен."""
        from src.subdomains.parser import _is_subdomain_of

        result = _is_subdomain_of("www.another.com", "example.com")
        assert result is False

    def test_case_insensitive(self) -> None:
        """Проверка регистронезависимая."""
        from src.subdomains.parser import _is_subdomain_of

        result = _is_subdomain_of("WWW.Example.Com", "example.com")
        assert result is True
