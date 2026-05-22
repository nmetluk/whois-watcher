"""Хэндлер ``/wishlist`` и связанные callback'и (Этап 9).

Wishlist — режим, где пользователь добавляет ЗАНЯТЫЙ домен и получает
**одноразовое** уведомление, когда WHOIS показывает, что домен освободился
(``is_registered=False``). После уведомления подписка автоматически
снимается — см. ``src.tasks.notify_wishlist``.

Команды:

- ``/wishlist <domain>`` — добавить
- ``/wishlist`` — показать текущий wishlist (как /list с фильтром wishlist)

Inline-кнопка ``WhoisAction(action='wishlist')`` из карточки /whois
переводит фокус-домен в wishlist одним нажатием.

Callback ``WishlistAction(action='track')`` из уведомления «домен
освободился» добавляет тот же домен обратно, но уже как обычную
подписку (через DomainService.add_for_user).
"""

from __future__ import annotations

import logging

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from arq import ArqRedis
from redis.asyncio import Redis

from src.bot.keyboards import WishlistAction
from src.bot.states import AwaitingDomainArg
from src.config.limits import Limits
from src.db.models import User
from src.db.repositories import DomainRepository, WhoisCacheRepository
from src.db.session import get_session
from src.locales import t
from src.services.domains import DomainService
from src.services.whois_facade import WhoisFacade
from src.utils.idn import from_punycode, normalize_domain

logger = logging.getLogger(__name__)

router = Router(name="wishlist")


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
    state: FSMContext,
) -> None:
    """``/wishlist`` — без аргумента запускает FSM-flow (ADR 033), с
    аргументом добавляет домен в wishlist.

    Просмотр текущего wishlist доступен через ``/list`` → фильтр
    «🎯 Wishlist» (см. ``ListFilter(name="wishlist")``).
    """
    args = (command.args or "").strip()
    if not args:
        # ADR 033.
        await state.set_state(AwaitingDomainArg.waiting)
        await state.update_data(cmd="wishlist", token_map={})
        await message.answer(t("commands.cmd_arg.prompt", lang, cmd="wishlist"))
        return
    await _add_to_wishlist(
        message=message,
        user=user,
        lang=lang,
        domain_input=args.split()[0],
        arq_redis=arq_redis,
        limits=limits,
    )


async def _add_to_wishlist(
    *,
    message: Message,
    user: User,
    lang: str,
    domain_input: str,
    arq_redis: ArqRedis,
    limits: Limits,
) -> None:
    """Нормализует домен, проверяет лимиты, ставит is_wishlist=True.

    Если домен СЕЙЧАС свободен (по кэшу) — не добавляем, а советуем /add.
    Если домена нет в кэше вообще — добавляем и ставим первичную проверку:
    после неё may immediately fire wishlist-уведомление (если домен
    оказался свободным).
    """
    try:
        normalized = normalize_domain(domain_input)
    except Exception:
        await message.answer(t("errors.invalid_domain", lang))
        return

    async with get_session() as session:
        domain_repo = DomainRepository(session)
        cache_repo = WhoisCacheRepository(session)

        # Лимит: используем ту же квоту, что и tracking — wishlist живёт
        # в той же таблице. Спецификация может ужесточить позже.
        current = await domain_repo.count_by_user(user.id)
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
        await domain_repo.add_to_wishlist(user.id, normalized)
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
    """``track`` — добавить как обычный домен; ``dismiss`` — просто закрыть."""
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
            domain_repo = DomainRepository(session)
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
