"""ARQ-задача ``send_ssl_change_notice``: уведомление об изменении SSL-сертификата.

Параллельно ``send_change_notice`` для WHOIS. Срабатывает из
``check_ssl._enqueue_change_notices`` при обнаружении diff'а:

- ``issuer_changed``: сменился CA (issuer CN или O)
- ``not_after_changed``: продлили / переподписали сертификат
- ``became_unreachable``: HTTPS-эндпоинт перестал отвечать
- ``became_reachable``: восстановился после периода недоступности
"""

from __future__ import annotations

import logging
from typing import Any

from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from src.bot.keyboards import change_notification
from src.db.repositories import DomainRepository, NotificationRepository, SSLCacheRepository
from src.db.repositories.users import UserRepository
from src.db.session import get_session
from src.locales import t

logger = logging.getLogger(__name__)


# change_type → (locale_key, notification_type для журнала, поле UserDomain)
_TYPE_MAP: dict[str, tuple[str, str, str]] = {
    "issuer_changed": (
        "notifications.ssl_change.issuer",
        "ssl_issuer_change",
        "notify_ssl_change_issuer",
    ),
    "not_after_changed": (
        "notifications.ssl_change.not_after",
        "ssl_not_after_change",
        "notify_ssl_change_issuer",
    ),
    "became_unreachable": (
        "notifications.ssl_change.unreachable",
        "ssl_unreachable",
        "notify_ssl_expiry",
    ),
    "became_reachable": (
        "notifications.ssl_change.reachable",
        "ssl_reachable",
        "notify_ssl_expiry",
    ),
}


def _format_date(value: object, lang: str) -> str:
    from datetime import datetime

    if value is None:
        return t("notifications.change.unknown", lang)
    if isinstance(value, datetime):
        return value.strftime("%d.%m.%Y")
    return str(value)


async def send_ssl_change_notice(
    ctx: dict[str, Any],
    user_id: int,
    domain: str,
    change_type: str,
) -> None:
    """Шлёт пользователю уведомление о смене SSL-сертификата."""
    bot: Bot = ctx["bot"]

    mapping = _TYPE_MAP.get(change_type)
    if mapping is None:
        logger.warning("send_ssl_change_notice: unknown change_type %r", change_type)
        return
    locale_key, notif_type, user_flag = mapping

    async with get_session() as session:
        domain_repo = DomainRepository(session)
        user_repo = UserRepository(session)
        cache_repo = SSLCacheRepository(session)

        user_domain = await domain_repo.get_for_user(user_id, domain)
        if user_domain is None or user_domain.is_muted or not user_domain.track_ssl:
            return
        if not getattr(user_domain, user_flag, False):
            return

        users = await user_repo.get_by_ids([user_id])
        if not users:
            return
        user = users[0]
        if user.is_blocked:
            return

        cache = await cache_repo.get(domain)

        format_args: dict[str, str] = {"domain": domain}
        if change_type == "issuer_changed":
            format_args["issuer"] = (
                cache.issuer_o or cache.issuer_cn or t("notifications.value.unknown", user.language)
                if cache is not None
                else t("notifications.value.unknown", user.language)
            )
        elif change_type == "not_after_changed":
            format_args["not_after"] = _format_date(
                cache.not_after if cache is not None else None, user.language
            )

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
        logger.warning("Bot blocked by user_id=%s on ssl_change_notice; marking", user_id)
        async with get_session() as session:
            user_repo = UserRepository(session)
            await user_repo.update_settings(user_id, is_blocked=True)
        return
    except TelegramBadRequest as exc:
        logger.warning(
            "send_ssl_change_notice TelegramBadRequest user=%s domain=%s: %s",
            user_id,
            domain,
            exc,
        )
        return
    except Exception:
        logger.exception("send_ssl_change_notice failed user=%s domain=%s", user_id, domain)
        return

    async with get_session() as session:
        notif_repo = NotificationRepository(session)
        await notif_repo.record_sent(
            user_id=user_id,
            domain=domain,
            notification_type=notif_type,
        )


__all__ = ["send_ssl_change_notice"]
