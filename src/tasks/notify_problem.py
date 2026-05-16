"""Реальная ARQ-задача ``send_problem_notice``.

Срабатывает из ``check_domain._handle_failure`` при длительных проблемах с
WHOIS. Шлёт пользователю одно сообщение про проблемный домен с кнопками
«Попробовать сейчас» и «🔕 Не уведомлять».

Логика тишины: если у user_domain выключены ВСЕ четыре ``notify_*`` флага
(пользователь сделал ``/unnotify``), problem-уведомление не шлём — раз он
не хочет слышать про этот домен, значит и про проблемы тоже.
"""

from __future__ import annotations

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


def _user_wants_any_notifications(user_domain: Any) -> bool:
    """True если у пары user_domain включён хотя бы один notify_* флаг."""
    return bool(
        user_domain.notify_expiry
        or user_domain.notify_ns_change
        or user_domain.notify_registrar_change
        or user_domain.notify_status_change
    )


def _format_dt_or_never(value: datetime | None, lang: str) -> str:
    if value is None:
        return t("notifications.value.never", lang)
    return value.strftime("%d.%m.%Y")


def _format_date_or_unknown(value: datetime | None, lang: str) -> str:
    if value is None:
        return t("notifications.value.unknown", lang)
    return value.strftime("%d.%m.%Y")


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
        if user_domain is None or not _user_wants_any_notifications(user_domain):
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

        text = t(
            "notifications.problem.body",
            user.language,
            domain=domain,
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
