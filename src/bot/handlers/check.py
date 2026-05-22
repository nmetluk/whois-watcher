"""Хэндлер ``/check <domain>`` — принудительное обновление WHOIS-данных.

Алиас кнопки «Обновить» в карточке ``/whois``. Имеет тот же cooldown через
Redis-флаг ``force_refresh:{user_id}:{domain}`` (TTL ``FORCE_REFRESH_COOLDOWN_HOURS``).
"""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from arq import ArqRedis
from redis.asyncio import Redis

from src.bot.handlers.whois import _send_whois_card
from src.bot.states import AwaitingDomainArg
from src.config.limits import Limits
from src.db.models import User
from src.locales import t
from src.utils.idn import normalize_domain

router = Router(name="check")


def _key(user_id: int, domain: str) -> str:
    return f"force_refresh:{user_id}:{domain}"


@router.message(Command("check"))
async def cmd_check(
    message: Message,
    command: CommandObject,
    user: User,
    lang: str,
    arq_redis: ArqRedis,
    redis: Redis[str],
    limits: Limits,
    state: FSMContext,
) -> None:
    if not command.args:
        # ADR 033.
        await state.set_state(AwaitingDomainArg.waiting)
        await state.update_data(cmd="check", token_map={})
        await message.answer(t("commands.cmd_arg.prompt", lang, cmd="check"))
        return
    raw = command.args.strip().split()[0]
    try:
        normalized = normalize_domain(raw)
    except Exception:
        await message.answer(t("errors.invalid_domain", lang))
        return

    ttl_seconds = limits.force_refresh_cooldown_hours * 3600
    acquired = await redis.set(_key(user.id, normalized), "1", ex=ttl_seconds, nx=True)
    if not acquired:
        await message.answer(
            t("errors.force_refresh_cooldown", lang, hours=limits.force_refresh_cooldown_hours)
        )
        return

    await _send_whois_card(
        message=message,
        domain_input=normalized,
        user=user,
        lang=lang,
        arq_redis=arq_redis,
        limits=limits,
        force_refresh=True,
    )


__all__ = ["router"]
