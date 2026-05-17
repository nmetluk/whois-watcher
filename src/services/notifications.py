"""Helpers per-domain notification settings (Этап 11, ADR 029).

Гранулярные настройки уведомлений хранятся в ``UserDomain``:

- ``is_muted`` — kill-switch, при True подавляет ВСЁ.
- ``notify_expiry`` / ``notify_registrar_change`` / ``notify_ns_change`` /
  ``notify_status_change`` / ``notify_registrant_change`` /
  ``notify_problem`` — индивидуальные toggle на каждый тип уведомления.
- ``notify_days`` — per-domain override списка дней предупреждения.
  NULL → используется ``User.notify_days``.

Этот модуль — единственная точка чтения этих полей в логике задач.
Хэндлеры конфигуратора (см. ``bot/handlers/notify_config.py``) пишут
напрямую через репозиторий.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal

from src.db.models import User, UserDomain

# Все типы уведомлений, которые управляются per-domain toggle'ами.
# Имена расходятся с именами полей в БД — соответствие см. в
# ``_FIELD_BY_TYPE`` ниже.
NotificationType = Literal[
    "expiry",
    "registrar_change",
    "ns_change",
    "status_change",
    "registrant_change",
    "problem",
]


def is_notification_enabled(
    user_domain: UserDomain,
    notification_type: NotificationType,
) -> bool:
    """Должно ли отправляться уведомление данного типа для этого домена.

    ``is_muted`` имеет приоритет: при True все типы → False, независимо
    от индивидуальных toggle'ов.
    """
    if user_domain.is_muted:
        return False
    return _FIELD_BY_TYPE[notification_type](user_domain)


def get_effective_notify_days(user: User, user_domain: UserDomain) -> list[int]:
    """Эффективный список дней-предупреждений для конкретного домена.

    Per-domain override (``UserDomain.notify_days``) имеет приоритет;
    при NULL — берётся ``User.notify_days``. Возвращаем отсортированный
    по убыванию список (старшие дни — раньше); та же логика, что в
    ``tasks/expiry_scheduler.py`` через SQL COALESCE.
    """
    if user_domain.notify_days is not None:
        return sorted(user_domain.notify_days, reverse=True)
    return sorted(user.notify_days, reverse=True)


# ---------------------------------------------------------------------------
# Внутреннее
# ---------------------------------------------------------------------------

_Field = Callable[[UserDomain], bool]

_FIELD_BY_TYPE: dict[NotificationType, _Field] = {
    "expiry": lambda ud: ud.notify_expiry,
    "registrar_change": lambda ud: ud.notify_registrar_change,
    "ns_change": lambda ud: ud.notify_ns_change,
    "status_change": lambda ud: ud.notify_status_change,
    "registrant_change": lambda ud: ud.notify_registrant_change,
    "problem": lambda ud: ud.notify_problem,
}


__all__ = [
    "NotificationType",
    "get_effective_notify_days",
    "is_notification_enabled",
]
