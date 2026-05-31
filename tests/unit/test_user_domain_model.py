"""Тесты модели UserDomain с новыми полями registrable_domain/is_subdomain."""

from __future__ import annotations

from src.db.models import User, UserDomain


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


class TestSubdomainMonitorFields:
    """Проверка полей мониторинга поддоменов (ADR 038)."""

    def test_user_subdomain_check_interval_days_exists(self) -> None:
        """У User должно быть поле subdomain_check_interval_days."""
        assert hasattr(User, "subdomain_check_interval_days")

    def test_user_domain_track_subdomains_exists(self) -> None:
        """У UserDomain должно быть поле track_subdomains."""
        assert hasattr(UserDomain, "track_subdomains")

    def test_user_domain_notify_subdomain_new_exists(self) -> None:
        """У UserDomain должно быть поле notify_subdomain_new."""
        assert hasattr(UserDomain, "notify_subdomain_new")

    def test_user_domain_notify_subdomain_removed_exists(self) -> None:
        """У UserDomain должно быть поле notify_subdomain_removed."""
        assert hasattr(UserDomain, "notify_subdomain_removed")

    def test_user_domain_subdomain_check_interval_override_exists(self) -> None:
        """У UserDomain должно быть поле subdomain_check_interval_override."""
        assert hasattr(UserDomain, "subdomain_check_interval_override")

    def test_model_instantiation_with_subdomain_fields(self) -> None:
        """Модель должна создаваться с полями мониторинга поддоменов."""
        row = UserDomain(
            user_id=1,
            domain="example.com",
            registrable_domain="example.com",
            is_subdomain=False,
            track_subdomains=False,  # opt-in, default false
            notify_subdomain_new=True,
            notify_subdomain_removed=True,
            subdomain_check_interval_override=None,
        )
        assert row.track_subdomains is False
        assert row.notify_subdomain_new is True
        assert row.notify_subdomain_removed is True
        assert row.subdomain_check_interval_override is None

    def test_model_instantiation_with_custom_interval(self) -> None:
        """Модель должна поддерживать кастомный интервал проверки."""
        row = UserDomain(
            user_id=1,
            domain="example.com",
            registrable_domain="example.com",
            is_subdomain=False,
            track_subdomains=True,
            subdomain_check_interval_override=14,
        )
        assert row.track_subdomains is True
        assert row.subdomain_check_interval_override == 14
