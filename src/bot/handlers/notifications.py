"""Хэндлеры ``/notify``, ``/unnotify`` (ADR 015, вариант A) и callback-кнопок
из уведомлений Этапа 5: ``refresh``, ``mute``, ``enable``.

Семантика (вариант A):

- ``/notify <domain>``   — все 4 ``notify_*`` флага возвращаются к дефолту
  (см. ``DEFAULT_NOTIFICATION_FLAGS`` в репозитории).
- ``/unnotify <domain>`` — все 4 флага становятся False.

Колбэки:

- ``NotifyAction(action="mute")``    — эквивалент ``/unnotify <domain>``
- ``NotifyAction(action="enable")``  — эквивалент ``/notify <domain>``
- ``NotifyAction(action="refresh")`` — постановка в очередь ``check_domain``
"""

from __future__ import annotations

import logging

import idna
from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, Message
from arq import ArqRedis

from src.bot.keyboards import NotifyAction, notify_enable_button
from src.db.models import User
from src.db.repositories import DomainRepository
from src.db.session import get_session
from src.locales import t
from src.utils.idn import from_punycode, normalize_domain

logger = logging.getLogger(__name__)

router = Router(name="notifications")


def _try_normalize(raw: str) -> str | None:
    """Тихая нормализация: возвращает punycode или None при невалидном входе."""
    try:
        return normalize_domain(raw)
    except (idna.IDNAError, ValueError, UnicodeError):
        return None


def _notify_days_label(days: list[int]) -> str:
    return ", ".join(str(d) for d in days)


@router.message(Command("notify"))
async def cmd_notify(message: Message, command: CommandObject, user: User, lang: str) -> None:
    """``/notify <domain>`` — включить уведомления для домена."""
    if not command.args:
        await message.answer(t("errors.no_domain_with_list", lang))
        return
    raw = command.args.strip().split()[0]
    normalized = _try_normalize(raw)
    if normalized is None:
        await message.answer(t("errors.invalid_domain", lang))
        return

    async with get_session() as session:
        domain_repo = DomainRepository(session)
        ok = await domain_repo.toggle_notifications(user.id, normalized, enabled=True)

    display = from_punycode(normalized)
    if not ok:
        await message.answer(t("errors.not_in_list", lang))
        return
    await message.answer(
        t(
            "commands.notify.success",
            lang,
            domain=display,
            notify_days=_notify_days_label(list(user.notify_days)),
        )
    )


@router.message(Command("unnotify"))
async def cmd_unnotify(message: Message, command: CommandObject, user: User, lang: str) -> None:
    """``/unnotify <domain>`` — выключить все уведомления для домена."""
    if not command.args:
        await message.answer(t("errors.no_domain_with_list", lang))
        return
    raw = command.args.strip().split()[0]
    normalized = _try_normalize(raw)
    if normalized is None:
        await message.answer(t("errors.invalid_domain", lang))
        return

    async with get_session() as session:
        domain_repo = DomainRepository(session)
        ok = await domain_repo.toggle_notifications(user.id, normalized, enabled=False)

    display = from_punycode(normalized)
    if not ok:
        await message.answer(t("errors.not_in_list", lang))
        return
    await message.answer(
        t("commands.unnotify.success", lang, domain=display),
        reply_markup=notify_enable_button(normalized, lang=lang),
    )


@router.callback_query(NotifyAction.filter(F.action == "mute"))
async def cb_mute(
    query: CallbackQuery,
    callback_data: NotifyAction,
    user: User,
    lang: str,
) -> None:
    """Колбэк «🔕 Не напоминать» / «🔕 Не уведомлять о проблемах»."""
    async with get_session() as session:
        domain_repo = DomainRepository(session)
        ok = await domain_repo.toggle_notifications(user.id, callback_data.domain, enabled=False)
    if not ok:
        await query.answer(t("notifications.ack.no_access", lang), show_alert=False)
        return
    await query.answer(t("notifications.ack.muted", lang), show_alert=False)


@router.callback_query(NotifyAction.filter(F.action == "enable"))
async def cb_enable(
    query: CallbackQuery,
    callback_data: NotifyAction,
    user: User,
    lang: str,
) -> None:
    """Колбэк «🔔 Включить обратно» (под /unnotify)."""
    async with get_session() as session:
        domain_repo = DomainRepository(session)
        ok = await domain_repo.toggle_notifications(user.id, callback_data.domain, enabled=True)
    if not ok:
        await query.answer(t("notifications.ack.no_access", lang), show_alert=False)
        return
    display = from_punycode(callback_data.domain)
    await query.answer(t("notify.on", lang, domain=display), show_alert=False)


@router.callback_query(NotifyAction.filter(F.action == "refresh"))
async def cb_refresh(
    query: CallbackQuery,
    callback_data: NotifyAction,
    user: User,
    lang: str,
    arq_redis: ArqRedis,
) -> None:
    """Колбэк «Уже продлил» / «Попробовать сейчас» — постановка в очередь."""
    async with get_session() as session:
        domain_repo = DomainRepository(session)
        owned = await domain_repo.exists(user.id, callback_data.domain)
    if not owned:
        await query.answer(t("notifications.ack.no_access", lang), show_alert=False)
        return
    await arq_redis.enqueue_job("check_domain", callback_data.domain)
    await query.answer(t("notifications.ack.refresh_started", lang), show_alert=False)


__all__ = ["router"]
