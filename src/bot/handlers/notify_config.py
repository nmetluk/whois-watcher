"""Inline-конфигуратор уведомлений для отдельного домена (Этап 11, ADR 029).

UX-цепочка:

1. Кнопка «⚙️ Уведомления» в карточке /whois → callback
   ``NotifyConfig(action="open", domain=...)`` открывает конфигуратор:
   текст с описанием текущих настроек + клавиатура из toggle'ов.
2. Toggle любого типа → ``NotifyConfig(action="toggle", field="notify_*")``
   меняет boolean в БД и перерисовывает клавиатуру (без нового сообщения).
3. «🔇 Заглушить всё» / «🔔 Снять заглушение» → ``mute_toggle``.
4. «📅 Изменить дни» → FSM ``NotifyDaysStates.waiting_for_days``.
   Пользователь вводит CSV-список, ``/default`` сбрасывает override,
   ``/cancel`` оставляет как есть.
5. «◀️ Назад» → ``close`` убирает inline-клавиатуру.

Все callback'и читают ``user_domain`` свежим из БД на каждом тапе —
тогда rerendering после toggle отражает реальное состояние, а не
predicted (UI и БД не разъезжаются при гонках).
"""

from __future__ import annotations

import logging
from contextlib import suppress
from typing import Any

from aiogram import Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.bot.keyboards import NotifyConfig, notify_config_keyboard
from src.bot.states import (
    NotifyDaysStates,
    NotifySslDaysStates,
    NotifySubdomainIntervalStates,
)
from src.config.limits import get_limits
from src.db.models import User, UserDomain
from src.db.repositories import DomainRepository, UserRepository
from src.db.session import get_session
from src.locales import t
from src.services.notifications import get_effective_notify_days
from src.utils.idn import from_punycode

logger = logging.getLogger(__name__)

router = Router(name="notify_config")


_MAX_DAYS = 365
_MAX_DAYS_COUNT = 10


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _load_user_domain(user_id: int, domain: str) -> tuple[User, UserDomain] | None:
    """Возвращает свежие ``User`` + ``UserDomain`` или ``None``, если
    домен не отслеживается."""
    async with get_session() as session:
        domain_repo = DomainRepository(session)
        user_repo = UserRepository(session)
        ud = await domain_repo.get_for_user(user_id, domain)
        if ud is None:
            return None
        users = await user_repo.get_by_ids([user_id])
        if not users:
            return None
        return users[0], ud


def _effective_ssl_days(user: User, ud: UserDomain) -> list[int]:
    """SSL-аналог ``get_effective_notify_days``: override → user default."""
    override = getattr(ud, "notify_ssl_days_override", None)
    if override:
        return list(override)
    return list(getattr(user, "notify_ssl_days_before", []) or [])


def _render_config_text(user: User, ud: UserDomain, lang: str) -> str:
    """Текст сообщения конфигуратора — заголовок + блок дней + статус mute."""
    display = from_punycode(ud.domain)
    effective_days = get_effective_notify_days(user, ud)
    days_str = ", ".join(str(d) for d in effective_days) if effective_days else "—"
    days_label_key = (
        "notify_config.days_label_custom"
        if ud.notify_days is not None
        else "notify_config.days_label_default"
    )
    ssl_days = _effective_ssl_days(user, ud)
    ssl_days_str = ", ".join(str(d) for d in ssl_days) if ssl_days else "—"
    ssl_label_key = (
        "notify_config.ssl_days_label_custom"
        if getattr(ud, "notify_ssl_days_override", None) is not None
        else "notify_config.ssl_days_label_default"
    )
    parts = [
        t("notify_config.title", lang, domain=display),
        "",
        t(days_label_key, lang, days=days_str),
        t(ssl_label_key, lang, days=ssl_days_str),
        "",
        t("notify_config.types_label", lang),
        "",
        t(
            "notify_config.muted_yes" if ud.is_muted else "notify_config.muted_no",
            lang,
        ),
    ]
    return "\n".join(parts)


def _parse_days(raw: str) -> list[int] | None:
    """Парсит CSV-строку дней. None при невалидном вводе.

    Правила:
    - целые числа от 1 до 365 включительно
    - не более 10 значений
    - дедуплицируем и сортируем по убыванию (стабильный порядок в /list)
    """
    parts = [p.strip() for p in raw.replace(";", ",").split(",") if p.strip()]
    if not parts or len(parts) > _MAX_DAYS_COUNT:
        return None
    try:
        nums = [int(p) for p in parts]
    except ValueError:
        return None
    if any(n < 1 or n > _MAX_DAYS for n in nums):
        return None
    return sorted(set(nums), reverse=True)


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------


@router.callback_query(NotifyConfig.filter())
async def on_notify_config(
    query: CallbackQuery,
    callback_data: NotifyConfig,
    user: User,
    lang: str,
    state: FSMContext,
) -> None:
    """Диспетчер всех NotifyConfig-callback'ов."""
    await query.answer()
    if not isinstance(query.message, Message):
        return
    domain = callback_data.domain
    action = callback_data.action

    if action == "close":
        with suppress(TelegramBadRequest):
            await query.message.edit_reply_markup(reply_markup=None)
        return

    if action == "edit_days":
        await state.set_state(NotifyDaysStates.waiting_for_days)
        await state.update_data(domain=domain)
        await query.message.answer(t("notify_config.days_prompt", lang))
        return

    if action == "edit_ssl_days":
        # ADR 030: отдельная FSM для SSL-дней, чтобы пользователь не
        # путал «WHOIS-дни» и «SSL-дни» — у них разные дефолты и смысл.
        await state.set_state(NotifySslDaysStates.waiting_for_days)
        await state.update_data(domain=domain)
        await query.message.answer(t("notify_config.ssl_days_prompt", lang))
        return

    if action == "edit_subdomain_interval":
        # TASK-0029, ADR 038: отдельная FSM для интервала поддоменов.
        await state.set_state(NotifySubdomainIntervalStates.waiting_for_interval)
        await state.update_data(domain=domain)
        await query.message.answer(t("notify_config.subdomain_interval_prompt", lang))
        return

    loaded = await _load_user_domain(user.id, domain)
    if loaded is None:
        await query.message.answer(t("notify_config.not_tracked", lang))
        return
    user_obj, ud = loaded

    if action == "open":
        await query.message.answer(
            _render_config_text(user_obj, ud, lang),
            reply_markup=notify_config_keyboard(ud, lang=lang),
        )
        return

    if action == "toggle":
        field = callback_data.field
        if field not in _ALLOWED_TOGGLE_FIELDS:
            logger.warning("notify_config toggle: unknown field %r", field)
            return
        new_value = not bool(getattr(ud, field))
        await _persist(user.id, domain, **{field: new_value})
        # Refresh + rerender keyboard (text не меняется — оно показывает
        # is_muted и effective_days, которые на toggle типов не зависят).
        loaded = await _load_user_domain(user.id, domain)
        if loaded is None:
            return
        _, ud2 = loaded
        with suppress(TelegramBadRequest):
            await query.message.edit_reply_markup(
                reply_markup=notify_config_keyboard(ud2, lang=lang)
            )
        return

    if action == "mute_toggle":
        new_value = not ud.is_muted
        await _persist(user.id, domain, is_muted=new_value)
        loaded = await _load_user_domain(user.id, domain)
        if loaded is None:
            return
        user_obj2, ud2 = loaded
        # При toggle mute текст меняется (показывает «muted on/off») →
        # edit_text + reply_markup одновременно.
        with suppress(TelegramBadRequest):
            await query.message.edit_text(
                _render_config_text(user_obj2, ud2, lang),
                reply_markup=notify_config_keyboard(ud2, lang=lang),
            )
        return


_ALLOWED_TOGGLE_FIELDS: frozenset[str] = frozenset(
    {
        "notify_expiry",
        "notify_registrar_change",
        "notify_ns_change",
        "notify_status_change",
        "notify_registrant_change",
        "notify_problem",
        # SSL (Этап 12, ADR 030)
        "track_ssl",
        "notify_ssl_expiry",
        "notify_ssl_change_issuer",
        # Email-intel (TASK-0018, ADR 036)
        "track_email",
        "notify_email_change",
    }
)


async def _persist(user_id: int, domain: str, **values: Any) -> None:
    async with get_session() as session:
        await DomainRepository(session).update_notification_settings(user_id, domain, **values)


# ---------------------------------------------------------------------------
# FSM: редактирование notify_days
# ---------------------------------------------------------------------------


@router.message(Command("default"), NotifyDaysStates.waiting_for_days)
async def on_default(
    message: Message,
    user: User,
    lang: str,
    state: FSMContext,
) -> None:
    """/default — сбросить override в NULL (использовать User.notify_days)."""
    data = await state.get_data()
    domain = str(data.get("domain") or "")
    await state.clear()
    if not domain:
        return
    await _persist(user.id, domain, notify_days=None)
    await message.answer(t("notify_config.days_saved_default", lang))
    await _send_refreshed_config(message, user, domain, lang)


@router.message(NotifyDaysStates.waiting_for_days)
async def on_days_input(
    message: Message,
    user: User,
    lang: str,
    state: FSMContext,
) -> None:
    """Принимает CSV-список дней. /cancel перехватывается help_cancel."""
    raw = (message.text or "").strip()
    if not raw:
        await message.answer(t("notify_config.days_prompt", lang))
        return
    days = _parse_days(raw)
    if days is None:
        # Не выходим из FSM — даём шанс ввести ещё раз.
        await message.answer(t("notify_config.days_invalid", lang))
        return

    data = await state.get_data()
    domain = str(data.get("domain") or "")
    await state.clear()
    if not domain:
        return

    await _persist(user.id, domain, notify_days=days)
    days_str = ", ".join(str(d) for d in days)
    await message.answer(t("notify_config.days_saved_override", lang, days=days_str))
    await _send_refreshed_config(message, user, domain, lang)


async def _send_refreshed_config(message: Message, user: User, domain: str, lang: str) -> None:
    """После сохранения дней — заново открываем конфигуратор, чтобы
    пользователь видел применённое значение и мог продолжить тыкать."""
    loaded = await _load_user_domain(user.id, domain)
    if loaded is None:
        return
    user_obj, ud = loaded
    await message.answer(
        _render_config_text(user_obj, ud, lang),
        reply_markup=notify_config_keyboard(ud, lang=lang),
    )


# ---------------------------------------------------------------------------
# FSM: редактирование notify_ssl_days_override (Этап 12, ADR 030)
# ---------------------------------------------------------------------------


@router.message(Command("default"), NotifySslDaysStates.waiting_for_days)
async def on_ssl_default(
    message: Message,
    user: User,
    lang: str,
    state: FSMContext,
) -> None:
    """/default — сбросить SSL-override в NULL (использовать
    ``User.notify_ssl_days_before``)."""
    data = await state.get_data()
    domain = str(data.get("domain") or "")
    await state.clear()
    if not domain:
        return
    await _persist(user.id, domain, notify_ssl_days_override=None)
    await message.answer(t("notify_config.ssl_days_saved_default", lang))
    await _send_refreshed_config(message, user, domain, lang)


@router.message(NotifySslDaysStates.waiting_for_days)
async def on_ssl_days_input(
    message: Message,
    user: User,
    lang: str,
    state: FSMContext,
) -> None:
    """Принимает CSV-список SSL-дней. /cancel перехватывается help_cancel."""
    raw = (message.text or "").strip()
    if not raw:
        await message.answer(t("notify_config.ssl_days_prompt", lang))
        return
    days = _parse_days(raw)
    if days is None:
        await message.answer(t("notify_config.days_invalid", lang))
        return

    data = await state.get_data()
    domain = str(data.get("domain") or "")
    await state.clear()
    if not domain:
        return

    await _persist(user.id, domain, notify_ssl_days_override=days)
    days_str = ", ".join(str(d) for d in days)
    await message.answer(t("notify_config.ssl_days_saved_override", lang, days=days_str))
    await _send_refreshed_config(message, user, domain, lang)


__all__ = ["router"]


# ---------------------------------------------------------------------------
# FSM: редактирование subdomain_check_interval_override (TASK-0029, ADR 038)
# ---------------------------------------------------------------------------


@router.message(Command("default"), NotifySubdomainIntervalStates.waiting_for_interval)
async def on_subdomain_interval_default(
    message: Message,
    user: User,
    lang: str,
    state: FSMContext,
) -> None:
    """/default — сбросить subdomain interval override в NULL (использовать
    ``User.subdomain_check_interval_days``)."""
    data = await state.get_data()
    domain = str(data.get("domain") or "")
    await state.clear()
    if not domain:
        return
    await _persist(user.id, domain, subdomain_check_interval_override=None)
    await message.answer(t("notify_config.subdomain_interval_saved_default", lang))
    await _send_refreshed_config(message, user, domain, lang)


@router.message(NotifySubdomainIntervalStates.waiting_for_interval)
async def on_subdomain_interval_input(
    message: Message,
    user: User,
    lang: str,
    state: FSMContext,
) -> None:
    """Принимает число — интервал проверки поддоменов (дни). /cancel перехватывается help_cancel."""
    raw = (message.text or "").strip()
    if not raw:
        await message.answer(t("notify_config.subdomain_interval_prompt", lang))
        return
    limits = get_limits()
    max_interval = limits.max_subdomain_check_interval_days

    try:
        interval = int(raw)
        if interval < 1 or interval > max_interval:
            raise ValueError
    except ValueError:
        await message.answer(t("notify_config.subdomain_interval_invalid", lang))
        return

    data = await state.get_data()
    domain = str(data.get("domain") or "")
    await state.clear()
    if not domain:
        return

    await _persist(user.id, domain, subdomain_check_interval_override=interval)
    await message.answer(
        t("notify_config.subdomain_interval_saved_override", lang, days=str(interval))
    )
    await _send_refreshed_config(message, user, domain, lang)
