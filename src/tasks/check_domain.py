"""ARQ-задача ``check_domain``: одиночная проверка домена.

Зовётся из:

- ``scheduler_tick`` (cron каждые 5 мин)
- ``WhoisFacade.enqueue_check`` (когда пользователь добавил неизвестный домен)

Что делает:

1. Берёт Redis-флаг ``check_in_progress:<domain>`` (TTL 60с). Если уже стоит —
   другой воркер уже занят этим доменом, выходим.
2. ``lookup_domain``.
3. На ``WhoisError`` — ``update_fail``, пересчитываем ``next_check_at`` через
   ``calculate_retry_after_failure``; при ``fail_count >= порога`` и старом
   ``last_successful_fetch_at`` — enqueue ``send_problem_notice``.
4. На ``WhoisData`` — UPSERT в ``whois_cache`` всех новых полей + ``fail_count=0``,
   ``next_check_at`` через ``calculate_next_check``. Сравниваем со старыми
   через ``compute_diff`` и enqueue ``send_change_notice`` подписчикам.
5. После успешной записи — если в Redis есть ``pending_add_followup:<domain>``
   c user_id'ами, шлём им followup-сообщение (это путь после ``/add`` нового
   домена).
6. В ``finally`` снимаем флаг ``check_in_progress``.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from aiogram import Bot
from redis.asyncio import Redis as AsyncRedis

from src.db.models import UserDomain, WhoisCache
from src.db.repositories import DomainRepository, UserRepository, WhoisCacheRepository
from src.db.session import get_session
from src.observability import bind_log_context, clear_log_context
from src.services.formatters import format_whois_response
from src.services.whois_facade import _cache_to_data
from src.whois.client import lookup_domain
from src.whois.diff import WhoisDiff, compute_diff
from src.whois.scheduler import calculate_next_check, calculate_retry_after_failure
from src.whois.types import WhoisData, WhoisError

logger = logging.getLogger(__name__)


# TTL Redis-флага «эта проверка уже идёт». На случай зависания соседнего
# воркера он автоматически отвалится через минуту.
_IN_PROGRESS_TTL_SECONDS = 60
# Сколько времени (после успешного ``/add`` нового домена) держим pending-followup'ы.
_PENDING_FOLLOWUP_TTL_SECONDS = 600


def _in_progress_key(domain: str) -> str:
    return f"check_in_progress:{domain}"


def _pending_followup_key(domain: str) -> str:
    return f"pending_add_followup:{domain}"


async def check_domain(ctx: dict[str, Any], domain: str) -> None:
    """ARQ-задача: проверить один домен и обновить кэш."""
    redis: AsyncRedis[str] = ctx["sync_redis"]
    bot: Bot = ctx["bot"]

    # Контекст для логов: имя домена попадёт во все структуры внутри таски,
    # включая «глубокие» logger.exception() из вложенных функций.
    bind_log_context(domain=domain)
    try:
        # 1. Защита от параллельных проверок одного домена.
        acquired = await redis.set(
            _in_progress_key(domain), "1", ex=_IN_PROGRESS_TTL_SECONDS, nx=True
        )
        if not acquired:
            logger.debug("check_domain skipped (already in progress): %s", domain)
            return

        try:
            async with get_session() as session:
                cache_repo = WhoisCacheRepository(session)
                existing = await cache_repo.get(domain)
                old_data = _cache_to_data(existing, domain) if existing is not None else None
            # 2. Live-lookup.
            result = await lookup_domain(domain)

            if isinstance(result, WhoisError):
                await _handle_failure(domain, result, ctx)
                return

            await _handle_success(domain, result, old_data, ctx, bot)
        finally:
            await redis.delete(_in_progress_key(domain))
    finally:
        clear_log_context()


# ---------------------------------------------------------------------------
# Ветка успеха
# ---------------------------------------------------------------------------


async def _handle_success(
    domain: str,
    new_data: WhoisData,
    old_data: WhoisData | None,
    ctx: dict[str, Any],
    bot: Bot,
) -> None:
    """UPSERT в кэш, diff, постановка уведомлений, followup."""
    now = datetime.now(tz=UTC)
    next_check = calculate_next_check(new_data.expires_at, now=now)

    fields: dict[str, Any] = {
        "expires_at": new_data.expires_at,
        "created_at_registrar": new_data.created_at,
        "updated_at_registrar": new_data.updated_at,
        "registrar": new_data.registrar,
        "status": new_data.status or None,
        "name_servers": new_data.name_servers or None,
        "raw_data": new_data.raw_data or None,
        "fetched_at": now,
        "last_successful_fetch_at": now,
        "next_check_at": next_check,
        "fail_count": 0,
        "last_error": None,
    }

    async with get_session() as session:
        cache_repo = WhoisCacheRepository(session)
        await cache_repo.upsert(domain, **fields)

    diff = compute_diff(old_data, new_data)
    if diff.has_any_changes and old_data is not None:
        await _enqueue_change_notices(domain, diff, ctx)

    # Followup для тех, кто только что сделал /add и ждёт первого ответа.
    await _flush_pending_followups(domain, new_data, ctx, bot)


async def _enqueue_change_notices(
    domain: str,
    diff: WhoisDiff,
    ctx: dict[str, Any],
) -> None:
    """Подбор подписчиков и постановка ``send_change_notice`` по типам diff'а."""
    from arq import ArqRedis

    arq_redis: ArqRedis = ctx["redis"]
    async with get_session() as session:
        domain_repo = DomainRepository(session)
        subscribers = await domain_repo.get_subscribers_for_domain(domain)

    pairs: list[tuple[str, bool, object, object]] = []
    if diff.expires_at_changed:
        pairs.append(
            (
                "expires_at",
                True,
                diff.old_values.get("expires_at"),
                diff.new_values.get("expires_at"),
            )
        )
    if diff.registrar_changed:
        pairs.append(
            ("registrar", True, diff.old_values.get("registrar"), diff.new_values.get("registrar"))
        )
    if diff.name_servers_changed:
        pairs.append(
            ("ns", True, diff.old_values.get("name_servers"), diff.new_values.get("name_servers"))
        )
    if diff.status_changed:
        pairs.append(("status", True, diff.old_values.get("status"), diff.new_values.get("status")))

    for sub in subscribers:
        for change_type, flag_default, old_val, new_val in pairs:
            if not _is_user_subscribed_to(sub, change_type, flag_default):
                continue
            await arq_redis.enqueue_job(
                "send_change_notice",
                sub.user_id,
                domain,
                change_type,
                old_val,
                new_val,
            )


def _is_user_subscribed_to(sub: UserDomain, change_type: str, _default: bool) -> bool:
    """Маппинг типа diff'а на ``UserDomain.notify_*`` флаги (ADR 012)."""
    if change_type == "expires_at":
        return bool(sub.notify_expiry)
    if change_type == "ns":
        return bool(sub.notify_ns_change)
    if change_type == "registrar":
        return bool(sub.notify_registrar_change)
    if change_type == "status":
        return bool(sub.notify_status_change)
    return False


async def _flush_pending_followups(
    domain: str,
    data: WhoisData,
    ctx: dict[str, Any],
    bot: Bot,
) -> None:
    """Шлёт followup-сообщения тем, кто только что добавил неизвестный домен.

    Множество user_id хранится в Redis set ``pending_add_followup:<domain>``,
    кладётся туда ``DomainService.add_for_user`` при ``added_pending``.
    После рассылки набор удаляется.
    """
    redis: AsyncRedis[str] = ctx["sync_redis"]
    key = _pending_followup_key(domain)
    user_ids_raw = await redis.smembers(key)
    if not user_ids_raw:
        return

    await redis.delete(key)
    parsed_ids: list[int] = []
    for raw in user_ids_raw:
        try:
            parsed_ids.append(int(raw))
        except (TypeError, ValueError):
            continue
    async with get_session() as session:
        user_repo = UserRepository(session)
        users = await user_repo.get_by_ids(parsed_ids)

    for user in users:
        try:
            text = format_whois_response(data, lang=user.language)
            await bot.send_message(chat_id=user.telegram_id, text=text)
        except Exception:
            logger.exception("Failed to send followup to %s for %s", user.id, domain)


# ---------------------------------------------------------------------------
# Ветка ошибки
# ---------------------------------------------------------------------------


async def _handle_failure(
    domain: str,
    error: WhoisError,
    ctx: dict[str, Any],
) -> None:
    """UPDATE fail_count + next_check_at; при долгих проблемах — notify."""
    from arq import ArqRedis

    arq_redis: ArqRedis = ctx["redis"]
    limits = ctx["limits"]
    now = datetime.now(tz=UTC)

    async with get_session() as session:
        cache_repo = WhoisCacheRepository(session)
        existing = await cache_repo.get(domain)
        fail_count = (existing.fail_count if existing is not None else 0) + 1
        next_check = calculate_retry_after_failure(fail_count, now=now)
        await cache_repo.update_fail(
            domain,
            error.message,
            next_check_at=next_check,
        )

    if existing is not None and _should_notify_problem(existing, fail_count, now, limits):
        async with get_session() as session:
            domain_repo = DomainRepository(session)
            subscribers = await domain_repo.get_subscribers_for_domain(domain)
        for sub in subscribers:
            await arq_redis.enqueue_job("send_problem_notice", sub.user_id, domain)


def _should_notify_problem(
    cache: WhoisCache,
    fail_count: int,
    now: datetime,
    limits: Any,
) -> bool:
    """True, если порог провалов превышен и последний успех был давно."""
    threshold = int(getattr(limits, "fail_threshold_for_user_notice", 5))
    cooldown_days = int(getattr(limits, "problem_notify_cooldown_days", 7))
    if fail_count < threshold:
        return False
    last_ok = cache.last_successful_fetch_at
    if last_ok is None:
        return False
    return now - last_ok >= timedelta(days=cooldown_days)


__all__ = ["check_domain"]
