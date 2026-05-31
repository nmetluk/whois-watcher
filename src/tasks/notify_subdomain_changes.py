"""ARQ-задача ``notify_subdomain_changes``: уведомление о новых/исчезнувших поддоменах (TASK-0029, ADR 038).

Параллельно ``send_ssl_change_notice`` для SSL. Срабатывает из
``check_subdomains`` при обнаружении diff'а:

- ``new``: появились новые поддомены
- ``removed``: исчезнувшие поддомены

Fan-out: рассылает **всем** подписчикам registrable-домена с
``track_subdomains=true``, honoring per-type toggle'ы и ``is_muted``.
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


async def notify_subdomain_changes(
    ctx: dict[str, Any],
    registrable_domain: str,
    diff: dict[str, list[str]],
) -> None:
    """Рассылает уведомления о новых/исчезнувших поддоменах подписчикам registrable.

    Args:
        ctx: ARQ context
        registrable_domain: Registrable-домен (eTLD+1, ADR 035)
        diff: {"new": [...], "removed": [...]}
    """
    bot: Bot = ctx["bot"]
    new_subdomains = diff.get("new", [])
    removed_subdomains = diff.get("removed", [])

    if not new_subdomains and not removed_subdomains:
        return

    async with get_session() as session:
        domain_repo = DomainRepository(session)
        user_repo = UserRepository(session)

        # Находим всех подписчиков registrable-домена с track_subdomains=true
        subscribers = await domain_repo.get_subscribers_by_registrable(
            registrable_domain=registrable_domain,
            track_subdomains=True,
        )

        notified_users: set[int] = set()

        for user_domain in subscribers:
            user_id = user_domain.user_id

            # Дедуп: одному пользователю — одно уведомление
            if user_id in notified_users:
                continue

            # is_muted kill-switch
            if user_domain.is_muted:
                continue

            users = await user_repo.get_by_ids([user_id])
            if not users:
                continue
            user = users[0]
            if user.is_blocked:
                continue

            # Формируем текст уведомления
            lines: list[str] = [f"<b>{registrable_domain}</b> —"]

            if new_subdomains and user_domain.notify_subdomain_new:
                lines.append(t("notifications.subdomain.new_header", user.language))
                for subdomain in new_subdomains[:5]:  # максимум 5 в сообщении
                    lines.append(f"  🆕 {subdomain}")
                if len(new_subdomains) > 5:
                    lines.append(
                        t(
                            "notifications.subdomain.and_more",
                            user.language,
                            count=len(new_subdomains) - 5,
                        )
                    )

            if removed_subdomains and user_domain.notify_subdomain_removed:
                if lines[-1] != f"<b>{registrable_domain}</b> —":
                    lines.append("")  # пустая строка-разделитель
                lines.append(t("notifications.subdomain.removed_header", user.language))
                for subdomain in removed_subdomains[:5]:
                    lines.append(f"  ➖ {subdomain}")
                if len(removed_subdomains) > 5:
                    lines.append(
                        t(
                            "notifications.subdomain.and_more",
                            user.language,
                            count=len(removed_subdomains) - 5,
                        )
                    )

            # Если в lines только заголовок — пропускаем (пустое уведомление)
            if len(lines) <= 1:
                continue

            text_body = "\n".join(lines)
            keyboard = change_notification(registrable_domain, lang=user.language)
            telegram_id = user.telegram_id

            try:
                await bot.send_message(
                    chat_id=telegram_id,
                    text=text_body,
                    reply_markup=keyboard,
                    parse_mode=ParseMode.HTML,
                )
                notified_users.add(user_id)
            except TelegramForbiddenError:
                logger.warning("Bot blocked by user_id=%s on subdomain_change; marking", user_id)
                await user_repo.update_settings(user_id, is_blocked=True)
                continue
            except TelegramBadRequest as exc:
                logger.warning(
                    "notify_subdomain_changes TelegramBadRequest user=%s registrable=%s: %s",
                    user_id,
                    registrable_domain,
                    exc,
                )
                continue
            except Exception:
                logger.exception(
                    "notify_subdomain_changes failed user=%s registrable=%s",
                    user_id,
                    registrable_domain,
                )
                continue

            # Записываем в журнал (раздельно для new и removed)
            notif_repo = NotificationRepository(session)
            if new_subdomains and user_domain.notify_subdomain_new:
                await notif_repo.record_sent(
                    user_id=user_id,
                    domain=registrable_domain,
                    notification_type="subdomain_new",
                )
            if removed_subdomains and user_domain.notify_subdomain_removed:
                await notif_repo.record_sent(
                    user_id=user_id,
                    domain=registrable_domain,
                    notification_type="subdomain_removed",
                )


__all__ = ["notify_subdomain_changes"]
