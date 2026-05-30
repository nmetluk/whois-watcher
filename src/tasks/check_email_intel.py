"""ARQ-задача ``check_email_intel``: одиночная проверка email-intel домена.

Параллельно ``check_ssl`` для SSL — те же принципы:

- Redis-флаг ``email_intel_check_in_progress:<domain>`` гарантирует один воркер на домен.
- Успех → UPSERT в ``email_intel_cache`` + diff против старого состояния + постановка
  ``send_email_change_notice`` подписчикам.
- Ошибка fetch'а → ``EmailIntelCacheRepository.update_fail`` + пересчёт
  ``next_check_at`` через ``calculate_next_email_check``.
- При first fetch (``old_cache is None`` или ``old.is_reachable=False``)
  — НЕ шлём уведомлений (пустой diff).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from arq import ArqRedis
from redis.asyncio import Redis as AsyncRedis

from src.db.models import EmailIntelCache, UserDomain
from src.db.repositories import DomainRepository, EmailIntelCacheRepository
from src.db.session import get_session
from src.email_intel.client import fetch_email_intel
from src.email_intel.diff import EmailIntelDiff, compute_email_diff
from src.email_intel.scheduler import calculate_next_email_check
from src.email_intel.types import EmailIntelError, EmailIntelResult
from src.observability import bind_log_context, clear_log_context

logger = logging.getLogger(__name__)


_IN_PROGRESS_TTL_SECONDS = 60


def _in_progress_key(domain: str) -> str:
    return f"email_intel_check_in_progress:{domain}"


def _cache_to_result(cache: EmailIntelCache) -> EmailIntelResult | None:
    """Достаёт ``EmailIntelResult`` из кэша для diff-сравнения.

    Returns None если в кэше нет настоящих данных (``is_reachable=False``).
    """
    if not cache.is_reachable:
        return None

    from src.email_intel.types import (
        DKIMInfo,
        DMARCRecord,
        MXRecord,
        SPFRecord,
    )

    # Восстанавливаем типы из JSONB-полей кэша
    mx_records = [
        MXRecord(host=item["host"], priority=item["priority"]) for item in (cache.mx_records or [])
    ]

    spf_record: SPFRecord | None = None
    if cache.spf_record and cache.spf_mode:
        spf_record = SPFRecord(
            raw=cache.spf_record,
            mode=cache.spf_mode,  # type: ignore[arg-type]
            is_multiple=False,
        )

    dmarc_record: DMARCRecord | None = None
    if cache.dmarc_policy:
        dmarc_record = DMARCRecord(
            policy=cache.dmarc_policy,  # type: ignore[arg-type]
            subpolicy=cache.dmarc_subpolicy,  # type: ignore[arg-type]
            pct=cache.dmarc_pct,
        )

    dkim_info: DKIMInfo | None = None
    if cache.dkim_selectors:
        dkim_info = DKIMInfo(selectors=list(cache.dkim_selectors or []))

    return EmailIntelResult(
        domain=cache.domain,
        is_reachable=True,
        mx_records=mx_records,
        spf=spf_record,
        dmarc=dmarc_record,
        dkim=dkim_info,
    )


async def check_email_intel(ctx: dict[str, Any], domain: str) -> None:
    """ARQ-задача: проверить email-intel одного домена."""
    redis: AsyncRedis[str] = ctx["sync_redis"]

    bind_log_context(domain=domain, subsystem="email_intel")
    try:
        acquired = await redis.set(
            _in_progress_key(domain), "1", ex=_IN_PROGRESS_TTL_SECONDS, nx=True
        )
        if not acquired:
            logger.debug("check_email_intel skipped (already in progress): %s", domain)
            return

        try:
            async with get_session() as session:
                cache_repo = EmailIntelCacheRepository(session)
                existing = await cache_repo.get(domain)
                old_result = _cache_to_result(existing) if existing is not None else None

            result = await fetch_email_intel(domain)

            if isinstance(result, EmailIntelError):
                await _handle_failure(domain, result, ctx)
                return

            await _handle_success(domain, result, old_result, existing, ctx)
        finally:
            await redis.delete(_in_progress_key(domain))
    finally:
        clear_log_context()


# ---------------------------------------------------------------------------
# Success branch
# ---------------------------------------------------------------------------


async def _handle_success(
    domain: str,
    new_result: EmailIntelResult,
    old_result: EmailIntelResult | None,
    old_cache: EmailIntelCache | None,
    ctx: dict[str, Any],
) -> None:
    """UPSERT в кэш, diff, постановка change-notice подписчикам."""
    now = datetime.now(tz=UTC)

    # Вычисляем next_check_at через scheduler
    has_dmarc = new_result.dmarc is not None
    has_spf = new_result.spf is not None
    next_check = calculate_next_email_check(has_dmarc, has_spf, now=now)

    # Сериализуем для JSONB
    mx_records = [{"host": r.host, "priority": r.priority} for r in new_result.mx_records]
    dkim_selectors = new_result.dkim.selectors if new_result.dkim else None

    fields: dict[str, Any] = {
        "last_checked_at": now,
        "last_successful_check_at": now,
        "next_check_at": next_check,
        "is_reachable": True,
        "mx_records": mx_records,
        "spf_record": new_result.spf.raw if new_result.spf else None,
        "spf_mode": new_result.spf.mode if new_result.spf else None,
        "dmarc_policy": new_result.dmarc.policy if new_result.dmarc else None,
        "dmarc_subpolicy": new_result.dmarc.subpolicy if new_result.dmarc else None,
        "dmarc_pct": new_result.dmarc.pct if new_result.dmarc else None,
        "dkim_selectors": dkim_selectors,
        "fail_count": 0,
        "last_error": None,
    }

    async with get_session() as session:
        cache_repo = EmailIntelCacheRepository(session)
        await cache_repo.upsert(domain, **fields)

    diff = compute_email_diff(old_result, new_result)
    # Guard на «первая проверка»: не шлём уведомления если старых данных не было
    if diff.has_any_changes and old_result is not None and old_cache is not None:
        await _enqueue_change_notices(domain, diff, ctx)


async def _enqueue_change_notices(
    domain: str,
    diff: EmailIntelDiff,
    ctx: dict[str, Any],
) -> None:
    """Подбор подписчиков и постановка ``send_email_change_notice``."""
    arq_redis: ArqRedis = ctx["redis"]

    # Собираем все типы изменений для уведомления
    change_types: list[str] = []
    if diff.mx_changed:
        change_types.append("mx_changed")
    if diff.spf_changed:
        change_types.append("spf_changed")
    if diff.dmarc_changed:
        change_types.append("dmarc_changed")
    if diff.dkim_changed:
        change_types.append("dkim_changed")
    if diff.became_unreachable:
        change_types.append("became_unreachable")
    if diff.became_reachable:
        change_types.append("became_reachable")

    if not change_types:
        return

    async with get_session() as session:
        domain_repo = DomainRepository(session)
        subscribers = await domain_repo.get_subscribers_for_domain(domain)

    for sub in subscribers:
        if sub.is_muted or not sub.track_email or not sub.notify_email_change:
            continue
        # Отправляем уведомление для каждого типа изменения
        for change_type in change_types:
            await arq_redis.enqueue_job(
                "send_email_change_notice",
                sub.user_id,
                domain,
                change_type,
            )


# ---------------------------------------------------------------------------
# Failure branch
# ---------------------------------------------------------------------------


async def _handle_failure(
    domain: str,
    error: EmailIntelError,
    ctx: dict[str, Any],
) -> None:
    """UPDATE fail_count + next_check_at + диф на became_unreachable.

    ВАЖНО: ``compute_email_diff`` считаем ПЕРЕД мутацией ``is_reachable``,
    иначе old.is_reachable уже будет False и переход не зарегистрируется.
    """
    async with get_session() as session:
        cache_repo = EmailIntelCacheRepository(session)
        existing = await cache_repo.get(domain)

        # Снимок старого состояния — до записи fail'а
        old_result = _cache_to_result(existing) if existing is not None else None

        fail_count = (existing.fail_count if existing is not None else 0) + 1
        next_check = calculate_next_email_check(
            False,
            False,  # при ошибке считаем что данных нет
            fail_count=fail_count,
            now=datetime.now(tz=UTC),
        )
        await cache_repo.update_fail(domain, error.message, next_check_at=next_check)

        # became_unreachable шлём сразу, без ожидания следующего успешного
        # fetch'а — иначе пользователь узнает о падении с задержкой в часы.
        if old_result is None:
            return
        diff = compute_email_diff(old_result, error)
        if diff.has_any_changes:
            await _enqueue_change_notices(domain, diff, ctx)


def _sub_is_email_active(sub: UserDomain) -> bool:
    """Хелпер для тестов: подписка активна для email-уведомлений."""
    return not sub.is_muted and bool(sub.track_email)


__all__ = ["check_email_intel", "_sub_is_email_active"]
