"""Тесты ``src.services.notifications`` (Этап 11, ADR 029)."""

from __future__ import annotations

from types import SimpleNamespace

from src.services.notifications import (
    get_effective_notify_days,
    is_notification_enabled,
)


def _ud(**overrides: object) -> SimpleNamespace:
    """Лёгкий stub UserDomain — все 7 boolean'ов + notify_days в одном месте."""
    base: dict[str, object] = {
        "is_muted": False,
        "notify_expiry": True,
        "notify_registrar_change": True,
        "notify_ns_change": False,  # ADR 012 default
        "notify_status_change": True,
        "notify_registrant_change": True,
        "notify_problem": True,
        "notify_days": None,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _user(notify_days: list[int]) -> SimpleNamespace:
    return SimpleNamespace(notify_days=notify_days)


class TestIsNotificationEnabled:
    def test_all_defaults_true_except_ns(self) -> None:
        ud = _ud()
        assert is_notification_enabled(ud, "expiry") is True
        assert is_notification_enabled(ud, "registrar_change") is True
        assert is_notification_enabled(ud, "ns_change") is False  # ADR 012
        assert is_notification_enabled(ud, "status_change") is True
        assert is_notification_enabled(ud, "registrant_change") is True
        assert is_notification_enabled(ud, "problem") is True

    def test_is_muted_overrides_everything(self) -> None:
        ud = _ud(is_muted=True)
        for t in (
            "expiry",
            "registrar_change",
            "ns_change",
            "status_change",
            "registrant_change",
            "problem",
        ):
            assert is_notification_enabled(ud, t) is False, t

    def test_individual_toggle_off_only_affects_that_type(self) -> None:
        ud = _ud(notify_expiry=False)
        assert is_notification_enabled(ud, "expiry") is False
        assert is_notification_enabled(ud, "registrar_change") is True
        assert is_notification_enabled(ud, "registrant_change") is True

    def test_registrant_change_is_independent_from_registrar_change(self) -> None:
        """ADR 029: раньше registrant шёл через registrar_change-mapping,
        теперь они независимы."""
        ud = _ud(notify_registrar_change=False, notify_registrant_change=True)
        assert is_notification_enabled(ud, "registrar_change") is False
        assert is_notification_enabled(ud, "registrant_change") is True

    def test_problem_can_be_disabled(self) -> None:
        ud = _ud(notify_problem=False)
        assert is_notification_enabled(ud, "problem") is False
        assert is_notification_enabled(ud, "expiry") is True


class TestEffectiveNotifyDays:
    def test_no_override_returns_user_days_sorted_desc(self) -> None:
        user = _user([1, 30, 7])
        ud = _ud(notify_days=None)
        assert get_effective_notify_days(user, ud) == [30, 7, 1]

    def test_override_takes_precedence(self) -> None:
        user = _user([30, 7, 1])
        ud = _ud(notify_days=[60, 14, 3])
        assert get_effective_notify_days(user, ud) == [60, 14, 3]

    def test_empty_override_returns_empty(self) -> None:
        # Пустой override — это явный выбор «вообще не напоминать
        # за дни». Не fallback'имся на user.
        user = _user([30, 7])
        ud = _ud(notify_days=[])
        assert get_effective_notify_days(user, ud) == []
