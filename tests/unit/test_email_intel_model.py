"""Тесты модели EmailIntelCache и новых полей UserDomain (TASK-0015, ADR 036)."""

from __future__ import annotations

from src.db.models import EmailIntelCache, UserDomain


class TestEmailIntelCacheModel:
    """Проверка что модель EmailIntelCache существует и имеет нужные поля."""

    def test_model_exists(self) -> None:
        """Модель EmailIntelCache должна существовать."""
        assert hasattr(EmailIntelCache, "__tablename__")
        assert EmailIntelCache.__tablename__ == "email_intel_cache"

    def test_domain_field_exists(self) -> None:
        """Поле domain (PK) должно существовать."""
        assert hasattr(EmailIntelCache, "domain")

    def test_scheduling_fields_exist(self) -> None:
        """Scheduling-поля должны существовать."""
        assert hasattr(EmailIntelCache, "fetched_at")
        assert hasattr(EmailIntelCache, "last_successful_check_at")
        assert hasattr(EmailIntelCache, "next_check_at")

    def test_reachability_field_exists(self) -> None:
        """Поле is_reachable должно существовать."""
        assert hasattr(EmailIntelCache, "is_reachable")

    def test_mx_fields_exist(self) -> None:
        """MX-поля должны существовать."""
        assert hasattr(EmailIntelCache, "mx_records")

    def test_spf_fields_exist(self) -> None:
        """SPF-поля должны существовать."""
        assert hasattr(EmailIntelCache, "spf_record")
        assert hasattr(EmailIntelCache, "spf_mode")

    def test_dmarc_fields_exist(self) -> None:
        """DMARC-поля должны существовать."""
        assert hasattr(EmailIntelCache, "dmarc_policy")
        assert hasattr(EmailIntelCache, "dmarc_subpolicy")
        assert hasattr(EmailIntelCache, "dmarc_pct")

    def test_dkim_fields_exist(self) -> None:
        """DKIM-поля должны существовать."""
        assert hasattr(EmailIntelCache, "dkim_selectors")

    def test_failure_tracking_fields_exist(self) -> None:
        """Поля для отслеживания ошибок должны существовать."""
        assert hasattr(EmailIntelCache, "fail_count")
        assert hasattr(EmailIntelCache, "last_error")

    def test_model_instantiation(self) -> None:
        """Модель должна создаваться с основными полями."""
        row = EmailIntelCache(
            domain="example.com",
            mx_records=[{"priority": 10, "host": "mail.example.com"}],
            spf_record="v=spf1 include:_spf.google.com ~all",
            spf_mode="softfail",
            dmarc_policy="quarantine",
            dmarc_subpolicy="none",
            dmarc_pct=100,
            dkim_selectors=["google", "smtp"],
        )
        assert row.domain == "example.com"
        assert row.mx_records == [{"priority": 10, "host": "mail.example.com"}]
        assert row.spf_mode == "softfail"
        assert row.dmarc_policy == "quarantine"


class TestUserDomainEmailToggles:
    """Проверка новых toggle'ов для email-intel в UserDomain."""

    def test_track_email_field_exists(self) -> None:
        """Поле track_email должно существовать."""
        assert hasattr(UserDomain, "track_email")

    def test_notify_email_change_field_exists(self) -> None:
        """Поле notify_email_change должно существовать."""
        assert hasattr(UserDomain, "notify_email_change")

    def test_model_instantiation_with_email_toggles(self) -> None:
        """Модель должна создаваться с новыми email toggle'ами."""
        row = UserDomain(
            user_id=1,
            domain="example.com",
            registrable_domain="example.com",
            is_subdomain=False,
            track_email=True,
            notify_email_change=True,
        )
        assert row.track_email is True
        assert row.notify_email_change is True

    def test_email_toggles_can_be_disabled(self) -> None:
        """Email toggle'ы можно отключить."""
        row = UserDomain(
            user_id=1,
            domain="example.com",
            registrable_domain="example.com",
            is_subdomain=False,
            track_email=False,
            notify_email_change=False,
        )
        assert row.track_email is False
        assert row.notify_email_change is False
