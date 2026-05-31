"""Adaptive TTL для subdomain enumeration (TASK-0023, ADR 037).

Чистая функция без I/O — легко тестируется. Поддомены меняются
редко (новые сервисы появляются периодически), поэтому интервалы:

| Состояние                  | Интервал |
|----------------------------|----------|
| Успех (есть поддомены)     | 7 дней   |
| Успех (нет поддоменов)    | 30 дней  |
| Ошибка (fail_count < 3)    | 1 час    |
| Ошибка (fail_count ≥ 3)    | 1 день   |

Философия:
- Если crt.sh доступен — кэшируем надолго (поддомены редки)
- Если ошибка — retry часто, но с капом (не спамим crt.sh)
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta


def calculate_next_subdomain_check(
    *,
    has_subdomains: bool,
    fail_count: int = 0,
    success_interval_days: int = 7,
    now: datetime | None = None,
) -> datetime:
    """Возвращает момент следующей плановой subdomain enumeration.

    Args:
        has_subdomains: Были ли найдены поддомены
        fail_count: Количество последовательных неудач
        success_interval_days: Интервал на успех (дни, default 7)
        now: Текущий момент (для тестов)

    Returns:
        Момент следующей проверки (timezone-aware UTC)
    """
    moment = now or datetime.now(tz=UTC)
    if moment.tzinfo is None:
        raise ValueError("now must be timezone-aware")

    # Критический порог фейлов — кап до 1 дня
    if fail_count >= 3:
        return moment + timedelta(days=1)

    # Недавние ошибки — retry чаще
    if fail_count > 0:
        return moment + timedelta(hours=1)

    # Успех, но нет поддоменов — редко проверяем
    if not has_subdomains:
        return moment + timedelta(days=30)

    # Есть поддомены — интервал от подписчиков (floor 1д)
    interval = max(1, success_interval_days)
    return moment + timedelta(days=interval)


__all__ = ["calculate_next_subdomain_check"]
