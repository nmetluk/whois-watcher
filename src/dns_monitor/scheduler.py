"""Adaptive TTL для DNS-проверок (Этап 14, ADR 032).

По образцу ``src/ssl/scheduler.py`` — bucket-based decision.

В отличие от SSL (где интервал зависит от ``not_after``), у DNS нет
"истечения", поэтому критерии другие:

- ``ns_mismatch_active`` — плотный мониторинг (30 мин), это
  critical state и хочется быстро увидеть его resolved
- ``fail_count >= MAX_FAIL_COUNT`` — backoff на упорные ошибки
  (24h), не долбим NXDOMAIN-домен
- recent A/AAAA change (последние 24h) без ASN-смены — likely
  CDN, реже (6h)
- recent change с ASN-сменой — наблюдаем плотно (1h)
- stable — раз в сутки
- новый домен (``last_successful_at=None``) — раз в час
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Final

# Интервалы
FRESH_INTERVAL: Final = timedelta(hours=1)
STABLE_INTERVAL: Final = timedelta(days=1)
CDN_LIKELY_INTERVAL: Final = timedelta(hours=6)
NS_MISMATCH_INTERVAL: Final = timedelta(minutes=30)
BACKOFF_INTERVAL: Final = timedelta(hours=24)

# Пороги
MAX_FAIL_COUNT: Final = 10
RECENT_CHANGE_WINDOW: Final = timedelta(hours=24)


def calculate_next_dns_check(
    *,
    last_successful_at: datetime | None,
    last_changed_at: datetime | None,
    fail_count: int,
    ns_mismatch_active: bool,
    last_change_was_asn: bool,
    now: datetime | None = None,
) -> datetime:
    """Вычисляет ``next_check_at`` для DNS-кэша.

    Args:
        last_successful_at: когда последний раз успешно резолвили
            (None — никогда не было успеха, т.е. новый домен)
        last_changed_at: когда A/AAAA/NS реально менялись
            (None если ничего не менялось с момента первого fetch)
        fail_count: сколько раз подряд resolve упал
        ns_mismatch_active: DNS-NS != WHOIS-NS прямо сейчас
            (critical state)
        last_change_was_asn: последнее изменение было сменой ASN
            (true critical) — игнорируем CDN-detection. В v0.8.0
            всегда False из-за ASN placeholder.
        now: текущее время (override для тестов)

    Returns:
        ``next_check_at`` — datetime в UTC
    """
    moment = now or datetime.now(tz=UTC)
    if moment.tzinfo is None:
        raise ValueError("now must be timezone-aware")

    # 1. Backoff на упорные ошибки
    if fail_count >= MAX_FAIL_COUNT:
        return moment + BACKOFF_INTERVAL

    # 2. Critical state — NS mismatch
    if ns_mismatch_active:
        return moment + NS_MISMATCH_INTERVAL

    # 3. Новый домен (никогда не было успеха)
    if last_successful_at is None:
        return moment + FRESH_INTERVAL

    # 4. Recent change
    if last_changed_at is not None:
        time_since_change = moment - last_changed_at
        if time_since_change < RECENT_CHANGE_WINDOW:
            # ASN-смена — наблюдаем плотно
            if last_change_was_asn:
                return moment + FRESH_INTERVAL
            # Без ASN-смены — likely CDN noise, реже
            return moment + CDN_LIKELY_INTERVAL

    # 5. Стабильный домен
    return moment + STABLE_INTERVAL


__all__ = [
    "BACKOFF_INTERVAL",
    "CDN_LIKELY_INTERVAL",
    "FRESH_INTERVAL",
    "MAX_FAIL_COUNT",
    "NS_MISMATCH_INTERVAL",
    "RECENT_CHANGE_WINDOW",
    "STABLE_INTERVAL",
    "calculate_next_dns_check",
]
