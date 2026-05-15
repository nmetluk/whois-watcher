"""Расчёт ``next_check_at`` для ``whois_cache`` (ADR 007).

Чистые функции — никаких I/O, легко тестируются на синтетических входах.
Все интервалы — из ``Limits`` (``TTL_*_DAYS``, ``FAIL_*``), чтобы можно
было переопределять через env.

Поведение по таблице из ``docs/architecture.md``:

| Дней до истечения | Интервал |
|-------------------|----------|
| > 90              | ``ttl_far_days`` (30)  |
| 30 – 90           | ``ttl_mid_days`` (7)   |
| 7 – 30            | ``ttl_near_days`` (2)  |
| 0 – 7             | ``ttl_critical_days`` (1) |
| < 0 (истёк)       | 1 день, в окне ``ttl_after_expiry_days`` после истечения |
| < -ttl_after_…    | None — больше не проверяем |
| expires_at = None | 1 день — пробуем дозаполнить |
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from src.config.limits import Limits, get_limits


def _now(now: datetime | None) -> datetime:
    """Возвращает ``now`` или текущее UTC-время; всегда timezone-aware."""
    if now is None:
        return datetime.now(tz=UTC)
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    return now


def calculate_next_check(
    expires_at: datetime | None,
    *,
    now: datetime | None = None,
    limits: Limits | None = None,
) -> datetime | None:
    """Возвращает момент следующей плановой проверки или ``None``.

    ``None`` означает «больше не проверяем» — это случай, когда домен
    истёк больше ``ttl_after_expiry_days`` назад и никем не продлён.

    ``expires_at`` тоже может быть ``None`` (мы ещё не знаем дату):
    запланируем повтор через 1 день, чтобы дозаполнить.
    """
    cfg = limits if limits is not None else get_limits()
    moment = _now(now)

    if expires_at is None:
        return moment + timedelta(days=1)

    if expires_at.tzinfo is None:
        raise ValueError("expires_at must be timezone-aware")

    delta = expires_at - moment
    days_left = delta.total_seconds() / 86400

    if days_left > 90:
        return moment + timedelta(days=cfg.ttl_far_days)
    if days_left > 30:
        return moment + timedelta(days=cfg.ttl_mid_days)
    if days_left > 7:
        return moment + timedelta(days=cfg.ttl_near_days)
    if days_left > 0:
        return moment + timedelta(days=cfg.ttl_critical_days)

    # Истёк. Проверяем ещё ``ttl_after_expiry_days`` дней — на случай
    # отложенного продления, потом перестаём.
    if days_left < -cfg.ttl_after_expiry_days:
        return None
    return moment + timedelta(days=1)


def calculate_retry_after_failure(
    fail_count: int,
    *,
    now: datetime | None = None,
) -> datetime:
    """Момент следующей попытки после неудачной WHOIS-проверки.

    Согласно ``docs/architecture.md``:

    - 1 фейл → +15 минут
    - 2-3 фейла → +1, затем +2 часа
    - 4-5 фейлов → +6, затем +12 часов
    - 6+ → каждые 24 часа (но при ``fail_count`` уровня 5+ и старом
      ``last_successful_fetch_at`` всё равно уведомляем пользователя,
      см. ADR 019 — это уже задача воркера, не планировщика).

    ``fail_count`` ≤ 0 трактуем как 1 — защита от вырожденных вызовов.
    """
    moment = _now(now)
    n = max(1, fail_count)
    if n == 1:
        delay = timedelta(minutes=15)
    elif n == 2:
        delay = timedelta(hours=1)
    elif n == 3:
        delay = timedelta(hours=2)
    elif n == 4:
        delay = timedelta(hours=6)
    elif n == 5:
        delay = timedelta(hours=12)
    else:
        delay = timedelta(hours=24)
    return moment + delay
