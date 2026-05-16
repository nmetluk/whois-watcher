"""Хэндлер команды ``/admin`` — служебные команды для администраторов.

Доступ ограничен ``settings.admin_user_ids`` (CSV-список Telegram ID).
Не-админам — короткое отказное сообщение. В меню BotFather команда не
выводится (только знающие).

Поддерживаются:

- ``/admin stats`` — текущие агрегаты (юзеры, домены, очередь)
- ``/admin alert <текст>`` — тестовая отправка алерта в админ-канал
"""

from __future__ import annotations

import logging

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from redis.asyncio import Redis
from sqlalchemy import func, select, text

from src.config.limits import Limits
from src.config.settings import Settings
from src.db.models import User, UserDomain, WhoisCache
from src.db.session import get_session
from src.locales import t
from src.services.alerts import AlertService

logger = logging.getLogger(__name__)

router = Router(name="admin")


@router.message(Command("admin"))
async def cmd_admin(
    message: Message,
    command: CommandObject,
    user: User,
    lang: str,
    settings: Settings,
    redis: Redis[str],
    limits: Limits,
) -> None:
    """Диспетчеризация по первому аргументу ``/admin``."""
    if user.telegram_id not in set(settings.admin_user_ids):
        await message.answer(t("admin.forbidden", lang))
        return

    args = (command.args or "").strip()
    if not args:
        await message.answer(t("admin.unknown", lang))
        return

    parts = args.split(maxsplit=1)
    subcommand = parts[0].lower()
    rest = parts[1] if len(parts) > 1 else ""

    if subcommand == "stats":
        body = await _build_stats_text(lang)
        await message.answer(body)
        return

    if subcommand == "alert":
        if not rest:
            await message.answer(t("admin.alert_no_text", lang))
            return
        if settings.admin_channel_id is None:
            await message.answer(t("admin.alert_no_channel", lang))
            return
        alerts = AlertService(
            bot=message.bot,  # type: ignore[arg-type]
            redis=redis,
            settings=settings,
            limits=limits,
        )
        await alerts.send_info("manual alert", rest)
        await message.answer(t("admin.alert_sent", lang))
        return

    await message.answer(t("admin.unknown", lang))


async def _build_stats_text(lang: str) -> str:
    """Один SQL-проход на 4 счётчика — пользователи, кэш, подписки, очередь."""
    async with get_session() as session:
        users_count = (await session.execute(select(func.count()).select_from(User))).scalar_one()
        domains_count = (
            await session.execute(select(func.count()).select_from(WhoisCache))
        ).scalar_one()
        tracked_count = (
            await session.execute(select(func.count()).select_from(UserDomain))
        ).scalar_one()
        due_checks = (
            await session.execute(
                text(
                    "SELECT count(*) FROM whois_cache "
                    "WHERE next_check_at IS NOT NULL AND next_check_at <= now()"
                )
            )
        ).scalar_one()

    return t(
        "admin.stats",
        lang,
        users=int(users_count or 0),
        cached_domains=int(domains_count or 0),
        tracked=int(tracked_count or 0),
        due_checks=int(due_checks or 0),
    )


__all__ = ["router"]
