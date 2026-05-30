"""Тесты модели SubdomainEnumCache (TASK-0022, ADR 037)."""

from __future__ import annotations

from src.db.models import SubdomainEnumCache


class TestSubdomainEnumCacheModel:
    """Проверка что модель SubdomainEnumCache существует и имеет нужные поля."""

    def test_model_exists(self) -> None:
        """Модель SubdomainEnumCache должна существовать."""
        assert hasattr(SubdomainEnumCache, "__tablename__")
        assert SubdomainEnumCache.__tablename__ == "subdomain_enum_cache"

    def test_registrable_domain_field_exists(self) -> None:
        """Поле registrable_domain (PK) должно существовать."""
        assert hasattr(SubdomainEnumCache, "registrable_domain")

    def test_subdomains_field_exists(self) -> None:
        """Поле subdomains (JSONB) должно существовать."""
        assert hasattr(SubdomainEnumCache, "subdomains")

    def test_scheduling_fields_exist(self) -> None:
        """Scheduling-поля должны существовать."""
        assert hasattr(SubdomainEnumCache, "fetched_at")
        assert hasattr(SubdomainEnumCache, "next_check_at")

    def test_reachability_field_exists(self) -> None:
        """Поле is_reachable должно существовать."""
        assert hasattr(SubdomainEnumCache, "is_reachable")

    def test_failure_tracking_fields_exist(self) -> None:
        """Поля для отслеживания ошибок должны существовать."""
        assert hasattr(SubdomainEnumCache, "fail_count")
        assert hasattr(SubdomainEnumCache, "last_error")

    def test_model_instantiation(self) -> None:
        """Модель должна создаваться с основными полями."""
        row = SubdomainEnumCache(
            registrable_domain="example.com",
            subdomains=["www.example.com", "mail.example.com", "api.example.com"],
            fail_count=0,
        )
        assert row.registrable_domain == "example.com"
        assert row.subdomains == ["www.example.com", "mail.example.com", "api.example.com"]
        assert row.fail_count == 0

    def test_model_instantiation_with_all_fields(self) -> None:
        """Модель должна создаваться со всеми полями."""
        row = SubdomainEnumCache(
            registrable_domain="example.com",
            subdomains=["www.example.com", "mail.example.com"],
            is_reachable=True,
            fail_count=0,
            last_error=None,
        )
        assert row.registrable_domain == "example.com"
        assert row.is_reachable is True
        assert row.fail_count == 0
        assert row.last_error is None

    def test_subdomains_can_be_empty(self) -> None:
        """Поле subdomains может быть None (поддомены не найдены)."""
        row = SubdomainEnumCache(
            registrable_domain="example.com",
            subdomains=None,
        )
        assert row.registrable_domain == "example.com"
        assert row.subdomains is None

    def test_repr(self) -> None:
        """__repr__ должен содержать registrable_domain и количество поддоменов."""
        row = SubdomainEnumCache(
            registrable_domain="example.com",
            subdomains=["www.example.com", "mail.example.com"],
        )
        repr_str = repr(row)
        assert "example.com" in repr_str
        assert "2" in repr_str  # количество поддоменов
