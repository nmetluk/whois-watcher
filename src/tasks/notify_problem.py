"""Реальная ARQ-задача ``send_problem_notice``.

Срабатывает из ``check_domain._handle_failure`` при длительных проблемах с
WHOIS. Шлёт пользователю одно сообщение про проблемный домен с кнопками
«Попробовать сейчас» и «🔕 Не уведомлять».

Логика тишины (Этап 11, ADR 029):

- ``UserDomain.is_muted=True`` — kill-switch, ничего не шлём.
- ``UserDomain.notify_problem=False`` — конкретно problem-уведомления
  выключены для этого домена.
"""

from __future__ import annotations

import html
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from src.bot.keyboards import problem_notification
from src.db.repositories import DomainRepository, NotificationRepository, WhoisCacheRepository
from src.db.repositories.users import UserRepository
from src.db.session import get_session
from src.locales import t

logger = logging.getLogger(__name__)


def _user_wants_problem_notice(user_domain: Any) -> bool:
    """True, если для пары user_domain разрешено problem-уведомление.

    Этап 11 (ADR 029): отдельный per-domain toggle ``notify_problem``
    + kill-switch ``is_muted``. Раньше использовалось «есть ли хоть один
    включённый notify_* флаг» — это была эвристика, теперь явный флаг.
    """
    if user_domain.is_muted:
        return False
    return bool(user_domain.notify_problem)


def _format_dt_or_never(value: datetime | None, lang: str) -> str:
    if value is None:
        return t("notifications.value.never", lang)
    return html.escape(value.strftime("%d.%m.%Y"))


def _format_date_or_unknown(value: datetime | None, lang: str) -> str:
    if value is None:
        return t("notifications.value.unknown", lang)
    return html.escape(value.strftime("%d.%m.%Y"))


async def send_problem_notice(ctx: dict[str, Any], user_id: int, domain: str) -> None:
    """Уведомляет пользователя о длительных WHOIS-проблемах с доменом."""
    bot: Bot = ctx["bot"]
    limits = ctx["limits"]
    cooldown_days = int(getattr(limits, "problem_notify_cooldown_days", 7))
    now = datetime.now(tz=UTC)

    async with get_session() as session:
        domain_repo = DomainRepository(session)
        user_repo = UserRepository(session)
        cache_repo = WhoisCacheRepository(session)

        user_domain = await domain_repo.get_for_user(user_id, domain)
        if user_domain is None or not _user_wants_problem_notice(user_domain):
            return

        # Cooldown: не чаще раза в N дней
        last = user_domain.last_problem_notified_at
        if last is not None and (now - last) < timedelta(days=cooldown_days):
            return

        users = await user_repo.get_by_ids([user_id])
        if not users:
            return
        user = users[0]
        if user.is_blocked:
            return

        cache = await cache_repo.get(domain)
        last_ok = cache.last_successful_fetch_at if cache is not None else None
        expires_at = cache.expires_at if cache is not None else None

        safe_domain = html.escape(domain)
        text = t(
            "notifications.problem.body",
            user.language,
            domain=safe_domain,
            last_ok=_format_dt_or_never(last_ok, user.language),
            expires_at=_format_date_or_unknown(expires_at, user.language),
        )
        keyboard = problem_notification(domain, lang=user.language)
        telegram_id = user.telegram_id

    try:
        await bot.send_message(
            chat_id=telegram_id,
            text=text,
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML,
        )
    except TelegramForbiddenError:
        logger.warning("Bot blocked by user_id=%s on problem_notice; marking", user_id)
        async with get_session() as session:
            user_repo = UserRepository(session)
            await user_repo.update_settings(user_id, is_blocked=True)
        return
    except TelegramBadRequest as exc:
        logger.warning(
            "send_problem_notice TelegramBadRequest user_id=%s domain=%s: %s",
            user_id,
            domain,
            exc,
        )
        return
    except Exception:
        logger.exception("send_problem_notice failed user_id=%s domain=%s", user_id, domain)
        return

    async with get_session() as session:
        domain_repo = DomainRepository(session)
        notif_repo = NotificationRepository(session)
        await domain_repo.mark_problem_notified(user_id, domain, at=now)
        await notif_repo.record_sent(
            user_id=user_id,
            domain=domain,
            notification_type="problem",
        )


__all__ = ["send_problem_notice"]
