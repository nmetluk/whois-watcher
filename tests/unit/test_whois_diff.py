"""Тесты ``src.whois.diff.compute_diff``."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from src.whois.diff import compute_diff
from src.whois.types import WhoisData


def _data(
    *,
    expires_at: datetime | None = None,
    registrar: str | None = None,
    status: list[str] | None = None,
    name_servers: list[str] | None = None,
) -> WhoisData:
    return WhoisData(
        domain="example.com",
        is_registered=True,
        expires_at=expires_at,
        registrar=registrar,
        status=status or [],
        name_servers=name_servers or [],
    )


class TestComputeDiff:
    def test_old_none_returns_empty_diff(self) -> None:
        diff = compute_diff(None, _data())
        assert not diff.has_any_changes
        assert diff.old_values == {}
        assert diff.new_values == {}

    def test_no_changes(self) -> None:
        d = _data(registrar="X", name_servers=["ns1.x.com", "ns2.x.com"], status=["ok"])
        diff = compute_diff(d, d)
        assert not diff.has_any_changes

    def test_expires_at_changed(self) -> None:
        old = _data(expires_at=datetime(2027, 3, 15, tzinfo=UTC))
        new = _data(expires_at=datetime(2028, 3, 15, tzinfo=UTC))
        diff = compute_diff(old, new)
        assert diff.expires_at_changed
        assert diff.has_any_changes
        assert diff.old_values["expires_at"] == old.expires_at
        assert diff.new_values["expires_at"] == new.expires_at

    def test_expires_at_within_tolerance_no_change(self) -> None:
        # Микро-различие в 30 минут — не считается изменением.
        old = _data(expires_at=datetime(2027, 3, 15, 10, 0, tzinfo=UTC))
        new = _data(expires_at=datetime(2027, 3, 15, 10, 30, tzinfo=UTC))
        diff = compute_diff(old, new)
        assert not diff.expires_at_changed

    def test_expires_at_above_tolerance(self) -> None:
        old = _data(expires_at=datetime(2027, 3, 15, 10, 0, tzinfo=UTC))
        new = _data(expires_at=datetime(2027, 3, 15, 12, 0, tzinfo=UTC))
        diff = compute_diff(old, new)
        assert diff.expires_at_changed

    def test_registrar_changed(self) -> None:
        old = _data(registrar="GoDaddy")
        new = _data(registrar="Namecheap")
        diff = compute_diff(old, new)
        assert diff.registrar_changed
        assert diff.old_values["registrar"] == "GoDaddy"
        assert diff.new_values["registrar"] == "Namecheap"

    def test_registrar_trim_equivalent(self) -> None:
        old = _data(registrar=" GoDaddy ")
        new = _data(registrar="GoDaddy")
        diff = compute_diff(old, new)
        assert not diff.registrar_changed

    def test_registrar_empty_to_none(self) -> None:
        # "" и None считаются равными (whitespace-trim даёт None).
        old = _data(registrar="")
        new = _data(registrar=None)
        diff = compute_diff(old, new)
        assert not diff.registrar_changed

    def test_name_servers_order_does_not_matter(self) -> None:
        old = _data(name_servers=["ns1.x.com", "ns2.x.com"])
        new = _data(name_servers=["ns2.x.com", "ns1.x.com"])
        diff = compute_diff(old, new)
        assert not diff.name_servers_changed

    def test_name_servers_added(self) -> None:
        old = _data(name_servers=["ns1.x.com"])
        new = _data(name_servers=["ns1.x.com", "ns2.x.com"])
        diff = compute_diff(old, new)
        assert diff.name_servers_changed
        assert set(diff.new_values["name_servers"]) == {"ns1.x.com", "ns2.x.com"}

    def test_status_set_compared(self) -> None:
        old = _data(status=["ok", "clientTransferProhibited"])
        new = _data(status=["clientTransferProhibited", "ok"])
        assert not compute_diff(old, new).status_changed

    def test_multiple_changes_collected(self) -> None:
        old = _data(
            expires_at=datetime(2027, 3, 15, tzinfo=UTC),
            registrar="A",
            name_servers=["a.x.com"],
            status=["ok"],
        )
        new = _data(
            expires_at=datetime(2028, 3, 15, tzinfo=UTC),
            registrar="B",
            name_servers=["b.x.com"],
            status=["serverHold"],
        )
        diff = compute_diff(old, new)
        assert diff.expires_at_changed
        assert diff.registrar_changed
        assert diff.name_servers_changed
        assert diff.status_changed
        assert diff.has_any_changes
        assert set(diff.old_values) == {"expires_at", "registrar", "name_servers", "status"}
        assert set(diff.new_values) == {"expires_at", "registrar", "name_servers", "status"}

    def test_none_to_value_for_dates(self) -> None:
        old = _data(expires_at=None)
        new = _data(expires_at=datetime(2027, 3, 15, tzinfo=UTC))
        diff = compute_diff(old, new)
        assert diff.expires_at_changed

    def test_value_to_none_for_dates(self) -> None:
        old = _data(expires_at=datetime(2027, 3, 15, tzinfo=UTC))
        new = _data(expires_at=None)
        diff = compute_diff(old, new)
        assert diff.expires_at_changed

    def test_tolerance_exactly_one_hour(self) -> None:
        old = _data(expires_at=datetime(2027, 3, 15, 10, 0, tzinfo=UTC))
        new = _data(expires_at=datetime(2027, 3, 15, 10, 0, tzinfo=UTC) + timedelta(hours=1))
        # ровно 1 час == граница, всё ещё «не изменилось».
        diff = compute_diff(old, new)
        assert not diff.expires_at_changed
