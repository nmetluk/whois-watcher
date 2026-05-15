"""Хэндлеры ``/add`` и ``/rmv`` — добавление и удаление доменов.

При ``added_pending`` (домен ещё не в кэше) кладём user_id в Redis-set
``pending_add_followup:<domain>``. ARQ-задача ``check_domain`` после успешной
проверки пришлёт пользователю followup-карточку.
"""

from __future__ import annotations

import logging

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from arq import ArqRedis
from redis.asyncio import Redis

from src.config.limits import Limits
from src.db.models import User
from src.db.repositories import DomainRepository, WhoisCacheRepository
from src.db.session import get_session
from src.locales import t
from src.services.domains import DomainService
from src.services.formatters import format_add_success
from src.services.whois_facade import WhoisFacade
from src.utils.idn import from_punycode

logger = logging.getLogger(__name__)

router = Router(name="add_remove")


_PENDING_FOLLOWUP_TTL = 600


@router.message(Command("add"))
async def cmd_add(
    message: Message,
    command: CommandObject,
    user: User,
    lang: str,
    arq_redis: ArqRedis,
    redis: Redis[str],
    limits: Limits,
) -> None:
    """``/add <domain>`` — добавить домен в портфель пользователя."""
    if not command.args:
        await message.answer(t("errors.no_domain", lang))
        return
    domain_input = command.args.strip().split()[0]

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
            domain_input=domain_input,
        )

    display = from_punycode(result.normalized_domain or domain_input)
    if result.status == "added" and result.whois_data is not None:
        await message.answer(
            format_add_success(
                result.whois_data, lang=lang, notify_days_label=result.notify_days_label
            )
        )
    elif result.status == "added_pending":
        # Регистрируем followup для followup'а после фоновой проверки.
        key = f"pending_add_followup:{result.normalized_domain}"
        await redis.sadd(key, str(user.id))
        await redis.expire(key, _PENDING_FOLLOWUP_TTL)
        await message.answer(t("commands.add.success_no_data", lang, domain=display))
    elif result.status == "already_tracked":
        await message.answer(t("commands.add.already_tracked", lang, domain=display))
    elif result.status == "limit_reached":
        await message.answer(t("errors.limit_reached", lang, limit=result.limit))
    else:
        await message.answer(t("errors.invalid_domain", lang))


@router.message(Command("rmv"))
async def cmd_rmv(
    message: Message,
    command: CommandObject,
    user: User,
    lang: str,
    arq_redis: ArqRedis,
    limits: Limits,
) -> None:
    """``/rmv <domain>`` — убрать домен из портфеля."""
    if not command.args:
        await message.answer(t("errors.no_domain_with_list", lang))
        return
    domain_input = command.args.strip().split()[0]

    async with get_session() as session:
        domain_repo = DomainRepository(session)
        cache_repo = WhoisCacheRepository(session)
        facade = WhoisFacade(cache_repo, arq_redis, limits)
        service = DomainService(
            domain_repo=domain_repo, cache_repo=cache_repo, facade=facade, limits=limits
        )
        result = await service.remove_for_user(user_id=user.id, domain_input=domain_input)

    display = from_punycode(result.normalized_domain or domain_input)
    if result.status == "removed":
        await message.answer(t("commands.rmv.success", lang, domain=display))
    elif result.status == "not_tracked":
        await message.answer(t("commands.rmv.not_found", lang))
    else:
        await message.answer(t("errors.invalid_domain", lang))


__all__ = ["router"]
