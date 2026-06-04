"""ARQ-задача ``check_dns``: проверка DNS-записей домена.

Параллельно ``check_ssl`` для SSL-сертификатов (Этап 14, ADR 032).

Алгоритм:

1. Берём distributed lock в Redis (``dns_check_in_progress:<domain>``,
   TTL 60s) — защита от двойного запуска между cron-тиками.
2. Снимаем старое состояние из ``dns_cache`` и WHOIS-NS из
   ``whois_cache.name_servers`` (отдельная колонка ARRAY(Text), не
   ``raw_data``) — нужны для diff и detect_ns_mismatch соответственно.
3. Резолвим DNS через ``src.dns_monitor.resolve_records`` (никогда
   не бросает — возвращает ``DNSRecords | DNSError``).
4. Обогащаем IP через ``enrich_with_asn`` (в v0.8.0 placeholder → []).
5. ``compute_dns_diff(old, new, asn_set)`` — first-fetch guard внутри
   (``old=None`` → пустой diff, тот же инвариант что в SSL/WHOIS).
6. ``calculate_next_dns_check`` с adaptive TTL.
7. ``upsert`` нового состояния (одной операцией, без отдельной
   ``update_fail`` — упрощает invariant ``ns_mismatch_active`` всегда
   синхронизирован с реальностью).
8. Если есть ``diff.has_any_changes`` или NS-mismatch transition —
   подбираем подписчиков и ставим ``send_dns_change_notice`` для
   каждого ``(user, change_type)``.

Инварианты:

- First-fetch не триггерит уведомлений (old=None → пустой diff).
- ``became_unreachable`` — только переход, через ``compute_dns_diff``.
- ``invalid_domain`` / ``disabled`` не считаются как unreachable.
- ``is_muted`` гасит все DNS-уведомления независимо от toggle'ов.
- NS-mismatch transitions ловятся ТОЛЬКО при ``old is not None``
  (первая проверка не может быть transition'ом).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from aiogram import Bot
from arq import ArqRedis
from redis.asyncio import Redis as AsyncRedis

from src.db.repositories import (
    DNSCacheRepository,
    DomainRepository,
    WhoisCacheRepository,
)
from src.db.session import get_session
from src.dns_monitor import (
    DNSRecords,
    calculate_next_dns_check,
    compute_dns_diff,
    detect_ns_mismatch,
    enrich_with_asn,
    resolve_records,
)
from src.locales import t
from src.observability import bind_log_context, clear_log_context
from src.services.formatters import format_dns_block

logger = logging.getLogger(__name__)


_IN_PROGRESS_TTL_SECONDS = 60


def _in_progress_key(domain: str) -> str:
    return f"dns_check_in_progress:{domain}"


async def check_dns(
    ctx: dict[str, Any],
    domain: str,
    deliver_chat_id: int | None = None,
    deliver_lang: str | None = None,
) -> None:
    """ARQ-задача: проверить DNS-записи одного домена."""
    redis: AsyncRedis[str] = ctx["sync_redis"]

    bind_log_context(domain=domain, subsystem="dns")
    try:
        acquired = await redis.set(
            _in_progress_key(domain), "1", ex=_IN_PROGRESS_TTL_SECONDS, nx=True
        )
        if not acquired:
            logger.debug("check_dns skipped (already in progress): %s", domain)
            return

        try:
            await _check_dns_locked(domain, ctx, deliver_chat_id, deliver_lang)
        finally:
            await redis.delete(_in_progress_key(domain))
    finally:
        clear_log_context()


async def _check_dns_locked(
    domain: str,
    ctx: dict[str, Any],
    deliver_chat_id: int | None = None,
    deliver_lang: str | None = None,
) -> None:
    """Основная логика проверки (внутри Redis lock)."""
    now = datetime.now(tz=UTC)

    # 1. Снимок старого состояния + WHOIS-NS (для detect_ns_mismatch).
    async with get_session() as session:
        cache_repo = DNSCacheRepository(session)
        whois_repo = WhoisCacheRepository(session)
        old = await cache_repo.get(domain)
        whois_cache = await whois_repo.get(domain)
        whois_ns = list(whois_cache.name_servers or []) if whois_cache is not None else []

    # 2. Резолв (никогда не бросает).
    result = await resolve_records(domain)

    # 3. ASN-обогащение (placeholder в v0.8.0 — всегда []).
    asn_set: list[int] = []
    if isinstance(result, DNSRecords):
        all_ips = list(result.a_records) + list(result.aaaa_records)
        asn_set = await enrich_with_asn(all_ips)

    # 4. Diff ДО мутации (тот же инвариант что в SSL).
    diff = compute_dns_diff(old, result, asn_set)

    # 5. NS-mismatch transitions (ortogonal к compute_dns_diff —
    # последний сравнивает только DNS-состояния между собой).
    new_ns_mismatch_active = False
    if isinstance(result, DNSRecords) and whois_ns:
        new_ns_mismatch_active = detect_ns_mismatch(result.ns_records, whois_ns)
    old_ns_mismatch_active = bool(old.ns_mismatch_active) if old is not None else False

    ns_mismatch_changes: list[str] = []
    if old is not None:
        if new_ns_mismatch_active and not old_ns_mismatch_active:
            ns_mismatch_changes.append("ns_mismatch_detected")
        elif old_ns_mismatch_active and not new_ns_mismatch_active:
            ns_mismatch_changes.append("ns_mismatch_resolved")

    # 6. Adaptive TTL.
    if diff.has_any_changes:
        last_changed_at: datetime | None = now
    elif old is not None:
        last_changed_at = old.last_changed_at
    else:
        last_changed_at = None

    if isinstance(result, DNSRecords):
        last_successful_at: datetime | None = now
        fail_count = 0
    else:
        last_successful_at = old.last_successful_check_at if old is not None else None
        fail_count = (old.fail_count if old is not None else 0) + 1

    next_check_at = calculate_next_dns_check(
        last_successful_at=last_successful_at,
        last_changed_at=last_changed_at,
        fail_count=fail_count,
        ns_mismatch_active=new_ns_mismatch_active,
        last_change_was_asn=diff.a_asn_changed or diff.aaaa_asn_changed,
        now=now,
    )

    # 7. Persist. Используем upsert и в success, и в error-ветке —
    # это сохраняет ``ns_mismatch_active`` синхронным с реальностью и
    # покрывает случай "первый fetch упал" (запись могла отсутствовать,
    # если scheduler bootstrap ещё не отработал).
    async with get_session() as session:
        cache_repo = DNSCacheRepository(session)
        if isinstance(result, DNSRecords):
            await cache_repo.upsert(
                domain,
                a_records=list(result.a_records) or None,
                aaaa_records=list(result.aaaa_records) or None,
                ns_records=list(result.ns_records) or None,
                asn_set=asn_set or None,
                resolution_state=result.resolution_state,
                is_reachable=True,
                resolver_used=result.resolver_used,
                ns_mismatch_active=new_ns_mismatch_active,
                fail_count=0,
                last_error=None,
                last_checked_at=now,
                last_successful_check_at=now,
                last_changed_at=last_changed_at,
                next_check_at=next_check_at,
            )

            # TASK-0076: доставка DNS обновления для whois карточки
            if deliver_chat_id:
                bot: Bot = ctx.get("bot")  # type: ignore[assignment]
                if bot:
                    try:
                        async with get_session() as session:
                            cr = DNSCacheRepository(session)
                            cache = await cr.get(domain)
                        if cache:
                            block = format_dns_block(
                                cache, whois_ns=whois_ns, lang=deliver_lang or "ru"
                            )
                            if block:
                                header = t(
                                    "tasks.deliver.dns_update",
                                    deliver_lang or "ru",
                                    domain=domain,
                                )
                                await bot.send_message(deliver_chat_id, f"{header}\n{block}")
                                logger.info(
                                    "Delivered DNS update to chat %s for %s",
                                    deliver_chat_id,
                                    domain,
                                )
                    except Exception as dexc:
                        logger.warning("Failed DNS deliver to %s: %s", deliver_chat_id, dexc)
        else:
            # invalid_domain / disabled — конфигурационные, не сетевые:
            # is_reachable не трогаем (становится / остаётся True или None).
            is_unreachable_now = result.error_type not in ("invalid_domain", "disabled")
            fields: dict[str, Any] = {
                "resolution_state": "error",
                "fail_count": fail_count,
                "last_error": f"{result.error_type}: {result.message}",
                "last_checked_at": now,
                "next_check_at": next_check_at,
            }
            if is_unreachable_now:
                fields["is_reachable"] = False
            await cache_repo.upsert(domain, **fields)

    # 8. Enqueue notifications. Собираем change_types из diff'а + NS.
    change_types: list[str] = []
    if diff.a_changed:
        change_types.append("a_changed")
    if diff.aaaa_changed:
        change_types.append("aaaa_changed")
    if diff.ns_changed:
        change_types.append("ns_changed")
    if diff.became_unreachable:
        change_types.append("became_unreachable")
    if diff.became_reachable:
        change_types.append("became_reachable")
    change_types.extend(ns_mismatch_changes)

    if not change_types:
        logger.info("check_dns: %s no changes", domain)
        return

    async with get_session() as session:
        domain_repo = DomainRepository(session)
        subscribers = await domain_repo.get_subscribers_for_domain(domain)

    arq_redis: ArqRedis = ctx["redis"]
    enqueued = 0
    for sub in subscribers:
        if sub.is_muted or not sub.track_dns:
            continue
        for change_type in change_types:
            await arq_redis.enqueue_job(
                "send_dns_change_notice",
                sub.user_id,
                domain,
                change_type,
            )
            enqueued += 1

    logger.info(
        "check_dns: %s diff=%s enqueued=%d",
        domain,
        change_types,
        enqueued,
    )


__all__ = ["check_dns"]
