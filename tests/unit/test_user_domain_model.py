"""Тесты модели UserDomain с новыми полями registrable_domain/is_subdomain."""

from __future__ import annotations

from src.db.models import UserDomain


class TestUserDomainModel:
    """Проверка что новые поля registrable_domain и is_subdomain существуют."""

    def test_registrable_domain_field_exists(self) -> None:
        """Поле registrable_domain должно существовать в модели."""
        assert hasattr(UserDomain, "registrable_domain")

    def test_is_subdomain_field_exists(self) -> None:
        """Поле is_subdomain должно существовать в модели."""
        assert hasattr(UserDomain, "is_subdomain")

    def test_model_instantiation_with_new_fields(self) -> None:
        """Модель должна создаваться с новыми полями."""
        row = UserDomain(
            user_id=1,
            domain="example.com",
            registrable_domain="example.com",
            is_subdomain=False,
        )
        assert row.domain == "example.com"
        assert row.registrable_domain == "example.com"
        assert row.is_subdomain is False

    def test_model_instantiation_for_subdomain(self) -> None:
        """Модель должна поддерживать поддомены."""
        row = UserDomain(
            user_id=1,
            domain="www.example.com",
            registrable_domain="example.com",
            is_subdomain=True,
        )
        assert row.domain == "www.example.com"
        assert row.registrable_domain == "example.com"
        assert row.is_subdomain is True
