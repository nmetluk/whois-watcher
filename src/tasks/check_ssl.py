"""ARQ-задача ``check_ssl``: одиночная проверка SSL-сертификата домена.

Параллельно ``check_domain`` для WHOIS — те же принципы:

- Redis-флаг ``ssl_check_in_progress:<domain>`` гарантирует один воркер на домен.
- Успех → UPSERT в ``ssl_cache`` + diff против старого состояния + постановка
  ``send_ssl_change_notice`` подписчикам.
- Ошибка fetch'а → ``SSLCacheRepository.update_fail`` + пересчёт
  ``next_check_at`` через ``calculate_next_ssl_check``.
- При first fetch (``old_cache is None`` или ``old.has_certificate=False``)
  — НЕ шлём уведомлений (см. фикс после Этапа 9 для WHOIS, та же логика).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from aiogram import Bot
from arq import ArqRedis
from redis.asyncio import Redis as AsyncRedis

from src.db.models import SSLCache, UserDomain
from src.db.repositories import DomainRepository, SSLCacheRepository
from src.db.session import get_session
from src.locales import t
from src.observability import bind_log_context, clear_log_context
from src.services.formatters import format_ssl_block
from src.ssl.client import fetch_certificate
from src.ssl.diff import SSLDiff, compute_ssl_diff
from src.ssl.scheduler import calculate_next_ssl_check
from src.ssl.types import SSLCertificate, SSLError

logger = logging.getLogger(__name__)


_IN_PROGRESS_TTL_SECONDS = 60


def _in_progress_key(domain: str) -> str:
    return f"ssl_check_in_progress:{domain}"


def _cache_to_certificate(cache: SSLCache) -> SSLCertificate | None:
    """Достроит ``SSLCertificate`` из строки кэша для diff-сравнения.

    Возвращает None, если в кэше нет настоящих данных (``has_certificate=False``
    или вообще ничего ещё не записывалось).
    """
    if not cache.has_certificate:
        return None
    return SSLCertificate(
        domain=cache.domain,
        is_reachable=bool(cache.is_reachable),
        has_certificate=True,
        not_before=cache.not_before,
        not_after=cache.not_after,
        issuer_cn=cache.issuer_cn,
        issuer_o=cache.issuer_o,
        subject_cn=cache.subject_cn,
        subject_alt_names=list(cache.subject_alt_names or []),
        serial_number=cache.serial_number,
        fingerprint_sha256=cache.fingerprint_sha256,
        signature_algorithm=cache.signature_algorithm,
    )


async def check_ssl(
    ctx: dict[str, Any],
    domain: str,
    deliver_chat_id: int | None = None,
    deliver_lang: str | None = None,
) -> None:
    """ARQ-задача: проверить SSL-сертификат одного домена."""
    redis: AsyncRedis[str] = ctx["sync_redis"]

    bind_log_context(domain=domain, subsystem="ssl")
    try:
        acquired = await redis.set(
            _in_progress_key(domain), "1", ex=_IN_PROGRESS_TTL_SECONDS, nx=True
        )
        if not acquired:
            logger.debug("check_ssl skipped (already in progress): %s", domain)
            return

        try:
            async with get_session() as session:
                cache_repo = SSLCacheRepository(session)
                existing = await cache_repo.get(domain)
                old_cert = _cache_to_certificate(existing) if existing is not None else None

            result = await fetch_certificate(domain)

            if isinstance(result, SSLError):
                await _handle_failure(domain, result, ctx)
                return

            await _handle_success(
                domain, result, old_cert, existing, ctx, deliver_chat_id, deliver_lang
            )
        finally:
            await redis.delete(_in_progress_key(domain))
    finally:
        clear_log_context()


# ---------------------------------------------------------------------------
# Success branch
# ---------------------------------------------------------------------------


async def _handle_success(
    domain: str,
    new_cert: SSLCertificate,
    old_cert: SSLCertificate | None,
    old_cache: SSLCache | None,
    ctx: dict[str, Any],
    deliver_chat_id: int | None = None,
    deliver_lang: str | None = None,
) -> None:
    """UPSERT в кэш, diff, постановка change-notice подписчикам."""
    now = datetime.now(tz=UTC)
    next_check = calculate_next_ssl_check(new_cert.not_after, now=now)

    fields: dict[str, Any] = {
        "last_checked_at": now,
        "last_successful_check_at": now,
        "next_check_at": next_check,
        "is_reachable": True,
        "has_certificate": True,
        "not_before": new_cert.not_before,
        "not_after": new_cert.not_after,
        "issuer_cn": new_cert.issuer_cn,
        "issuer_o": new_cert.issuer_o,
        "subject_cn": new_cert.subject_cn,
        "subject_alt_names": new_cert.subject_alt_names or None,
        "serial_number": new_cert.serial_number,
        "fingerprint_sha256": new_cert.fingerprint_sha256,
        "signature_algorithm": new_cert.signature_algorithm,
        "fail_count": 0,
        "last_error": None,
    }

    async with get_session() as session:
        cache_repo = SSLCacheRepository(session)
        await cache_repo.upsert(domain, **fields)

    # TASK-0076: доставка SSL обновления для whois карточки (если запрошено с deliver)
    if deliver_chat_id:
        bot: Bot = ctx.get("bot")  # type: ignore[assignment]
        if bot:
            try:
                async with get_session() as session:
                    cr = SSLCacheRepository(session)
                    cache = await cr.get(domain)
                if cache:
                    block = format_ssl_block(cache, lang=deliver_lang or "ru")
                    if block:
                        header = t(
                            "tasks.deliver.ssl_update", deliver_lang or "ru", domain=domain
                        )
                        await bot.send_message(deliver_chat_id, f"{header}\n{block}")
                        logger.info(
                            "Delivered SSL update to chat %s for %s", deliver_chat_id, domain
                        )
            except Exception as dexc:
                logger.warning("Failed SSL deliver to %s: %s", deliver_chat_id, dexc)

    diff = compute_ssl_diff(old_cert, new_cert)
    # Guard на «первая проверка»: даже если в old_cache была заглушка
    # (созданная ssl_scheduler'ом до первого fetch'а), реальных данных
    # ещё нет — не шлём «issuer changed» из ниоткуда.
    if diff.has_any_changes and old_cert is not None and old_cache is not None:
        await _enqueue_change_notices(domain, diff, ctx)


async def _enqueue_change_notices(
    domain: str,
    diff: SSLDiff,
    ctx: dict[str, Any],
) -> None:
    """Подбор подписчиков и постановка ``send_ssl_change_notice``."""
    arq_redis: ArqRedis = ctx["redis"]

    pairs: list[tuple[str, str]] = []
    if diff.issuer_changed:
        pairs.append(("issuer_changed", "notify_ssl_change_issuer"))
    # Ротация — тот же признак, контролируется тем же toggle что и issuer.
    # Не дублируем уведомление если issuer тоже сменился (типичный случай
    # — обновили cert, поменялся и not_after, и intermediate).
    if diff.not_after_changed and not diff.issuer_changed:
        pairs.append(("not_after_changed", "notify_ssl_change_issuer"))
    if diff.became_unreachable:
        # Сетевой сбой / TLS handshake fail — отдельный человеческий сигнал,
        # привязан к notify_ssl_expiry (этот toggle покрывает «здоровье SSL»).
        pairs.append(("became_unreachable", "notify_ssl_expiry"))
    if diff.became_reachable:
        pairs.append(("became_reachable", "notify_ssl_expiry"))

    if not pairs:
        return

    async with get_session() as session:
        domain_repo = DomainRepository(session)
        subscribers = await domain_repo.get_subscribers_for_domain(domain)

    for sub in subscribers:
        if sub.is_muted or not sub.track_ssl:
            continue
        for change_type, user_flag in pairs:
            if not getattr(sub, user_flag, False):
                continue
            await arq_redis.enqueue_job(
                "send_ssl_change_notice",
                sub.user_id,
                domain,
                change_type,
            )


# ---------------------------------------------------------------------------
# Failure branch
# ---------------------------------------------------------------------------


async def _handle_failure(
    domain: str,
    error: SSLError,
    ctx: dict[str, Any],
) -> None:
    """UPDATE fail_count + next_check_at + диф на became_unreachable.

    ВАЖНО: ``compute_ssl_diff`` считаем ПЕРЕД мутацией ``is_reachable``,
    иначе old.is_reachable уже будет False и переход не зарегистрируется.
    """
    async with get_session() as session:
        cache_repo = SSLCacheRepository(session)
        existing = await cache_repo.get(domain)

        # Снимок старого состояния — до записи fail'а.
        old_cert = _cache_to_certificate(existing) if existing is not None else None

        fail_count = (existing.fail_count if existing is not None else 0) + 1
        # Берём not_after из старой записи — adaptive scheduler не сбрасывает
        # интервал в «нет данных», если оно у нас раньше было.
        not_after = existing.not_after if existing is not None else None
        next_check = calculate_next_ssl_check(
            not_after,
            fail_count=fail_count,
            now=datetime.now(tz=UTC),
        )
        await cache_repo.update_fail(domain, error.message, next_check_at=next_check)

        # update_fail не трогает is_reachable намеренно — апдейтим вручную,
        # чтобы следующая проверка корректно отличала «уже падали» от
        # «упали в первый раз».
        if existing is not None and error.error_type != "no_https":
            existing.is_reachable = False

    # became_unreachable шлём сразу, без ожидания следующего успешного
    # fetch'а — иначе пользователь узнает о падении HTTPS с задержкой
    # в часы. compute_ssl_diff внутри проверяет old.has_certificate и
    # old.is_reachable, так что повторов не будет.
    if old_cert is None:
        return
    diff = compute_ssl_diff(old_cert, error)
    if diff.has_any_changes:
        await _enqueue_change_notices(domain, diff, ctx)


def _sub_is_ssl_active(sub: UserDomain) -> bool:  # pragma: no cover
    """Хелпер для тестов: подписка активна для SSL-уведомлений."""
    return not sub.is_muted and bool(sub.track_ssl)


__all__ = ["check_ssl"]
