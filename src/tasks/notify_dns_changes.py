"""ARQ-задача ``send_dns_change_notice``: уведомление об изменении DNS.

Параллельно ``send_ssl_change_notice``. Срабатывает из
``check_dns._enqueue_change_notices`` при обнаружении diff'а:

- ``a_changed``: сменился список A-записей
- ``aaaa_changed``: сменился список AAAA-записей
- ``ns_changed``: сменились NS-записи (обычная смена)
- ``ns_mismatch_detected``: DNS-NS != WHOIS-NS (critical)
- ``ns_mismatch_resolved``: расхождение исчезло
- ``became_unreachable``: домен перестал резолвиться
- ``became_reachable``: восстановился
"""

from __future__ import annotations

import html
import logging
from typing import Any

from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from src.bot.keyboards import change_notification
from src.db.repositories import DNSCacheRepository, DomainRepository, NotificationRepository
from src.db.repositories.users import UserRepository
from src.db.session import get_session
from src.locales import t

logger = logging.getLogger(__name__)


# change_type → (locale_key, notification_type для журнала, поле UserDomain)
_TYPE_MAP: dict[str, tuple[str, str, str]] = {
    "a_changed": (
        "notifications.dns_change.a_changed",
        "dns_a_change",
        "notify_dns_a_change",
    ),
    "aaaa_changed": (
        "notifications.dns_change.aaaa_changed",
        "dns_aaaa_change",
        "notify_dns_aaaa_change",
    ),
    "ns_changed": (
        "notifications.dns_change.ns_changed",
        "dns_ns_change",
        "notify_dns_ns_change",
    ),
    "ns_mismatch_detected": (
        "notifications.dns_change.ns_mismatch_detected",
        "dns_ns_mismatch_detected",
        "notify_dns_ns_change",
    ),
    "ns_mismatch_resolved": (
        "notifications.dns_change.ns_mismatch_resolved",
        "dns_ns_mismatch_resolved",
        "notify_dns_ns_change",
    ),
    "became_unreachable": (
        "notifications.dns_change.unreachable",
        "dns_unreachable",
        "notify_dns_unreachable",
    ),
    "became_reachable": (
        "notifications.dns_change.reachable",
        "dns_reachable",
        "notify_dns_unreachable",
    ),
}


def _format_records(records: list[str] | None) -> str:
    """Форматирует список IP/NS для текста уведомления (с HTML-escape)."""
    if not records:
        return "—"
    return ", ".join(html.escape(r) for r in records)


async def send_dns_change_notice(
    ctx: dict[str, Any],
    user_id: int,
    domain: str,
    change_type: str,
) -> None:
    """Шлёт пользователю уведомление о смене DNS-записей."""
    bot: Bot = ctx["bot"]

    mapping = _TYPE_MAP.get(change_type)
    if mapping is None:
        logger.warning("send_dns_change_notice: unknown change_type %r", change_type)
        return
    locale_key, notif_type, user_flag = mapping

    async with get_session() as session:
        domain_repo = DomainRepository(session)
        user_repo = UserRepository(session)
        cache_repo = DNSCacheRepository(session)

        user_domain = await domain_repo.get_for_user(user_id, domain)
        if user_domain is None or user_domain.is_muted or not user_domain.track_dns:
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

        # Контекстные параметры для локали
        safe_domain = html.escape(domain)
        format_args: dict[str, str] = {"domain": safe_domain}
        if cache is not None:
            if change_type == "a_changed":
                format_args["records"] = _format_records(cache.a_records)
            elif change_type == "aaaa_changed":
                format_args["records"] = _format_records(cache.aaaa_records)
            elif change_type in ("ns_changed", "ns_mismatch_detected", "ns_mismatch_resolved"):
                format_args["records"] = _format_records(cache.ns_records)

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
        logger.warning("Bot blocked by user_id=%s on dns_change_notice; marking", user_id)
        async with get_session() as session:
            user_repo = UserRepository(session)
            await user_repo.update_settings(user_id, is_blocked=True)
        return
    except TelegramBadRequest as exc:
        logger.warning(
            "send_dns_change_notice TelegramBadRequest user=%s domain=%s: %s",
            user_id,
            domain,
            exc,
        )
        return
    except Exception:
        logger.exception("send_dns_change_notice failed user=%s domain=%s", user_id, domain)
        return

    async with get_session() as session:
        notif_repo = NotificationRepository(session)
        await notif_repo.record_sent(
            user_id=user_id,
            domain=domain,
            notification_type=notif_type,
        )


__all__ = ["send_dns_change_notice"]
