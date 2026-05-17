"""Adaptive TTL для SSL-проверок (Этап 12, ADR 030).

Чистая функция без I/O — легко тестируется. SSL-сертификаты живут
сильно короче WHOIS-регистраций (LE — 90 дней, многие сертификаты —
365), поэтому шкала интервалов другая чем в ``src.whois.scheduler``:

| Дней до истечения | Интервал |
|-------------------|----------|
| > 30              | 1 день   |
| 7 – 30            | 6 часов  |
| 1 – 7             | 1 час    |
| ≤ 0 / нет данных  | 4 часа   |

При ``fail_count ≥ 10`` (длительные сбои) — фиксированно раз в сутки,
чтобы не долбить мёртвый хост.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta


def calculate_next_ssl_check(
    not_after: datetime | None,
    *,
    fail_count: int = 0,
    now: datetime | None = None,
) -> datetime:
    """Возвращает момент следующей плановой SSL-проверки.

    Возвращаемое значение — всегда timezone-aware UTC.
    """
    moment = now or datetime.now(tz=UTC)
    if moment.tzinfo is None:
        raise ValueError("now must be timezone-aware")

    if fail_count >= 10:
        # Кэп от спама в логи: после 10 фейлов раз в сутки.
        return moment + timedelta(hours=24)

    if not_after is None:
        # Нет данных (например, no_https / cert не получен) —
        # пробуем снова через 4 часа.
        return moment + timedelta(hours=4)

    if not_after.tzinfo is None:
        raise ValueError("not_after must be timezone-aware")

    delta = not_after - moment
    days_left = delta.total_seconds() / 86400

    if days_left > 30:
        return moment + timedelta(days=1)
    if days_left > 7:
        return moment + timedelta(hours=6)
    if days_left > 1:
        return moment + timedelta(hours=1)
    # ≤ 1 день, либо уже истёк — каждые 4 часа.
    return moment + timedelta(hours=4)


__all__ = ["calculate_next_ssl_check"]
