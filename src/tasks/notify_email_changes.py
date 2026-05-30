"""ARQ-задача ``send_email_change_notice``: уведомление об изменении email-intel.

Параллельно ``send_ssl_change_notice`` для SSL. Срабатывает из
``check_email_intel._enqueue_change_notices`` при обнаружении diff'а:

- ``mx_changed``: изменился список MX-записей
- ``spf_changed``: изменилась SPF-запись
- ``dmarc_changed``: изменился DMARC
- ``dkim_changed``: изменился список DKIM-селекторов
- ``became_unreachable``: DNS-резолв перестал работать
- ``became_reachable``: восстановился после периода недоступности
"""

from __future__ import annotations

import logging
from typing import Any

from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from src.bot.keyboards import change_notification
from src.db.repositories import DomainRepository, NotificationRepository
from src.db.repositories.users import UserRepository
from src.db.session import get_session
from src.locales import t

logger = logging.getLogger(__name__)


# change_type → (locale_key, notification_type для журнала, поле UserDomain)
_TYPE_MAP: dict[str, tuple[str, str, str]] = {
    "mx_changed": (
        "notifications.email_change.mx",
        "email_mx_change",
        "notify_email_mx",
    ),
    "spf_changed": (
        "notifications.email_change.spf",
        "email_spf_change",
        "notify_email_spf",
    ),
    "dmarc_changed": (
        "notifications.email_change.dmarc",
        "email_dmarc_change",
        "notify_email_dmarc",
    ),
    "dkim_changed": (
        "notifications.email_change.dkim",
        "email_dkim_change",
        "notify_email_dkim",
    ),
    "became_unreachable": (
        "notifications.email_change.unreachable",
        "email_unreachable",
        "notify_email_mx",
    ),
    "became_reachable": (
        "notifications.email_change.reachable",
        "email_reachable",
        "notify_email_mx",
    ),
}


async def send_email_change_notice(
    ctx: dict[str, Any],
    user_id: int,
    domain: str,
    change_type: str,
) -> None:
    """Шлёт пользователю уведомление о смене email-intel."""
    bot: Bot = ctx["bot"]

    mapping = _TYPE_MAP.get(change_type)
    if mapping is None:
        logger.warning("send_email_change_notice: unknown change_type %r", change_type)
        return
    locale_key, notif_type, user_flag = mapping

    async with get_session() as session:
        domain_repo = DomainRepository(session)
        user_repo = UserRepository(session)

        user_domain = await domain_repo.get_for_user(user_id, domain)
        if user_domain is None or user_domain.is_muted or not user_domain.track_email:
            return
        if not getattr(user_domain, user_flag, False):
            return

        users = await user_repo.get_by_ids([user_id])
        if not users:
            return
        user = users[0]
        if user.is_blocked:
            return

        format_args: dict[str, str] = {"domain": domain}

        text_body = t(locale_key, user.language, **format_args)
        keyboard = change_notification(domain, lang=user.language)
        telegram_id = user.telegram_id

    try:
        await bot.send_message(
            chat_id=telegram_id,
            text=text_body,
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML,
        )
    except TelegramForbiddenError:
        logger.warning("Bot blocked by user_id=%s on email_change_notice; marking", user_id)
        async with get_session() as session:
            user_repo = UserRepository(session)
            await user_repo.update_settings(user_id, is_blocked=True)
        return
    except TelegramBadRequest as exc:
        logger.warning(
            "send_email_change_notice TelegramBadRequest user=%s domain=%s: %s",
            user_id,
            domain,
            exc,
        )
        return
    except Exception:
        logger.exception("send_email_change_notice failed user=%s domain=%s", user_id, domain)
        return

    async with get_session() as session:
        notif_repo = NotificationRepository(session)
        await notif_repo.record_sent(
            user_id=user_id,
            domain=domain,
            notification_type=notif_type,
        )


__all__ = ["send_email_change_notice"]
