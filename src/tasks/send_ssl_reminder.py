"""ARQ-задача ``send_ssl_expiry_reminder``: одиночное напоминание об
истечении SSL-сертификата.

Параллельно ``send_expiry_reminder`` для WHOIS:

1. Дедупликация через ``NotificationRepository`` (тип ``ssl_expiry``,
   ключ — ``days_before`` + ``not_after`` как ``expires_at``).
2. Перепроверка актуальных флагов на момент рассылки
   (``is_muted``, ``track_ssl``, ``notify_ssl_expiry``).
3. Берём свежий ``ssl_cache`` для ``not_after`` (мог измениться между
   постановкой задачи и её выполнением).
4. Отправляем сообщение через ``Bot.send_message``.
5. На ``TelegramForbiddenError`` — помечаем ``user.is_blocked = True``
   и всё равно ``record_sent``, чтобы не дёргать заново.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from src.bot.keyboards import ssl_expiry_notification
from src.db.repositories import DomainRepository, NotificationRepository, SSLCacheRepository
from src.db.repositories.users import UserRepository
from src.db.session import get_session
from src.locales import t

logger = logging.getLogger(__name__)


def _format_days_left(days: int, lang: str) -> str:
    """Готовая «through-фраза» для подстановки в шаблон уведомления.

    Возвращает уже с предлогом — «через N дней» / «in N days» / «сегодня» /
    «today», чтобы шаблон оставался плоским ``{days_left}`` без «(через …)»
    обёртки, которая на ``days=0`` ломается («через сегодня»).
    """
    if days <= 0:
        return "сегодня" if lang == "ru" else "today"
    if lang == "ru":
        last = days % 10
        last_two = days % 100
        if 11 <= last_two <= 14:
            tail = "дней"
        elif last == 1:
            tail = "день"
        elif 2 <= last <= 4:
            tail = "дня"
        else:
            tail = "дней"
        return f"через {days} {tail}"
    unit = "day" if days == 1 else "days"
    return f"in {days} {unit}"


def _format_date(value: datetime | None, lang: str) -> str:
    if value is None:
        return t("notifications.value.unknown", lang)
    return value.strftime("%d.%m.%Y")


async def send_ssl_expiry_reminder(
    ctx: dict[str, Any],
    user_id: int,
    domain: str,
    days_before: int,
) -> None:
    """Одно напоминание об истечении SSL-сертификата."""
    bot: Bot = ctx["bot"]

    async with get_session() as session:
        domain_repo = DomainRepository(session)
        notif_repo = NotificationRepository(session)
        user_repo = UserRepository(session)
        cache_repo = SSLCacheRepository(session)

        user_domain = await domain_repo.get_for_user(user_id, domain)
        if user_domain is None or user_domain.is_muted:
            return
        if not user_domain.track_ssl or not user_domain.notify_ssl_expiry:
            return

        users = await user_repo.get_by_ids([user_id])
        if not users:
            return
        user = users[0]
        if user.is_blocked:
            return

        cache = await cache_repo.get(domain)
        if cache is None or cache.not_after is None or not cache.has_certificate:
            return
        not_after = cache.not_after

        already = await notif_repo.was_sent(
            user_id=user_id,
            domain=domain,
            notification_type="ssl_expiry",
            days_before=days_before,
            expires_at=not_after,
        )
        if already:
            return

        issuer = cache.issuer_o or cache.issuer_cn or t("notifications.value.unknown", user.language)
        text_body = t(
            "notifications.ssl_expiry.body",
            user.language,
            domain=domain,
            not_after=_format_date(not_after, user.language),
            days_left=_format_days_left(days_before, user.language),
            issuer=issuer,
        )
        keyboard = ssl_expiry_notification(domain, lang=user.language)
        telegram_id = user.telegram_id

    try:
        await bot.send_message(
            chat_id=telegram_id,
            text=text_body,
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML,
        )
    except TelegramForbiddenError:
        logger.warning("Bot blocked by user_id=%s on ssl reminder; marking", user_id)
        async with get_session() as session:
            user_repo = UserRepository(session)
            notif_repo = NotificationRepository(session)
            await user_repo.update_settings(user_id, is_blocked=True)
            await notif_repo.record_sent(
                user_id=user_id,
                domain=domain,
                notification_type="ssl_expiry",
                days_before=days_before,
                expires_at=not_after,
            )
        return
    except TelegramBadRequest as exc:
        logger.warning(
            "send_ssl_expiry_reminder TelegramBadRequest user=%s domain=%s: %s",
            user_id,
            domain,
            exc,
        )
        return
    except Exception:
        logger.exception("send_ssl_expiry_reminder failed user=%s domain=%s", user_id, domain)
        return

    async with get_session() as session:
        notif_repo = NotificationRepository(session)
        await notif_repo.record_sent(
            user_id=user_id,
            domain=domain,
            notification_type="ssl_expiry",
            days_before=days_before,
            expires_at=not_after,
        )


__all__ = ["send_ssl_expiry_reminder"]
