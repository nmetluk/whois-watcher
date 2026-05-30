"""Хэндлер ``/wishlist`` и связанные callback'и (ADR 039).

Wishlist — режим, где пользователь добавляет ЗАНЯТЫЙ домен и получает
**одноразовое** уведомление, когда WHOIS показывает, что домен освободился
(``is_registered=False``). После уведомления запись автоматически удаляется
(см. ``src.tasks.notify_wishlist``).

Команды:

- ``/wishlist <domain>`` — добавить
- ``/wishlist`` — показать текущий wishlist

Inline-кнопка ``WhoisAction(action='wishlist')`` из карточки /whois добавляет
домен в wishlist (теперь независимо от tracking).

Callback ``WishlistAction(action='track')`` из уведомления «домен
освободился» добавляет тот же домен как обычную подписку (через
DomainService.add_for_user) и удаляет из wishlist.
"""

from __future__ import annotations

import logging

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, Message
from arq import ArqRedis
from redis.asyncio import Redis

from src.bot.keyboards import WishlistAction, list_pagination
from src.config.limits import Limits
from src.db.models import User
from src.db.repositories import WhoisCacheRepository, WishlistRepository
from src.db.session import get_session
from src.locales import t
from src.services.domains import DomainService
from src.services.formatters import format_list_row
from src.services.whois_facade import WhoisFacade
from src.utils.idn import from_punycode, normalize_domain

logger = logging.getLogger(__name__)

router = Router(name="wishlist")

_LIST_PAGE_SIZE = 50


# ---------------------------------------------------------------------------
# /wishlist
# ---------------------------------------------------------------------------


@router.message(Command("wishlist"))
async def cmd_wishlist(
    message: Message,
    command: CommandObject,
    user: User,
    lang: str,
    arq_redis: ArqRedis,
    limits: Limits,
) -> None:
    """``/wishlist`` без аргумента → список; с аргументом → добавить.

    FSM-flow из ADR 033 НЕ применяется к этой команде — у неё уже есть
    осмысленное поведение для пустого аргумента (показать список).
    """
    args = (command.args or "").strip()
    if not args:
        await _show_wishlist(message=message, user=user, lang=lang)
        return
    await _add_to_wishlist(
        message=message,
        user=user,
        lang=lang,
        domain_input=args.split()[0],
        arq_redis=arq_redis,
        limits=limits,
    )


async def _show_wishlist(*, message: Message, user: User, lang: str) -> None:
    async with get_session() as session:
        wishlist_repo = WishlistRepository(session)
        rows, total = await wishlist_repo.list_with_whois(
            user.id,
            limit=_LIST_PAGE_SIZE,
            offset=0,
        )

    if not rows:
        await message.answer(t("commands.wishlist.empty", lang))
        return

    header = t(
        "commands.wishlist.header",
        lang,
        total=total,
        page=1,
        total_pages=max(1, (total + _LIST_PAGE_SIZE - 1) // _LIST_PAGE_SIZE),
    )
    # format_list_row ожидает UserDomain, но Wishlist имеет те же поля для отображения
    # (domain, registrable_domain, is_subdomain, added_at) — используем type: ignore
    body_rows = [format_list_row(wishlist, cache, lang=lang) for wishlist, cache in rows]  # type: ignore[arg-type]
    body = header + "\n\n" + "\n".join(body_rows)
    keyboard = list_pagination(
        0, max(1, (total + _LIST_PAGE_SIZE - 1) // _LIST_PAGE_SIZE), lang=lang
    )
    await message.answer(body, reply_markup=keyboard)


async def _add_to_wishlist(
    *,
    message: Message,
    user: User,
    lang: str,
    domain_input: str,
    arq_redis: ArqRedis,
    limits: Limits,
) -> None:
    """Нормализует домен, проверяет лимиты, добавляет в wishlist.

    Если домен СЕЙЧАС свободен (по кэшу) — не добавляем, а советуем /add.
    Если домена нет в кэше вообще — добавляем и ставим первичную проверку:
    после неё может сразу сработать wishlist-уведомление (если домен
    оказался свободным).
    """
    try:
        normalized = normalize_domain(domain_input)
    except Exception:
        await message.answer(t("errors.invalid_domain", lang))
        return

    async with get_session() as session:
        wishlist_repo = WishlistRepository(session)
        cache_repo = WhoisCacheRepository(session)

        # Лимит wishlist — та же квота, что и tracking
        current = await wishlist_repo.count_by_user(user.id)
        if current >= limits.max_domains_per_user:
            await message.answer(t("errors.limit_reached", lang, limit=limits.max_domains_per_user))
            return

        cached = await cache_repo.get(normalized)
        if cached is not None and cached.expires_at is None and cached.registrar is None:
            # В кэше «пустая» запись (свежеcreated до /add). Это не
            # «домен свободен» — это «ещё не проверили».
            cached = None

        # Если домен в кэше зарегистрирован — добавляем в wishlist.
        # Если в кэше пусто — добавляем + триггерим проверку.
        added = await wishlist_repo.add(user.id, normalized)
        if added is None:
            # Уже в wishlist
            await message.answer(
                t("commands.wishlist.already_added", lang, domain=from_punycode(normalized))
            )
            return

        if cached is None or cached.expires_at is None:
            await cache_repo.upsert(normalized)
            facade = WhoisFacade(cache_repo, arq_redis, limits)
            await facade.enqueue_check(normalized)

    await message.answer(t("commands.wishlist.added", lang, domain=from_punycode(normalized)))


# ---------------------------------------------------------------------------
# Callback'и из уведомления «домен освободился»
# ---------------------------------------------------------------------------


@router.callback_query(WishlistAction.filter())
async def on_wishlist_action(
    query: CallbackQuery,
    callback_data: WishlistAction,
    user: User,
    lang: str,
    arq_redis: ArqRedis,
    limits: Limits,
    redis: Redis[str],
) -> None:
    """``track`` — добавить как обычный домен и убрать из wishlist; ``dismiss`` — просто закрыть."""
    del redis
    domain = callback_data.domain
    await query.answer()
    if not isinstance(query.message, Message):
        return

    if callback_data.action == "dismiss":
        await query.message.edit_reply_markup(reply_markup=None)
        return

    if callback_data.action == "track":
        async with get_session() as session:
            from src.db.repositories import DomainRepository

            domain_repo = DomainRepository(session)
            wishlist_repo = WishlistRepository(session)
            cache_repo = WhoisCacheRepository(session)
            facade = WhoisFacade(cache_repo, arq_redis, limits)
            service = DomainService(
                domain_repo=domain_repo,
                cache_repo=cache_repo,
                facade=facade,
                limits=limits,
            )
            result = await service.add_for_user(
                user_id=user.id,
                notify_days=list(user.notify_days),
                domain_input=domain,
            )
            # Убираем из wishlist (переход «слежу вместо ожидания»)
            await wishlist_repo.remove(user.id, domain)

        display = from_punycode(result.normalized_domain or domain)
        if result.status in ("added", "added_pending"):
            await query.message.answer(t("commands.wishlist.tracked_now", lang, domain=display))
        elif result.status == "already_tracked":
            await query.message.answer(t("commands.add.already_tracked", lang, domain=display))
        elif result.status == "limit_reached":
            await query.message.answer(t("errors.limit_reached", lang, limit=result.limit))
        else:
            await query.message.answer(t("errors.invalid_domain", lang))


__all__ = ["router"]
