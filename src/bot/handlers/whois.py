"""Хэндлеры ``/whois`` и связанных callback-кнопок («следить», «снять»,
«обновить», «полный ответ»).

Тонкий слой: парсит ввод, зовёт сервис, рендерит ответ. Бизнес-логика —
в ``DomainService`` / ``WhoisFacade``.
"""

from __future__ import annotations

import io
import logging

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from arq import ArqRedis
from redis.asyncio import Redis

from src.bot.keyboards import WhoisAction, whois_actions
from src.config.limits import Limits
from src.db.models import User
from src.db.repositories import DomainRepository, WhoisCacheRepository
from src.db.session import get_session
from src.locales import t
from src.services.domains import DomainService
from src.services.formatters import format_whois_response
from src.services.whois_facade import WhoisFacade
from src.utils.idn import from_punycode

logger = logging.getLogger(__name__)

router = Router(name="whois")


# Cooldown между принудительными обновлениями (часов). Ключ Redis:
# ``force_refresh:{user_id}:{domain}``.
def _force_refresh_key(user_id: int, domain: str) -> str:
    return f"force_refresh:{user_id}:{domain}"


# ---------------------------------------------------------------------------
# /whois <domain>
# ---------------------------------------------------------------------------


@router.message(Command("whois"))
async def cmd_whois(
    message: Message,
    command: CommandObject,
    user: User,
    lang: str,
    arq_redis: ArqRedis,
    limits: Limits,
) -> None:
    """Показать WHOIS-карточку домена."""
    if not command.args:
        await message.answer(t("errors.no_domain", lang))
        return
    domain_input = command.args.strip().split()[0]
    await _send_whois_card(
        message=message,
        domain_input=domain_input,
        user=user,
        lang=lang,
        arq_redis=arq_redis,
        limits=limits,
        force_refresh=False,
    )


async def _send_whois_card(
    *,
    message: Message,
    domain_input: str,
    user: User,
    lang: str,
    arq_redis: ArqRedis,
    limits: Limits,
    force_refresh: bool,
) -> None:
    """Общий путь для ``/whois``, ``/check`` и plain-text триггера."""
    async with get_session() as session:
        cache_repo = WhoisCacheRepository(session)
        domain_repo = DomainRepository(session)
        facade = WhoisFacade(cache_repo, arq_redis, limits)
        service = DomainService(
            domain_repo=domain_repo, cache_repo=cache_repo, facade=facade, limits=limits
        )
        result = await service.lookup_for_user(domain_input, force_refresh=force_refresh)
        if result.error is not None or result.data is None:
            reason = result.error.message if result.error else "no data"
            await message.answer(
                t("errors.whois_failed", lang, domain=from_punycode(domain_input), reason=reason)
            )
            return
        is_tracked = await domain_repo.exists(user.id, result.data.domain)
        # ``fetched_at`` для «откуда данные» — берём из самой свежей записи кэша.
        cached = await cache_repo.get(result.data.domain)
        fetched_at = cached.fetched_at if cached is not None else None

    body = format_whois_response(result.data, lang=lang, fetched_at=fetched_at)
    if result.is_stale:
        body = t("errors.whois_stale", lang, days=result.stale_age_days) + "\n\n" + body
    await message.answer(
        body,
        reply_markup=whois_actions(result.data.domain, is_tracked=is_tracked, lang=lang),
    )


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------


@router.callback_query(WhoisAction.filter())
async def on_whois_action(
    query: CallbackQuery,
    callback_data: WhoisAction,
    user: User,
    lang: str,
    arq_redis: ArqRedis,
    redis: Redis[str],
    limits: Limits,
) -> None:
    """Один обработчик на все 4 кнопки карточки WHOIS."""
    action = callback_data.action
    domain = callback_data.domain
    await query.answer()

    if not isinstance(query.message, Message):
        return

    if action == "follow":
        await _track(
            query.message,
            user=user,
            lang=lang,
            domain=domain,
            arq_redis=arq_redis,
            redis=redis,
            limits=limits,
        )
    elif action == "unfollow":
        await _untrack(
            query.message,
            user=user,
            lang=lang,
            domain=domain,
            arq_redis=arq_redis,
            limits=limits,
        )
    elif action == "refresh":
        await _force_refresh(
            query=query,
            user=user,
            lang=lang,
            domain=domain,
            arq_redis=arq_redis,
            redis=redis,
            limits=limits,
        )
    elif action == "raw":
        await _send_raw(query.message, lang=lang, domain=domain)


async def _track(
    message: Message,
    *,
    user: User,
    lang: str,
    domain: str,
    arq_redis: ArqRedis,
    redis: Redis[str],
    limits: Limits,
) -> None:
    """Добавить домен пользователю (кнопка «Следить»)."""
    async with get_session() as session:
        domain_repo = DomainRepository(session)
        cache_repo = WhoisCacheRepository(session)
        facade = WhoisFacade(cache_repo, arq_redis, limits)
        service = DomainService(
            domain_repo=domain_repo, cache_repo=cache_repo, facade=facade, limits=limits
        )
        result = await service.add_for_user(
            user_id=user.id,
            notify_days=list(user.notify_days),
            domain_input=domain,
        )

    display = from_punycode(result.normalized_domain or domain)
    if result.status == "added" and result.whois_data is not None:
        from src.services.formatters import format_add_success

        await message.answer(
            format_add_success(
                result.whois_data, lang=lang, notify_days_label=result.notify_days_label
            )
        )
    elif result.status == "added_pending":
        await _register_pending_followup(
            redis=redis, domain=result.normalized_domain, user_id=user.id
        )
        await message.answer(t("commands.add.success_no_data", lang, domain=display))
    elif result.status == "already_tracked":
        await message.answer(t("commands.add.already_tracked", lang, domain=display))
    elif result.status == "limit_reached":
        await message.answer(t("errors.limit_reached", lang, limit=result.limit))
    else:
        await message.answer(t("errors.invalid_domain", lang))


async def _untrack(
    message: Message,
    *,
    user: User,
    lang: str,
    domain: str,
    arq_redis: ArqRedis,
    limits: Limits,
) -> None:
    """Снять домен со слежения (кнопка «Снять»)."""
    async with get_session() as session:
        domain_repo = DomainRepository(session)
        cache_repo = WhoisCacheRepository(session)
        facade = WhoisFacade(cache_repo, arq_redis, limits)
        service = DomainService(
            domain_repo=domain_repo, cache_repo=cache_repo, facade=facade, limits=limits
        )
        result = await service.remove_for_user(user_id=user.id, domain_input=domain)
    display = from_punycode(result.normalized_domain or domain)
    if result.status == "removed":
        await message.answer(t("commands.rmv.success", lang, domain=display))
    elif result.status == "not_tracked":
        await message.answer(t("commands.rmv.not_found", lang))
    else:
        await message.answer(t("errors.invalid_domain", lang))


async def _force_refresh(
    *,
    query: CallbackQuery,
    user: User,
    lang: str,
    domain: str,
    arq_redis: ArqRedis,
    redis: Redis[str],
    limits: Limits,
) -> None:
    """Кнопка «Обновить» — live-lookup с rate-limit cooldown."""
    if not isinstance(query.message, Message):
        return
    key = _force_refresh_key(user.id, domain)
    ttl_seconds = limits.force_refresh_cooldown_hours * 3600
    acquired = await redis.set(key, "1", ex=ttl_seconds, nx=True)
    if not acquired:
        await query.answer(
            t("errors.force_refresh_cooldown", lang, hours=limits.force_refresh_cooldown_hours),
            show_alert=True,
        )
        return
    await _send_whois_card(
        message=query.message,
        domain_input=domain,
        user=user,
        lang=lang,
        arq_redis=arq_redis,
        limits=limits,
        force_refresh=True,
    )


async def _send_raw(message: Message, *, lang: str, domain: str) -> None:
    """Кнопка «Полный ответ» — отдаём raw_data как .txt-файл."""
    async with get_session() as session:
        cache_repo = WhoisCacheRepository(session)
        cached = await cache_repo.get(domain)
    if cached is None or not cached.raw_data:
        await message.answer(t("errors.whois_unavailable", lang))
        return
    raw = cached.raw_data.get("raw_text") or str(cached.raw_data)
    buffer = io.BytesIO(raw.encode("utf-8"))
    await message.answer_document(
        BufferedInputFile(buffer.getvalue(), filename=f"{domain}.whois.txt")
    )


async def _register_pending_followup(
    *,
    redis: Redis[str],
    domain: str,
    user_id: int,
) -> None:
    """Кладёт user_id в set ``pending_add_followup:<domain>`` с TTL 10 минут.

    ARQ-задача ``check_domain`` после успешной проверки прочитает set и
    отправит карточку WHOIS этим пользователям.
    """
    key = f"pending_add_followup:{domain}"
    await redis.sadd(key, str(user_id))
    await redis.expire(key, 600)


__all__ = ["router"]
