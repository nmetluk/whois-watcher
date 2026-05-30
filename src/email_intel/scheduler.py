"""Adaptive TTL для email-intel проверок (TASK-0016, ADR 036).

Чистая функция без I/O — легко тестируется. Email/policy записи
меняются редко (месяцы/годы), поэтому интервалы длинные:

| Состояние                  | Интервал |
|----------------------------|----------|
| Нет DMARC/SPF             | 1 день   |
| Есть данные               | 7 дней   |
| fail_count ≥ 10           | 1 день   |

Философия: MX/SPF/DMARC меняются редко, но при первой настройке
компании часто добавляют/изменяют записи — поэтому при отсутствии
данных проверяем чаще (раз в день).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta


def calculate_next_email_check(
    has_dmarc: bool,
    has_spf: bool,
    *,
    fail_count: int = 0,
    now: datetime | None = None,
) -> datetime:
    """Возвращает момент следующей плановой email-intel проверки.

    Args:
        has_dmarc: Есть ли DMARC-запись
        has_spf: Есть ли SPF-запись
        fail_count: Количество последовательных неудач
        now: Текущий момент (для тестов)

    Returns:
        Момент следующей проверки (timezone-aware UTC)
    """
    moment = now or datetime.now(tz=UTC)
    if moment.tzinfo is None:
        raise ValueError("now must be timezone-aware")

    if fail_count >= 10:
        # Кэп от спама: после 10 фейлов раз в сутки
        return moment + timedelta(days=1)

    # Нет DMARC или SPF — проверяем чаще (может появиться)
    if not has_dmarc or not has_spf:
        return moment + timedelta(days=1)

    # Есть данные — проверяем раз в неделю
    return moment + timedelta(days=7)


__all__ = ["calculate_next_email_check"]
