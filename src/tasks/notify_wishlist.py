"""ARQ-задача ``send_wishlist_available_notice`` (ADR 039).

Срабатывает из ``check_domain._enqueue_wishlist_notices`` когда отслеживаемый
wishlist-домен переходит из ``is_registered=True`` в ``False`` (освободился).

Что делает:

1. Проверяет что домен всё ещё в wishlist (через WishlistRepository.exists).
2. Шлёт сообщение с кнопками «📌 Начать отслеживать» / «OK».
3. Регистрирует факт в ``sent_notifications`` (audit log).
4. Удаляет запись из wishlist — уведомление одноразовое. При повторном
   /wishlist <domain> пользователь снова попадёт в очередь.
"""

from __future__ import annotations

import logging
from typing import Any

from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from src.db.repositories import NotificationRepository, UserRepository, WishlistRepository
from src.db.session import get_session
from src.locales import t
from src.utils.idn import from_punycode

logger = logging.getLogger(__name__)

NOTIFICATION_TYPE = "wishlist_available"


async def send_wishlist_available_notice(
    ctx: dict[str, Any],
    user_id: int,
    domain: str,
) -> None:
    """Уведомляет пользователя об освобождении wishlist-домена."""
    bot: Bot = ctx["bot"]

    async with get_session() as session:
        wishlist_repo = WishlistRepository(session)
        user_repo = UserRepository(session)

        # Проверяем что домен всё ещё в wishlist
        if not await wishlist_repo.exists(user_id, domain):
            # Пользователь уже удалил из wishlist — выходим.
            return

        users = await user_repo.get_by_ids([user_id])
        if not users:
            return
        user = users[0]
        if user.is_blocked:
            return

        lang = user.language
        telegram_id = user.telegram_id

    display = from_punycode(domain)
    title = t("notifications.wishlist.available.title", lang, domain=display)
    body = t("notifications.wishlist.available.body", lang)
    text = f"{title}\n\n{body}"
    keyboard = _build_keyboard(domain, lang=lang)

    try:
        await bot.send_message(
            chat_id=telegram_id,
            text=text,
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )
    except TelegramForbiddenError:
        logger.warning("Bot blocked by user_id=%s; marking is_blocked", user_id)
        async with get_session() as session:
            await UserRepository(session).update_settings(user_id, is_blocked=True)
        return
    except TelegramBadRequest as exc:
        logger.warning(
            "wishlist notice TelegramBadRequest user_id=%s domain=%s: %s",
            user_id,
            domain,
            exc,
        )
        return
    except Exception:
        logger.exception("wishlist notice failed user_id=%s domain=%s", user_id, domain)
        return

    # Запись в журнал + удаление wishlist-подписки (одноразовое уведомление).
    async with get_session() as session:
        notif_repo = NotificationRepository(session)
        await notif_repo.record_sent(
            user_id=user_id,
            domain=domain,
            notification_type=NOTIFICATION_TYPE,
        )
        # Удаляем из wishlist (mark_notified удаляет запись)
        await WishlistRepository(session).mark_notified(user_id, domain)


def _build_keyboard(domain: str, *, lang: str) -> Any:
    """Inline-кнопки под уведомлением.

    Импорт keyboards здесь, а не на уровне модуля — keyboards.py подтягивает
    локали, что в свою очередь утяжеляет ARQ-cold-start. Лень-импорт
    оставляет startup быстрым.
    """
    from src.bot.keyboards import wishlist_available_actions

    return wishlist_available_actions(domain, lang=lang)


__all__ = ["NOTIFICATION_TYPE", "send_wishlist_available_notice"]
