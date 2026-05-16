"""Реальная ARQ-задача ``send_change_notice``.

Срабатывает из ``check_domain._enqueue_change_notices`` при обнаружении diff'а.
Шлёт пользователю одно сообщение про конкретный тип изменения с inline-кнопкой
«Открыть домен».
"""

from __future__ import annotations

import logging
from datetime import datetime
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


# Карта типа diff'а из check_domain → ключ локали + ``notification_type``
# в журнале sent_notifications + поле UserDomain для проверки.
_TYPE_MAP: dict[str, tuple[str, str, str]] = {
    "registrar": (
        "notifications.change.registrar",
        "registrar_change",
        "notify_registrar_change",
    ),
    "ns": ("notifications.change.ns", "ns_change", "notify_ns_change"),
    "status": ("notifications.change.status", "status_change", "notify_status_change"),
    "expires_at": (
        "notifications.change.expires_at",
        "expiry_change",
        "notify_expiry",
    ),
}


def _format_value(value: object, lang: str) -> str:
    if value is None:
        return t("notifications.change.unknown", lang)
    if isinstance(value, list):
        return (
            ", ".join(str(item) for item in value)
            if value
            else t("notifications.change.unknown", lang)
        )
    if isinstance(value, datetime):
        return value.strftime("%d.%m.%Y")
    return str(value)


async def send_change_notice(
    ctx: dict[str, Any],
    user_id: int,
    domain: str,
    change_type: str,
    old_value: object,
    new_value: object,
) -> None:
    """Уведомляет пользователя о смене значения у его домена."""
    bot: Bot = ctx["bot"]

    mapping = _TYPE_MAP.get(change_type)
    if mapping is None:
        logger.warning("send_change_notice: unknown change_type %r", change_type)
        return
    locale_key, notif_type, user_flag = mapping

    async with get_session() as session:
        domain_repo = DomainRepository(session)
        user_repo = UserRepository(session)

        user_domain = await domain_repo.get_for_user(user_id, domain)
        if user_domain is None or not getattr(user_domain, user_flag):
            return

        users = await user_repo.get_by_ids([user_id])
        if not users:
            return
        user = users[0]
        if user.is_blocked:
            return

        text = t(
            locale_key,
            user.language,
            domain=domain,
            old=_format_value(old_value, user.language),
            new=_format_value(new_value, user.language),
        )
        keyboard = change_notification(domain, lang=user.language)
        telegram_id = user.telegram_id

    try:
        await bot.send_message(
            chat_id=telegram_id,
            text=text,
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML,
        )
    except TelegramForbiddenError:
        logger.warning("Bot blocked by user_id=%s on change_notice; marking", user_id)
        async with get_session() as session:
            user_repo = UserRepository(session)
            await user_repo.update_settings(user_id, is_blocked=True)
        return
    except TelegramBadRequest as exc:
        logger.warning(
            "send_change_notice TelegramBadRequest user_id=%s domain=%s: %s",
            user_id,
            domain,
            exc,
        )
        return
    except Exception:
        logger.exception("send_change_notice failed user_id=%s domain=%s", user_id, domain)
        return

    async with get_session() as session:
        notif_repo = NotificationRepository(session)
        # expires_at не закладываем — для change-уведомлений важен факт смены,
        # а не снапшот; повторных дублей не ждём, потому что diff формируется
        # один раз на проверку (см. check_domain.compute_diff).
        await notif_repo.record_sent(
            user_id=user_id,
            domain=domain,
            notification_type=notif_type,
        )


__all__ = ["send_change_notice"]
