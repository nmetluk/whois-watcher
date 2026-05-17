"""Тесты ``src.ssl.diff``: определение значимых изменений SSL-сертификата."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from src.ssl.diff import compute_ssl_diff
from src.ssl.types import SSLCertificate, SSLError


def _cert(
    *,
    domain: str = "example.com",
    is_reachable: bool = True,
    has_certificate: bool = True,
    not_after: datetime | None = None,
    issuer_cn: str | None = "R3",
    issuer_o: str | None = "Let's Encrypt",
    fingerprint: str | None = "abc",
) -> SSLCertificate:
    return SSLCertificate(
        domain=domain,
        is_reachable=is_reachable,
        has_certificate=has_certificate,
        not_after=not_after or datetime(2026, 8, 1, tzinfo=UTC),
        issuer_cn=issuer_cn,
        issuer_o=issuer_o,
        fingerprint_sha256=fingerprint,
    )


class TestFirstFetch:
    def test_old_none_returns_empty_diff(self) -> None:
        new = _cert()
        diff = compute_ssl_diff(None, new)
        assert not diff.has_any_changes

    def test_old_has_no_certificate_returns_empty_diff(self) -> None:
        old = _cert(has_certificate=False, not_after=None)
        new = _cert()
        diff = compute_ssl_diff(old, new)
        assert not diff.has_any_changes


class TestReachability:
    def test_became_unreachable_on_tls_failure(self) -> None:
        old = _cert()
        new = SSLError(
            domain="example.com",
            error_type="tls_handshake_failed",
            message="boom",
        )
        diff = compute_ssl_diff(old, new)
        assert diff.became_unreachable
        assert not diff.became_reachable

    def test_no_https_does_not_count_as_unreachable(self) -> None:
        old = _cert()
        new = SSLError(domain="example.com", error_type="no_https", message="…")
        diff = compute_ssl_diff(old, new)
        assert not diff.became_unreachable
        assert not diff.has_any_changes

    def test_became_reachable_after_outage(self) -> None:
        # old: has_certificate=True (старые данные), но is_reachable=False
        old = _cert(is_reachable=False)
        new = _cert(is_reachable=True)
        diff = compute_ssl_diff(old, new)
        assert diff.became_reachable

    def test_still_reachable_no_signal(self) -> None:
        old = _cert(is_reachable=True)
        new = _cert(is_reachable=True)
        diff = compute_ssl_diff(old, new)
        assert not diff.became_reachable
        assert not diff.became_unreachable

    def test_new_has_no_certificate_counts_as_unreachable(self) -> None:
        old = _cert()
        new = _cert(has_certificate=False, not_after=None)
        diff = compute_ssl_diff(old, new)
        assert diff.became_unreachable

    def test_already_unreachable_no_repeat_signal(self) -> None:
        # Прошлая проверка уже зафиксировала недоступность — повторный
        # fail не должен спамить «became_unreachable» снова.
        old = _cert(is_reachable=False)
        new = SSLError(
            domain="example.com",
            error_type="tls_handshake_failed",
            message="still broken",
        )
        diff = compute_ssl_diff(old, new)
        assert not diff.became_unreachable

    def test_already_unreachable_no_cert_no_repeat(self) -> None:
        old = _cert(is_reachable=False)
        new = _cert(is_reachable=False, has_certificate=False, not_after=None)
        diff = compute_ssl_diff(old, new)
        assert not diff.became_unreachable


class TestNotAfterChange:
    def test_same_not_after_no_change(self) -> None:
        same = datetime(2026, 8, 1, tzinfo=UTC)
        diff = compute_ssl_diff(_cert(not_after=same), _cert(not_after=same))
        assert not diff.not_after_changed

    def test_renewed_certificate_detected(self) -> None:
        old = _cert(not_after=datetime(2026, 8, 1, tzinfo=UTC))
        new = _cert(not_after=datetime(2026, 8, 1, tzinfo=UTC) + timedelta(days=90))
        diff = compute_ssl_diff(old, new)
        assert diff.not_after_changed


class TestIssuerChange:
    def test_same_issuer_no_change(self) -> None:
        diff = compute_ssl_diff(_cert(), _cert())
        assert not diff.issuer_changed

    def test_cn_change_only(self) -> None:
        old = _cert(issuer_cn="R3", issuer_o="Let's Encrypt")
        new = _cert(issuer_cn="R10", issuer_o="Let's Encrypt")
        diff = compute_ssl_diff(old, new)
        assert diff.issuer_changed

    def test_organization_change_only(self) -> None:
        old = _cert(issuer_cn="R3", issuer_o="Let's Encrypt")
        new = _cert(issuer_cn="R3", issuer_o="DigiCert")
        diff = compute_ssl_diff(old, new)
        assert diff.issuer_changed

    def test_both_changed(self) -> None:
        old = _cert(issuer_cn="R3", issuer_o="Let's Encrypt")
        new = _cert(issuer_cn="G2", issuer_o="GlobalSign")
        diff = compute_ssl_diff(old, new)
        assert diff.issuer_changed


class TestCombined:
    def test_multiple_signals(self) -> None:
        old = _cert(
            issuer_cn="R3",
            issuer_o="Let's Encrypt",
            not_after=datetime(2026, 8, 1, tzinfo=UTC),
        )
        new = _cert(
            issuer_cn="DigiCert SHA2",
            issuer_o="DigiCert",
            not_after=datetime(2027, 8, 1, tzinfo=UTC),
        )
        diff = compute_ssl_diff(old, new)
        assert diff.issuer_changed
        assert diff.not_after_changed
        assert not diff.became_unreachable
        assert diff.has_any_changes
