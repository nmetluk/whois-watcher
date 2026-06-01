"""ARQ-задача ``send_expiry_reminder``: одиночное напоминание об истечении.

Зовётся из ``expiry_notification_scheduler`` (cron каждый час). На каждый
триггер строится одно сообщение с inline-кнопками.

Поток:

1. Дедупликация: ``NotificationRepository.was_sent`` для тройки
   (user, domain, expires_at, days_before, type='expiry'). Если уже было —
   выходим тихо.
2. Перепроверяем актуальные настройки на момент рассылки
   (``user_domain.notify_expiry``, ``user.is_blocked``).
3. Берём ``WhoisCache`` для свежего ``expires_at``/registrar.
4. Шлём сообщение через ``Bot.send_message`` с кнопками «Уже продлил» и
   «🔕 Не напоминать».
5. На ``TelegramForbiddenError`` — помечаем ``user.is_blocked = True``,
   запись в ``sent_notifications`` всё равно делаем, чтобы не дёргать снова.
6. После успешной отправки — ``record_sent`` (через UNIQUE constraint).

Идеемпотентность гарантирует UNIQUE-индекс ``uq_sent_notifications_dedup``:
два воркера, одновременно дёрнувшие одну задачу, не пошлют сообщение дважды
(второй ``record_sent`` вернёт False — caller это игнорирует).
"""

from __future__ import annotations

import html
import logging
from datetime import datetime
from typing import Any

from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from src.bot.keyboards import expiry_notification
from src.db.repositories import DomainRepository, NotificationRepository, WhoisCacheRepository
from src.db.repositories.users import UserRepository
from src.db.session import get_session
from src.locales import t

logger = logging.getLogger(__name__)


def _format_days_left(days: int, lang: str) -> str:
    """Грубое склонение «через N дней» / «in N days» без gettext-плюрализации.

    Достаточно для MVP: точная плюрализация — отдельная задача, здесь важна
    непростительная корректность только в граничных случаях (0 → «сегодня»).
    """
    if days <= 0:
        return "сегодня" if lang == "ru" else "today"
    if lang == "ru":
        last = days % 10
        last_two = days % 100
        if 11 <= last_two <= 14:
            return f"{days} дней"
        if last == 1:
            return f"{days} день"
        if 2 <= last <= 4:
            return f"{days} дня"
        return f"{days} дней"
    return f"{days} day" if days == 1 else f"{days} days"


def _format_date(value: datetime | None, lang: str) -> str:
    if value is None:
        return t("notifications.value.unknown", lang)
    return html.escape(value.strftime("%d.%m.%Y"))


async def send_expiry_reminder(
    ctx: dict[str, Any],
    user_id: int,
    domain: str,
    days_before: int,
) -> None:
    """Отправляет одно напоминание об истечении.

    Параметры приходят из планировщика; ``expires_at`` намеренно НЕ передаём
    в аргументах — он мог измениться между постановкой задачи и её
    выполнением, перечитываем из кэша. Дедупликация по ``expires_at`` из
    кэша + UNIQUE-индекс защищает от дублей при продлении.
    """
    bot: Bot = ctx["bot"]

    async with get_session() as session:
        domain_repo = DomainRepository(session)
        notif_repo = NotificationRepository(session)
        user_repo = UserRepository(session)
        cache_repo = WhoisCacheRepository(session)

        user_domain = await domain_repo.get_for_user(user_id, domain)
        if user_domain is None or not user_domain.notify_expiry:
            return

        users = await user_repo.get_by_ids([user_id])
        if not users:
            return
        user = users[0]
        if user.is_blocked:
            return

        cache = await cache_repo.get(domain)
        if cache is None or cache.expires_at is None:
            return
        expires_at = cache.expires_at

        already = await notif_repo.was_sent(
            user_id=user_id,
            domain=domain,
            notification_type="expiry",
            days_before=days_before,
            expires_at=expires_at,
        )
        if already:
            return

        registrar = cache.registrar or t("notifications.value.unknown", user.language)
        safe_registrar = html.escape(str(registrar))
        safe_domain = html.escape(domain)
        text = t(
            "notifications.expiry.body",
            user.language,
            domain=safe_domain,
            expires_at=_format_date(expires_at, user.language),
            days_left=_format_days_left(days_before, user.language),
            registrar=safe_registrar,
        )
        keyboard = expiry_notification(domain, lang=user.language)
        telegram_id = user.telegram_id

    try:
        await bot.send_message(
            chat_id=telegram_id,
            text=text,
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML,
        )
    except TelegramForbiddenError:
        logger.warning("Bot blocked by user_id=%s; marking is_blocked", user_id)
        async with get_session() as session:
            user_repo = UserRepository(session)
            notif_repo = NotificationRepository(session)
            await user_repo.update_settings(user_id, is_blocked=True)
            # Записываем в журнал, чтобы не дёргать на следующих тиках
            await notif_repo.record_sent(
                user_id=user_id,
                domain=domain,
                notification_type="expiry",
                days_before=days_before,
                expires_at=expires_at,
            )
        return
    except TelegramBadRequest as exc:
        logger.warning(
            "send_message TelegramBadRequest user_id=%s domain=%s: %s",
            user_id,
            domain,
            exc,
        )
        # Не помечаем blocked, но и не записываем — пусть повторится на
        # следующем тике, может быть транзиентная ошибка.
        return
    except Exception:
        logger.exception("send_expiry_reminder failed for user_id=%s domain=%s", user_id, domain)
        return

    async with get_session() as session:
        notif_repo = NotificationRepository(session)
        await notif_repo.record_sent(
            user_id=user_id,
            domain=domain,
            notification_type="expiry",
            days_before=days_before,
            expires_at=expires_at,
        )


__all__ = ["send_expiry_reminder"]
