"""Скрытая команда ``/version`` — диагностика для пользователя и админа.

- Не регистрируется в меню BotFather (``src.bot.commands``)
- Не упоминается в ``/help``
- Обычному пользователю — минимальный вывод (версия + commit + время сборки):
  достаточно, чтобы сравнить со стейджем при репорте бага.
- Админу (``ADMIN_USER_IDS``) — расширенный отчёт с uptime, проверкой
  компонентов (Postgres, Redis), цифрами по таблицам и стеком версий.

Полезно когда:

- развёрнут новый релиз и хочется быстро убедиться, что у бота свежий код
- админ ловит «не работает» и хочет одним сообщением увидеть состояние стека
"""

from __future__ import annotations

import logging
import platform
import sys
import time

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from redis.asyncio import Redis
from sqlalchemy import func, select, text

from src.config.settings import Settings
from src.db.models import User, UserDomain, WhoisCache
from src.db.session import get_session
from src.utils.build_info import get_build_info
from src.utils.version import get_app_version

logger = logging.getLogger(__name__)

router = Router(name="version")

# Запоминаем монотонное время старта процесса — для uptime в /version.
# ``monotonic`` устойчиво к NTP-скачкам, в отличие от time.time().
_PROCESS_STARTED_MONOTONIC: float = time.monotonic()


@router.message(Command("version"))
async def cmd_version(
    message: Message,
    user: User,
    lang: str,
    settings: Settings,
    redis: Redis[str],
) -> None:
    """Краткая версия для всех, подробный отчёт для админов."""
    del lang  # /version намеренно англоязычная — это диагностика
    info = get_build_info()
    version = get_app_version()
    is_admin = user.telegram_id in set(settings.admin_user_ids)

    if not is_admin:
        # Простой пользователь — только то, что поможет в репорте бага.
        short = (
            f"🤖 Whois Watcher\n"
            f"Version: {version} (commit {info.git_commit_short})\n"
            f"Built:   {info.build_time}"
        )
        await message.answer(short)
        return

    # Расширенный отчёт для админа.
    uptime = _format_uptime(time.monotonic() - _PROCESS_STARTED_MONOTONIC)
    pg_version = await _postgres_version()
    redis_version, redis_ok = await _redis_info(redis)
    storage = await _storage_stats()

    github_url = (
        f"https://github.com/nmetluk/whois-watcher/tree/{info.git_commit}"
        if info.git_commit not in ("unknown", "")
        else "https://github.com/nmetluk/whois-watcher"
    )

    tag_line = f"\nTag:     {info.git_tag}" if info.git_tag else ""
    text_lines = [
        "🤖 <b>Whois Watcher</b>",
        "",
        f"Version: {version}{tag_line}",
        f"Commit:  {info.git_commit_short} ({info.git_branch})",
        f"Built:   {info.build_time}",
        f"Uptime:  {uptime}",
        f"Env:     {settings.environment}",
        "",
        f"GitHub: {github_url}",
        "",
        "Components:",
        f"  Postgres: {'✅' if pg_version else '❌'}",
        f"  Redis:    {'✅' if redis_ok else '❌'}",
        "",
        "Stack:",
        f"  Python:   {sys.version.split()[0]} ({platform.system()})",
        f"  Postgres: {pg_version or 'unreachable'}",
        f"  Redis:    {redis_version or 'unreachable'}",
        "",
        "Storage:",
        f"  Users:        {storage['users']}",
        f"  User-domains: {storage['user_domains']}",
        f"  WHOIS cache:  {storage['whois_cache']}",
        f"  Due now:      {storage['due_checks']}",
    ]
    await message.answer("\n".join(text_lines))


def _format_uptime(seconds: float) -> str:
    """``5d 3h 17m`` / ``17m 4s`` — короткий human-readable."""
    total = int(seconds)
    days, rem = divmod(total, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)
    if days:
        return f"{days}d {hours}h {minutes}m"
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


async def _postgres_version() -> str | None:
    """``SELECT version()`` → короткое имя, или None при ошибке."""
    try:
        async with get_session() as session:
            row = await session.execute(text("SELECT version()"))
            raw = row.scalar_one()
    except Exception:
        logger.exception("postgres version query failed")
        return None
    # «PostgreSQL 16.4 (Debian 16.4-1.pgdg120+1) on ...» — берём первые два слова.
    parts = str(raw).split()
    return " ".join(parts[:2]) if len(parts) >= 2 else str(raw)


async def _redis_info(redis: Redis[str]) -> tuple[str | None, bool]:
    """Возвращает ``(version, ok)``. ``ok=False`` — Redis не отвечает."""
    try:
        info = await redis.info("server")
    except Exception:
        logger.exception("redis info query failed")
        return None, False
    version = info.get("redis_version") if isinstance(info, dict) else None
    return (str(version) if version else None), True


async def _storage_stats() -> dict[str, int]:
    """Цифры по основным таблицам — те же, что и в ``/admin stats``."""
    try:
        async with get_session() as session:
            users = (await session.execute(select(func.count()).select_from(User))).scalar_one()
            udoms = (
                await session.execute(select(func.count()).select_from(UserDomain))
            ).scalar_one()
            cache = (
                await session.execute(select(func.count()).select_from(WhoisCache))
            ).scalar_one()
            due = (
                await session.execute(
                    text(
                        "SELECT count(*) FROM whois_cache "
                        "WHERE next_check_at IS NOT NULL AND next_check_at <= now()"
                    )
                )
            ).scalar_one()
    except Exception:
        logger.exception("storage stats query failed")
        return {"users": -1, "user_domains": -1, "whois_cache": -1, "due_checks": -1}
    return {
        "users": int(users or 0),
        "user_domains": int(udoms or 0),
        "whois_cache": int(cache or 0),
        "due_checks": int(due or 0),
    }


__all__ = ["router"]
