"""FSM-flow для команд с обязательным доменом-аргументом (ADR 033).

Когда пользователь шлёт ``/add``, ``/rmv``, ``/check``, ``/notify``
или ``/unnotify`` без аргумента, соответствующий handler переводит
сессию в ``AwaitingDomainArg.waiting`` и пишет prompt. ``/wishlist``
из этого flow выпадает: у него уже есть осмысленное поведение для
пустого аргумента (показать список wishlist'а), и его собственный
handler не ставит state.

Дальше работает этот роутер:

1. ``on_domain_input`` — FSM-text-handler. Валидирует ввод, кладёт пару
   ``(cmd, domain)`` в FSM-data под коротким токеном и показывает
   confirm с кнопками ✅/❌.
2. ``on_confirm`` — callback-handler для CmdArgCallback. По «Да» вызывает
   тот же handler-функцию, что и inline-форма ``/<cmd> <domain>``,
   через синтетический ``CommandObject``. По «Нет» — пишет cancelled и
   чистит state.
"""

from __future__ import annotations

import logging
import uuid

from aiogram import F, Router
from aiogram.filters import CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from arq import ArqRedis
from redis.asyncio import Redis

from src.bot.handlers import add_remove
from src.bot.handlers import check as check_handler
from src.bot.handlers import notifications as notifications_handler
from src.bot.keyboards import CmdArgCallback, cmd_arg_confirm_kb
from src.bot.states import AwaitingDomainArg
from src.bot.validators import extract_domain_from_text, is_valid_domain
from src.config.limits import Limits
from src.db.models import User
from src.locales import t
from src.utils.idn import from_punycode, normalize_domain

logger = logging.getLogger(__name__)

router = Router(name="awaiting_arg")


# Поддерживаемые команды + соответствующие handler-функции. Имена
# совпадают с command-литералом в ``Command("...")``.
SUPPORTED_COMMANDS: frozenset[str] = frozenset({"add", "rmv", "check", "notify", "unnotify"})


def _extract_domains(text: str) -> list[str]:
    """Возвращает все валидные домены, упомянутые в сообщении (punycode-форма).

    Используется для веток 0/1/many в ``on_domain_input``. Порядок —
    как в исходном тексте, дубликаты сохраняются (фильтр первого
    домена в ``too_many`` берёт его естественно).
    """
    if not text:
        return []
    found: list[str] = []
    seen: set[str] = set()

    stripped = text.strip()
    if stripped and is_valid_domain(stripped):
        try:
            normalized = normalize_domain(stripped)
            if normalized not in seen:
                found.append(normalized)
                seen.add(normalized)
        except (ValueError, UnicodeError):
            pass

    # Запасной путь — извлечь из произвольного текста (URL, фразы и т. п.).
    if not found:
        candidate = extract_domain_from_text(text)
        if candidate and candidate not in seen:
            found.append(candidate)
            seen.add(candidate)

    return found


def _make_token() -> str:
    """Короткий идентификатор для callback_data (8 hex)."""
    return uuid.uuid4().hex[:8]


# ---------------------------------------------------------------------------
# FSM-text-handler — ловит ответ пользователя в state AwaitingDomainArg.waiting
# ---------------------------------------------------------------------------


@router.message(AwaitingDomainArg.waiting, F.text, ~F.text.startswith("/"))
async def on_domain_input(message: Message, state: FSMContext, lang: str) -> None:
    """Принимает ввод пользователя, валидирует, показывает confirm."""
    text = message.text or ""
    domains = _extract_domains(text)

    if not domains:
        # Не похоже на домен — state НЕ чистим, даём попробовать ещё раз.
        await message.answer(t("commands.cmd_arg.invalid", lang, input=text.strip()[:64]))
        return

    data = await state.get_data()
    cmd = str(data.get("cmd", ""))
    if cmd not in SUPPORTED_COMMANDS:
        # Сюда не должны попасть — но если state-data битый, выходим тихо.
        await state.clear()
        return

    domain = domains[0]
    token = _make_token()
    token_map: dict[str, str] = dict(data.get("token_map") or {})
    token_map[token] = domain
    await state.update_data(token_map=token_map)

    display = from_punycode(domain)
    if len(domains) > 1:
        await message.answer(
            t("commands.cmd_arg.too_many", lang, domain=display),
            reply_markup=cmd_arg_confirm_kb(token, lang=lang),
        )
    else:
        await message.answer(
            t("commands.cmd_arg.confirm", lang, cmd=cmd, domain=display),
            reply_markup=cmd_arg_confirm_kb(token, lang=lang),
        )


# ---------------------------------------------------------------------------
# Callback-handler — «Да» / «Нет» под confirm
# ---------------------------------------------------------------------------


@router.callback_query(CmdArgCallback.filter())
async def on_confirm(
    query: CallbackQuery,
    callback_data: CmdArgCallback,
    state: FSMContext,
    user: User,
    lang: str,
    arq_redis: ArqRedis,
    redis: Redis[str],
    limits: Limits,
) -> None:
    """Обрабатывает «✅ Да» / «❌ Нет» из confirm-сообщения."""
    await query.answer()
    if not isinstance(query.message, Message):
        # Старое сообщение, недоступное для редактирования.
        return

    data = await state.get_data()
    token_map: dict[str, str] = dict(data.get("token_map") or {})
    cmd = str(data.get("cmd", ""))
    domain = token_map.get(callback_data.token)

    if domain is None or cmd not in SUPPORTED_COMMANDS:
        # Stale-callback: state протух/сменился/бот рестартовал.
        await query.message.edit_text(t("commands.cmd_arg.stale", lang))
        return

    if callback_data.action == "no":
        await query.message.edit_text(t("commands.cmd_arg.cancelled", lang))
        await state.clear()
        return

    if callback_data.action != "yes":
        return

    display = from_punycode(domain)
    await query.message.edit_text(t("commands.cmd_arg.executing", lang, cmd=cmd, domain=display))
    # Чистим state ДО вызова handler'а, чтобы повторный confirm не
    # триггерил повторное выполнение.
    await state.clear()

    await _dispatch(
        cmd=cmd,
        domain=domain,
        message=query.message,
        user=user,
        lang=lang,
        arq_redis=arq_redis,
        redis=redis,
        limits=limits,
        state=state,
    )


# ---------------------------------------------------------------------------
# Диспетчер: cmd → исходный handler с синтетическим CommandObject
# ---------------------------------------------------------------------------


def _make_command(cmd: str, domain: str) -> CommandObject:
    """Синтетический ``CommandObject`` — как если бы пришло ``/<cmd> <domain>``."""
    return CommandObject(prefix="/", command=cmd, mention=None, args=domain)


async def _dispatch(
    *,
    cmd: str,
    domain: str,
    message: Message,
    user: User,
    lang: str,
    arq_redis: ArqRedis,
    redis: Redis[str],
    limits: Limits,
    state: FSMContext,
) -> None:
    """Зовёт настоящий handler команды через тот же путь, что и inline-форма.

    Каждая cmd-функция уже знает, что делать с непустым ``command.args``
    — мы только подставляем тот же ``Message`` (на самом деле — confirm-
    сообщение от бота, но ``message.answer()`` ответит в тот же чат) и
    нужный набор DI-deps.
    """
    command = _make_command(cmd, domain)

    if cmd == "add":
        await add_remove.cmd_add(
            message=message,
            command=command,
            user=user,
            lang=lang,
            arq_redis=arq_redis,
            redis=redis,
            limits=limits,
            state=state,
        )
    elif cmd == "rmv":
        await add_remove.cmd_rmv(
            message=message,
            command=command,
            user=user,
            lang=lang,
            arq_redis=arq_redis,
            limits=limits,
            state=state,
        )
    elif cmd == "check":
        await check_handler.cmd_check(
            message=message,
            command=command,
            user=user,
            lang=lang,
            arq_redis=arq_redis,
            redis=redis,
            limits=limits,
            state=state,
        )
    elif cmd == "notify":
        await notifications_handler.cmd_notify(
            message=message,
            command=command,
            user=user,
            lang=lang,
            state=state,
        )
    elif cmd == "unnotify":
        await notifications_handler.cmd_unnotify(
            message=message,
            command=command,
            user=user,
            lang=lang,
            state=state,
        )


__all__ = ["router", "SUPPORTED_COMMANDS"]
