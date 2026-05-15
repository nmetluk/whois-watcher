"""Работа с часовыми поясами пользователей.

Все даты в БД — ``timestamptz`` (UTC). Локализация только на отображении.
Используем ``zoneinfo`` из stdlib (Python 3.9+).
"""

from __future__ import annotations

from datetime import datetime, tzinfo
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def _resolve_tz(tz_name: str) -> tzinfo:
    """Возвращает ``ZoneInfo`` или поднимает ``ValueError`` с понятным текстом."""
    try:
        return ZoneInfo(tz_name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"Unknown timezone: {tz_name!r}") from exc


def is_valid_timezone(tz_name: str) -> bool:
    """True, если имя tz распознаётся ``zoneinfo``.

    Используется в ``/settings`` при вводе таймзоны вручную.
    """
    try:
        ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        return False
    return True


def get_user_local_hour(tz_name: str, *, now: datetime | None = None) -> int:
    """Текущий час (0–23) у пользователя с tz ``tz_name``.

    Используется планировщиком для проверки, "сейчас ли" у пользователя его
    ``notify_at_hour``. В коде это нужно только для тестов/отладки: в проде
    выборка идёт через SQL ``EXTRACT(HOUR FROM now() AT TIME ZONE ...)``,
    см. ``UserRepository.get_users_due_for_notification``.

    Параметр ``now`` облегчает тестирование.
    """
    tz = _resolve_tz(tz_name)
    moment = now if now is not None else datetime.now(tz=tz)
    return moment.astimezone(tz).hour


def format_in_user_tz(
    dt: datetime,
    tz_name: str,
    *,
    fmt: str = "%d.%m.%Y %H:%M",
) -> str:
    """Форматирует datetime в локальной TZ пользователя.

    ``dt`` должен быть timezone-aware (так как из БД приходит ``timestamptz``).
    На naive datetime бросаем ``ValueError`` — это всегда баг.
    """
    if dt.tzinfo is None:
        raise ValueError("format_in_user_tz requires timezone-aware datetime")
    tz = _resolve_tz(tz_name)
    return dt.astimezone(tz).strftime(fmt)
