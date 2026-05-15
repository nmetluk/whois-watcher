"""Хэндлеры ``/delete_me`` и ``/delete_me_confirm`` (ADR 017).

Двухшаговая отмена с подтверждением:

1. ``/delete_me`` — ставит Redis-флаг ``delete_pending:{user_id}`` с TTL
   ``DELETE_ME_CONFIRM_TIMEOUT_MINUTES`` и показывает предупреждение.
2. ``/delete_me_confirm`` — проверяет флаг и удаляет пользователя
   (CASCADE на ``user_domains`` и ``sent_notifications``).

``/delete_me_confirm`` намеренно не выведена в меню BotFather (ADR 017).
"""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from redis.asyncio import Redis

from src.config.limits import Limits
from src.db.models import User
from src.db.repositories import DomainRepository, UserRepository
from src.db.session import get_session
from src.locales import t

router = Router(name="delete_me")


def _flag_key(user_id: int) -> str:
    return f"delete_pending:{user_id}"


@router.message(Command("delete_me"))
async def cmd_delete_me(
    message: Message,
    user: User,
    lang: str,
    redis: Redis[str],
    limits: Limits,
) -> None:
    """Шаг 1: показать предупреждение и поставить TTL-флаг в Redis."""
    async with get_session() as session:
        domains = DomainRepository(session)
        count = await domains.count_by_user(user.id)
    ttl_seconds = limits.delete_me_confirm_timeout_minutes * 60
    await redis.set(_flag_key(user.id), "1", ex=ttl_seconds)
    await message.answer(t("commands.delete_me.warning", lang, domains_count=count))


@router.message(Command("delete_me_confirm"))
async def cmd_delete_me_confirm(
    message: Message,
    user: User,
    lang: str,
    redis: Redis[str],
) -> None:
    """Шаг 2: при наличии флага — удалить пользователя."""
    flag = await redis.get(_flag_key(user.id))
    if flag is None:
        await message.answer(t("commands.delete_me.need_init", lang))
        return
    async with get_session() as session:
        users = UserRepository(session)
        await users.delete(user.id)
    await redis.delete(_flag_key(user.id))
    await message.answer(t("commands.delete_me.success", lang))
