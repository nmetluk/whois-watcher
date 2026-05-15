"""Форматирование для UI: даты, дни до истечения, статус-эмодзи."""

from __future__ import annotations

from datetime import datetime, timezone

from src.utils.idn import from_punycode

# Статус-эмодзи по дням до истечения (docs/commands.md → /list).
EMOJI_OK = "🟢"           # > 30 дней
EMOJI_WARNING = "🟡"      # 7–30 дней
EMOJI_CRITICAL = "🔴"     # < 7 дней или истёк
EMOJI_UNKNOWN = "⚫"      # нет данных


def days_until(target: datetime, *, now: datetime | None = None) -> int:
    """Количество дней между ``now`` и ``target`` (округление вниз).

    Отрицательное значение — домен уже истёк. ``now`` — для тестов;
    в проде используется ``datetime.now(timezone.utc)``.
    """
    moment = now if now is not None else datetime.now(tz=timezone.utc)
    if target.tzinfo is None:
        raise ValueError("days_until: target must be timezone-aware")
    if moment.tzinfo is None:
        raise ValueError("days_until: now must be timezone-aware")
    delta = target - moment
    return delta.days


def format_days_until(target: datetime, *, lang: str = "ru") -> tuple[int, str]:
    """Возвращает пару (дней, человекочитаемая строка).

    Локализация — на двух языках. Для RU используется упрощённое склонение:
    1 день / 2-4 дня / 5+ дней — точная плюрализация поддерживается.
    """
    days = days_until(target)
    if lang == "en":
        return days, _format_days_en(days)
    return days, _format_days_ru(days)


def _format_days_ru(days: int) -> str:
    if days < 0:
        n = -days
        return f"истёк {n} {_plural_ru_days(n)} назад"
    if days == 0:
        return "сегодня"
    return f"через {days} {_plural_ru_days(days)}"


def _format_days_en(days: int) -> str:
    if days < 0:
        n = -days
        return f"expired {n} day{'s' if n != 1 else ''} ago"
    if days == 0:
        return "today"
    return f"in {days} day{'s' if days != 1 else ''}"


def _plural_ru_days(n: int) -> str:
    """Русская плюрализация: день / дня / дней."""
    n_abs = abs(n) % 100
    if 11 <= n_abs <= 14:
        return "дней"
    last = n_abs % 10
    if last == 1:
        return "день"
    if 2 <= last <= 4:
        return "дня"
    return "дней"


def format_date(dt: datetime, *, lang: str = "ru") -> str:
    """Форматирует дату в локальный формат: ``15.03.2027`` (RU) / ``2027-03-15`` (EN)."""
    if lang == "en":
        return dt.strftime("%Y-%m-%d")
    return dt.strftime("%d.%m.%Y")


def format_domain_for_display(domain: str) -> str:
    """Punycode → Unicode для отображения в UI.

    На некорректном вводе вернёт ``domain`` как есть.
    """
    return from_punycode(domain)


def get_expiry_emoji(days_left: int | None) -> str:
    """Возвращает статус-эмодзи по числу дней до истечения.

    ``None`` означает "данных нет" → чёрный кружок.
    """
    if days_left is None:
        return EMOJI_UNKNOWN
    if days_left < 7:
        return EMOJI_CRITICAL
    if days_left <= 30:
        return EMOJI_WARNING
    return EMOJI_OK
