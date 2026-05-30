"""Тесты ``src.email_intel.diff``: сравнение состояний."""

from __future__ import annotations

from datetime import UTC, datetime

from src.email_intel.diff import EmailIntelDiff, compute_email_diff
from src.email_intel.types import (
    DKIMInfo,
    DMARCRecord,
    EmailIntelError,
    EmailIntelResult,
    MXRecord,
    SPFRecord,
)

NOW = datetime(2026, 5, 30, 12, 0, tzinfo=UTC)


class TestComputeEmailDiff:
    def test_none_old_returns_empty_diff(self) -> None:
        """old=None — первая проверка, пустой diff."""
        new = EmailIntelResult(
            domain="example.com",
            is_reachable=True,
            mx_records=[MXRecord(host="mail.example.com", priority=10)],
        )
        diff = compute_email_diff(None, new)
        assert not diff.has_any_changes

    def test_no_changes_returns_empty_diff(self) -> None:
        """Нет изменений — пустой diff."""
        old = EmailIntelResult(
            domain="example.com",
            is_reachable=True,
            mx_records=[MXRecord(host="mail.example.com", priority=10)],
            spf=SPFRecord(raw="v=spf1 -all", mode="fail", is_multiple=False),
            dmarc=DMARCRecord(policy="none"),
            dkim=DKIMInfo(selectors=["google"]),
        )
        new = EmailIntelResult(
            domain="example.com",
            is_reachable=True,
            mx_records=[MXRecord(host="mail.example.com", priority=10)],
            spf=SPFRecord(raw="v=spf1 -all", mode="fail", is_multiple=False),
            dmarc=DMARCRecord(policy="none"),
            dkim=DKIMInfo(selectors=["google"]),
        )
        diff = compute_email_diff(old, new)
        assert not diff.has_any_changes

    def test_mx_added(self) -> None:
        """MX добавились."""
        old = EmailIntelResult(domain="example.com", is_reachable=True, mx_records=[])
        new = EmailIntelResult(
            domain="example.com",
            is_reachable=True,
            mx_records=[MXRecord(host="mail.example.com", priority=10)],
        )
        diff = compute_email_diff(old, new)
        assert diff.mx_changed
        assert diff.has_any_changes

    def test_mx_changed_priority(self) -> None:
        """MX priority изменился."""
        old = EmailIntelResult(
            domain="example.com",
            is_reachable=True,
            mx_records=[MXRecord(host="mail.example.com", priority=10)],
        )
        new = EmailIntelResult(
            domain="example.com",
            is_reachable=True,
            mx_records=[MXRecord(host="mail.example.com", priority=20)],
        )
        diff = compute_email_diff(old, new)
        assert diff.mx_changed

    def test_mx_changed_host(self) -> None:
        """MX host изменился."""
        old = EmailIntelResult(
            domain="example.com",
            is_reachable=True,
            mx_records=[MXRecord(host="mail1.example.com", priority=10)],
        )
        new = EmailIntelResult(
            domain="example.com",
            is_reachable=True,
            mx_records=[MXRecord(host="mail2.example.com", priority=10)],
        )
        diff = compute_email_diff(old, new)
        assert diff.mx_changed

    def test_spf_appeared(self) -> None:
        """SPF появился."""
        old = EmailIntelResult(domain="example.com", is_reachable=True)
        new = EmailIntelResult(
            domain="example.com",
            is_reachable=True,
            spf=SPFRecord(raw="v=spf1 -all", mode="fail", is_multiple=False),
        )
        diff = compute_email_diff(old, new)
        assert diff.spf_changed

    def test_spf_disappeared(self) -> None:
        """SPF исчез."""
        old = EmailIntelResult(
            domain="example.com",
            is_reachable=True,
            spf=SPFRecord(raw="v=spf1 -all", mode="fail", is_multiple=False),
        )
        new = EmailIntelResult(domain="example.com", is_reachable=True)
        diff = compute_email_diff(old, new)
        assert diff.spf_changed

    def test_spf_mode_changed(self) -> None:
        """SPF режим изменился."""
        old = EmailIntelResult(
            domain="example.com",
            is_reachable=True,
            spf=SPFRecord(raw="v=spf1 -all", mode="fail", is_multiple=False),
        )
        new = EmailIntelResult(
            domain="example.com",
            is_reachable=True,
            spf=SPFRecord(raw="v=spf1 ~all", mode="softfail", is_multiple=False),
        )
        diff = compute_email_diff(old, new)
        assert diff.spf_changed

    def test_spf_raw_changed(self) -> None:
        """SPF содержимое изменилось (режим тот же)."""
        old = EmailIntelResult(
            domain="example.com",
            is_reachable=True,
            spf=SPFRecord(raw="v=spf1 a -all", mode="fail", is_multiple=False),
        )
        new = EmailIntelResult(
            domain="example.com",
            is_reachable=True,
            spf=SPFRecord(raw="v=spf1 a mx -all", mode="fail", is_multiple=False),
        )
        diff = compute_email_diff(old, new)
        assert diff.spf_changed

    def test_dmarc_appeared(self) -> None:
        """DMARC появился."""
        old = EmailIntelResult(domain="example.com", is_reachable=True)
        new = EmailIntelResult(
            domain="example.com",
            is_reachable=True,
            dmarc=DMARCRecord(policy="none"),
        )
        diff = compute_email_diff(old, new)
        assert diff.dmarc_changed

    def test_dmarc_policy_changed(self) -> None:
        """DMARC policy изменился."""
        old = EmailIntelResult(
            domain="example.com",
            is_reachable=True,
            dmarc=DMARCRecord(policy="none"),
        )
        new = EmailIntelResult(
            domain="example.com",
            is_reachable=True,
            dmarc=DMARCRecord(policy="quarantine"),
        )
        diff = compute_email_diff(old, new)
        assert diff.dmarc_changed

    def test_dmarc_subpolicy_changed(self) -> None:
        """DMARC subpolicy изменился."""
        old = EmailIntelResult(
            domain="example.com",
            is_reachable=True,
            dmarc=DMARCRecord(policy="none", subpolicy=None),
        )
        new = EmailIntelResult(
            domain="example.com",
            is_reachable=True,
            dmarc=DMARCRecord(policy="none", subpolicy="reject"),
        )
        diff = compute_email_diff(old, new)
        assert diff.dmarc_changed

    def test_dmarc_pct_changed(self) -> None:
        """DMARC pct изменился."""
        old = EmailIntelResult(
            domain="example.com",
            is_reachable=True,
            dmarc=DMARCRecord(policy="none", pct=100),
        )
        new = EmailIntelResult(
            domain="example.com",
            is_reachable=True,
            dmarc=DMARCRecord(policy="none", pct=50),
        )
        diff = compute_email_diff(old, new)
        assert diff.dmarc_changed

    def test_dkim_appeared(self) -> None:
        """DKIM появился."""
        old = EmailIntelResult(domain="example.com", is_reachable=True)
        new = EmailIntelResult(
            domain="example.com",
            is_reachable=True,
            dkim=DKIMInfo(selectors=["google"]),
        )
        diff = compute_email_diff(old, new)
        assert diff.dkim_changed

    def test_dkim_selectors_changed(self) -> None:
        """DKIM селекторы изменились."""
        old = EmailIntelResult(
            domain="example.com",
            is_reachable=True,
            dkim=DKIMInfo(selectors=["google"]),
        )
        new = EmailIntelResult(
            domain="example.com",
            is_reachable=True,
            dkim=DKIMInfo(selectors=["google", "default"]),
        )
        diff = compute_email_diff(old, new)
        assert diff.dkim_changed

    def test_became_unreachable_on_error(self) -> None:
        """Ошибка → became_unreachable (если был reachable)."""
        old = EmailIntelResult(domain="example.com", is_reachable=True)
        new = EmailIntelError(
            domain="example.com",
            error_type="dns_error",
            message="Timeout",
        )
        diff = compute_email_diff(old, new)
        assert diff.became_unreachable
        assert not diff.became_reachable

    def test_no_unreachable_if_already_unreachable(self) -> None:
        """Повторная ошибка — не became_unreachable (только переход)."""
        old = EmailIntelResult(domain="example.com", is_reachable=False)
        new = EmailIntelError(
            domain="example.com",
            error_type="dns_error",
            message="Timeout",
        )
        diff = compute_email_diff(old, new)
        assert not diff.became_unreachable

    def test_nxdomain_not_unreachable(self) -> None:
        """NXDOMAIN — не became_unreachable (это не «сломался», а «не существует»)."""
        old = EmailIntelResult(domain="example.com", is_reachable=True)
        new = EmailIntelError(
            domain="example.com",
            error_type="nxdomain",
            message="NXDOMAIN",
        )
        diff = compute_email_diff(old, new)
        assert not diff.became_unreachable

    def test_became_reachable(self) -> None:
        """Восстановление → became_reachable."""
        old = EmailIntelResult(domain="example.com", is_reachable=False)
        new = EmailIntelResult(domain="example.com", is_reachable=True)
        diff = compute_email_diff(old, new)
        assert diff.became_reachable
        assert not diff.became_unreachable

    def test_multiple_changes(self) -> None:
        """Несколько изменений одновременно."""
        old = EmailIntelResult(
            domain="example.com",
            is_reachable=True,
            mx_records=[],
            spf=SPFRecord(raw="v=spf1 -all", mode="fail", is_multiple=False),
        )
        new = EmailIntelResult(
            domain="example.com",
            is_reachable=True,
            mx_records=[MXRecord(host="mail.example.com", priority=10)],
            spf=SPFRecord(raw="v=spf1 ~all", mode="softfail", is_multiple=False),
        )
        diff = compute_email_diff(old, new)
        assert diff.mx_changed
        assert diff.spf_changed
        assert diff.has_any_changes


def test_email_diff_has_any_changes() -> None:
    """has_any_changes работает корректно."""
    diff = EmailIntelDiff()
    assert not diff.has_any_changes

    diff.mx_changed = True
    assert diff.has_any_changes
