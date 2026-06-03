"""Хэндлеры ``/whois`` и связанных callback-кнопок («следить», «снять»,
«обновить», «полный ответ»).

Тонкий слой: парсит ввод, зовёт сервис, рендерит ответ. Бизнес-логика —
в ``DomainService`` / ``WhoisFacade``.
"""

from __future__ import annotations

import io
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, Literal

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import BufferedInputFile, CallbackQuery, InlineKeyboardMarkup, Message
from arq import ArqRedis
from redis.asyncio import Redis

from src.bot.keyboards import WhoisAction, subdomains_keyboard, whois_actions
from src.config.limits import Limits
from src.db.models import EmailDeepCache, SubdomainEnumCache, User
from src.db.repositories import (
    DNSCacheRepository,
    DomainRepository,
    EmailDeepCacheRepository,
    EmailIntelCacheRepository,
    SSLCacheRepository,
    SubdomainEnumCacheRepository,
    WhoisCacheRepository,
    WishlistRepository,
)
from src.db.session import get_session
from src.locales import t
from src.services.domains import DomainService
from src.services.formatters import (
    format_dns_block,
    format_email_block,
    format_email_deep,
    format_pending_block,
    format_ssl_block,
    format_whois_response,
)
from src.services.formatters_full import build_full_text_from_cache_row
from src.services.whois_facade import WhoisFacade
from src.utils.domains import is_public_suffix_only, is_subdomain, registrable_domain
from src.utils.formatting import format_date
from src.utils.idn import from_punycode, normalize_domain

logger = logging.getLogger(__name__)

router = Router(name="whois")


# Cooldown между принудительными обновлениями (часов). Ключ Redis:
# ``force_refresh:{user_id}:{domain}``.
def _force_refresh_key(user_id: int, domain: str) -> str:
    return f"force_refresh:{user_id}:{domain}"


# ---------------------------------------------------------------------------
# /whois <domain>
# ---------------------------------------------------------------------------


@router.message(Command("whois"))
async def cmd_whois(
    message: Message,
    command: CommandObject,
    user: User,
    lang: str,
    arq_redis: ArqRedis,
    limits: Limits,
) -> None:
    """Показать WHOIS-карточку домена."""
    if not command.args:
        await message.answer(t("errors.no_domain", lang))
        return
    domain_input = command.args.strip().split()[0]
    # TASK-0005: проверка на публичный суффикс. Мусорный ввод не должен
    # ронять хэндлер — невалидное пусть обработается ниже штатно
    # (idna.IDNAError — подкласс UnicodeError).
    try:
        is_suffix_only = is_public_suffix_only(domain_input)
    except (ValueError, UnicodeError):
        is_suffix_only = False
    if is_suffix_only:
        await message.answer(t("errors.public_suffix_not_domain", lang))
        return
    await _send_whois_card(
        message=message,
        domain_input=domain_input,
        user=user,
        lang=lang,
        arq_redis=arq_redis,
        limits=limits,
        force_refresh=False,
    )


async def _send_whois_card(
    *,
    message: Message,
    domain_input: str,
    user: User,
    lang: str,
    arq_redis: ArqRedis,
    limits: Limits,
    force_refresh: bool,
) -> None:
    """Общий путь для ``/whois``, ``/check`` и plain-text триггера."""
    async with get_session() as session:
        cache_repo = WhoisCacheRepository(session)
        domain_repo = DomainRepository(session)
        wishlist_repo = WishlistRepository(session)
        facade = WhoisFacade(cache_repo, arq_redis, limits)
        service = DomainService(
            domain_repo=domain_repo, cache_repo=cache_repo, facade=facade, limits=limits
        )
        result = await service.lookup_for_user(domain_input, force_refresh=force_refresh)
        if result.error is not None or result.data is None:
            reason = result.error.message if result.error else "no data"
            await message.answer(
                t("errors.whois_failed", lang, domain=from_punycode(domain_input), reason=reason)
            )
            return

        # TASK-0013: mypy type narrowing — сохранить результат проверки выше
        assert result.data is not None  # mypy narrowing (is_subdomain below resets it)

        # TASK-0005: определяем поддомен
        is_sub = is_subdomain(domain_input)
        # TASK-0013: mypy narrowing — явный if/else вместо тернарника, чтобы
        # mypy понимал, что lookup_domain не None в обеих ветках
        if is_sub:
            parent = registrable_domain(domain_input)
            lookup_domain = parent
        else:
            lookup_domain = result.data.domain

        is_tracked = await domain_repo.exists(user.id, lookup_domain)
        # ADR 039: проверяем наличие в wishlist для кнопки "убрать из wishlist"
        is_wishlisted = await wishlist_repo.exists(user.id, lookup_domain)
        # ``fetched_at`` для «откуда данные» — берём из самой свежей записи кэша.
        cached = await cache_repo.get(lookup_domain)
        fetched_at = cached.fetched_at if cached is not None else None
        # ADR 030: SSL-блок берём из общего ssl_cache. Если данных ещё нет —
        # планируем фоновую проверку, чтобы карточка в следующий раз показала
        # сертификат. Сама задача защищена от задвоения redis-флагом.
        ssl_repo = SSLCacheRepository(session)
        # TASK-0005: для поддоменов берём SSL из поддомена, а не родителя
        ssl_target = domain_input if is_sub else lookup_domain
        ssl_cache = await ssl_repo.get(ssl_target)
        if ssl_cache is None:
            await ssl_repo.upsert(ssl_target)
            await arq_redis.enqueue_job(
                "check_ssl", ssl_target, deliver_chat_id=message.chat.id, deliver_lang=lang
            )
        # ADR 032: DNS-блок аналогично — bootstrap + enqueue check_dns. Сама
        # задача защищена redis-флагом dns_check_in_progress.
        dns_repo = DNSCacheRepository(session)
        # TASK-0005: для поддоменов берём DNS из поддомена, а не родителя
        dns_target = domain_input if is_sub else lookup_domain
        dns_cache = await dns_repo.get(dns_target)
        if dns_cache is None:
            await dns_repo.upsert(dns_target)
            await arq_redis.enqueue_job(
                "check_dns", dns_target, deliver_chat_id=message.chat.id, deliver_lang=lang
            )
        # ADR 036: Email-intel блок аналогично — bootstrap + enqueue check_email_intel.
        # Сама задача защищена redis-флагом email_check_in_progress.
        email_repo = EmailIntelCacheRepository(session)
        # TASK-0005 + ADR 036: для поддоменов берём email из поддомена, а не родителя
        email_target = domain_input if is_sub else lookup_domain
        email_cache = await email_repo.get(email_target)
        if email_cache is None:
            await email_repo.upsert(email_target)
            await arq_redis.enqueue_job(
                "check_email_intel",
                email_target,
                deliver_chat_id=message.chat.id,
                deliver_lang=lang,
            )
        whois_ns = list(cached.name_servers or []) if cached is not None else None

    # Формируем тело карточки
    body_parts = []
    # TASK-0005: баннер для поддомена
    if is_sub and parent:
        body_parts.append(
            t(
                "commands.whois.subdomain_banner",
                lang,
                subdomain=from_punycode(domain_input),
                parent=from_punycode(parent),
            )
        )
        body_parts.append("")

    body_parts.append(format_whois_response(result.data, lang=lang, fetched_at=fetched_at))

    # TASK-0040 (ADR 040): показываем pending placeholder вместо пропуска,
    # когда кэш ещё не наполнен (мы только что заэнкьюили проверку).
    ssl_block = format_ssl_block(ssl_cache, lang=lang)
    if ssl_block is None:
        ssl_block = format_pending_block(t("commands.whois.ssl_section", lang), lang=lang)
    body_parts.append(ssl_block)

    dns_block = format_dns_block(dns_cache, whois_ns=whois_ns, lang=lang)
    if dns_block is None:
        dns_block = format_pending_block(t("commands.whois.dns_section", lang), lang=lang)
    body_parts.append(dns_block)

    email_block = format_email_block(email_cache, lang=lang)
    if email_block is None:
        email_block = format_pending_block(t("commands.whois.email_section", lang), lang=lang)
    body_parts.append(email_block)
    if result.is_stale:
        body_parts.insert(
            0 if not is_sub else 2,
            t("errors.whois_stale", lang, days=result.stale_age_days),
        )

    body = "\n\n".join(body_parts)
    await message.answer(
        body,
        reply_markup=whois_actions(
            lookup_domain, is_tracked=is_tracked, is_wishlisted=is_wishlisted, lang=lang
        ),
    )


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------


@router.callback_query(WhoisAction.filter())
async def on_whois_action(
    query: CallbackQuery,
    callback_data: WhoisAction,
    user: User,
    lang: str,
    arq_redis: ArqRedis,
    redis: Redis[str],
    limits: Limits,
) -> None:
    """Один обработчик на все 4 кнопки карточки WHOIS."""
    action = callback_data.action
    domain = callback_data.domain
    await query.answer()

    if not isinstance(query.message, Message):
        return

    if action == "follow":
        await _track(
            query.message,
            user=user,
            lang=lang,
            domain=domain,
            arq_redis=arq_redis,
            redis=redis,
            limits=limits,
        )
    elif action == "unfollow":
        await _untrack(
            query.message,
            user=user,
            lang=lang,
            domain=domain,
            arq_redis=arq_redis,
            limits=limits,
        )
    elif action == "refresh":
        await _force_refresh(
            query=query,
            user=user,
            lang=lang,
            domain=domain,
            arq_redis=arq_redis,
            redis=redis,
            limits=limits,
        )
    elif action == "raw":
        await _send_raw(query.message, lang=lang, domain=domain)
    elif action == "subdomains":
        await _show_subdomains_from_whois_card(
            query=query,
            user=user,
            lang=lang,
            domain=domain,
            arq_redis=arq_redis,
        )
    elif action == "deep_email":
        await _show_deep_email_from_whois_card(
            query=query,
            user=user,
            lang=lang,
            domain=domain,
            arq_redis=arq_redis,
        )
    elif action == "wishlist":
        await _add_to_wishlist_shortcut(
            query.message,
            user=user,
            lang=lang,
            domain=domain,
            arq_redis=arq_redis,
            limits=limits,
        )
    elif action == "unwishlist":
        await _remove_from_wishlist(
            query.message,
            user=user,
            lang=lang,
            domain=domain,
        )


async def _track(
    message: Message,
    *,
    user: User,
    lang: str,
    domain: str,
    arq_redis: ArqRedis,
    redis: Redis[str],
    limits: Limits,
) -> None:
    """Добавить домен пользователю (кнопка «Следить»)."""
    async with get_session() as session:
        domain_repo = DomainRepository(session)
        cache_repo = WhoisCacheRepository(session)
        facade = WhoisFacade(cache_repo, arq_redis, limits)
        service = DomainService(
            domain_repo=domain_repo, cache_repo=cache_repo, facade=facade, limits=limits
        )
        result = await service.add_for_user(
            user_id=user.id,
            notify_days=list(user.notify_days),
            domain_input=domain,
        )

    display = from_punycode(result.normalized_domain or domain)
    if result.status == "added" and result.whois_data is not None:
        from src.services.formatters import format_add_success

        await message.answer(
            format_add_success(
                result.whois_data, lang=lang, notify_days_label=result.notify_days_label
            )
        )
    elif result.status == "added_pending":
        await _register_pending_followup(
            redis=redis, domain=result.normalized_domain, user_id=user.id
        )
        await message.answer(t("commands.add.success_no_data", lang, domain=display))
    elif result.status == "already_tracked":
        await message.answer(t("commands.add.already_tracked", lang, domain=display))
    elif result.status == "limit_reached":
        await message.answer(t("errors.limit_reached", lang, limit=result.limit))
    else:
        await message.answer(t("errors.invalid_domain", lang))


async def _untrack(
    message: Message,
    *,
    user: User,
    lang: str,
    domain: str,
    arq_redis: ArqRedis,
    limits: Limits,
) -> None:
    """Снять домен со слежения (кнопка «Снять»)."""
    async with get_session() as session:
        domain_repo = DomainRepository(session)
        cache_repo = WhoisCacheRepository(session)
        facade = WhoisFacade(cache_repo, arq_redis, limits)
        service = DomainService(
            domain_repo=domain_repo, cache_repo=cache_repo, facade=facade, limits=limits
        )
        result = await service.remove_for_user(user_id=user.id, domain_input=domain)
    display = from_punycode(result.normalized_domain or domain)
    if result.status == "removed":
        await message.answer(t("commands.rmv.success", lang, domain=display))
    elif result.status == "not_tracked":
        await message.answer(t("commands.rmv.not_found", lang))
    else:
        await message.answer(t("errors.invalid_domain", lang))


async def _force_refresh(
    *,
    query: CallbackQuery,
    user: User,
    lang: str,
    domain: str,
    arq_redis: ArqRedis,
    redis: Redis[str],
    limits: Limits,
) -> None:
    """Кнопка «Обновить» — live-lookup с rate-limit cooldown."""
    if not isinstance(query.message, Message):
        return
    key = _force_refresh_key(user.id, domain)
    ttl_seconds = limits.force_refresh_cooldown_hours * 3600
    acquired = await redis.set(key, "1", ex=ttl_seconds, nx=True)
    if not acquired:
        await query.answer(
            t("errors.force_refresh_cooldown", lang, hours=limits.force_refresh_cooldown_hours),
            show_alert=True,
        )
        return
    await _send_whois_card(
        message=query.message,
        domain_input=domain,
        user=user,
        lang=lang,
        arq_redis=arq_redis,
        limits=limits,
        force_refresh=True,
    )


async def _send_raw(message: Message, *, lang: str, domain: str) -> None:
    """Кнопка «Полный ответ» — отдаём комбинированный «человекочитаемая шапка +
    raw source data» как .txt-файл (Этап 8).
    """
    async with get_session() as session:
        cache_repo = WhoisCacheRepository(session)
        cached = await cache_repo.get(domain)
    if cached is None or not cached.raw_data:
        await message.answer(t("errors.whois_unavailable", lang))
        return
    file_lang: Literal["ru", "en"] = "en" if lang == "en" else "ru"
    text = build_full_text_from_cache_row(cached, lang=file_lang)
    buffer = io.BytesIO(text.encode("utf-8"))
    await message.answer_document(
        BufferedInputFile(buffer.getvalue(), filename=f"{domain}.whois.txt")
    )


async def _add_to_wishlist_shortcut(
    message: Message,
    *,
    user: User,
    lang: str,
    domain: str,
    arq_redis: ArqRedis,
    limits: Limits,
) -> None:
    """Shortcut из карточки /whois: добавить домен в wishlist одним нажатием.

    Делегирует в ``wishlist._add_to_wishlist`` чтобы не дублировать
    лимиты/проверки. Локальный импорт — wishlist.router зависит от
    keyboards, которая зависит от t() — путь через __init__ всё равно
    прогревается, разрыв цикла достаточен на уровне функций.
    """
    from src.bot.handlers.wishlist import _add_to_wishlist

    await _add_to_wishlist(
        message=message,
        user=user,
        lang=lang,
        domain_input=domain,
        arq_redis=arq_redis,
        limits=limits,
    )


async def _remove_from_wishlist(
    message: Message,
    *,
    user: User,
    lang: str,
    domain: str,
) -> None:
    """Удаляет домен из wishlist (кнопка «убрать из wishlist»)."""
    async with get_session() as session:
        wishlist_repo = WishlistRepository(session)
        removed = await wishlist_repo.remove(user.id, domain)

    if removed:
        display = from_punycode(domain)
        await message.answer(t("commands.wishlist.removed", lang, domain=display))
    else:
        # Не было в wishlist — странно, но не критично
        await message.answer(t("commands.wishlist.not_found", lang))


async def _register_pending_followup(
    *,
    redis: Redis[str],
    domain: str,
    user_id: int,
) -> None:
    """Кладёт user_id в set ``pending_add_followup:<domain>`` с TTL 10 минут.

    ARQ-задача ``check_domain`` после успешной проверки прочитает set и
    отправит карточку WHOIS этим пользователям.
    """
    key = f"pending_add_followup:{domain}"
    await redis.sadd(key, str(user_id))
    await redis.expire(key, 600)


# ---------------------------------------------------------------------------
# TASK-0042: "🛰 Поддомены" button — reuse existing enumeration (ADR 037)
# ---------------------------------------------------------------------------


async def _on_demand_card_view(
    *,
    query: CallbackQuery,
    lang: str,
    registrable: str,
    cached: Any | None,
    is_fresh: bool,
    render: Callable[[Any], str],
    reply_markup_factory: Callable[[Any], InlineKeyboardMarkup | None] | None = None,
    arq_redis: ArqRedis,
    job_name: str,
    searching_text: str,
) -> None:
    """Общий helper для on-demand кнопок карточки /whois (TASK-0048, ADR 040).

    Устраняет дублирование кэш→freshness→render | enqueue+"ищу…" между
    deep-email и subdomains. Сигнатура с инъекцией render/factory для гибкости
    и минимума зависимостей в helper'е.
    """
    if not isinstance(query.message, Message):
        await query.answer()
        return

    if cached is not None and is_fresh:
        text = render(cached)
        markup = reply_markup_factory(cached) if reply_markup_factory else None
        await query.message.reply(text, reply_markup=markup)
        await query.answer()
        return

    # Нет свежего кэша — enqueue той же ARQ-задачи, что и прямая команда
    # Передаём контекст доставки результата (TASK-0075): чтобы задача дослала
    # результат в чат кликнувшего (без повторного тапа).
    deliver_chat_id = None
    deliver_lang = lang
    if isinstance(query.message, Message):
        deliver_chat_id = query.message.chat.id
    await arq_redis.enqueue_job(
        job_name,
        registrable,
        deliver_chat_id=deliver_chat_id,
        deliver_lang=deliver_lang,
    )
    await query.message.reply(searching_text)
    await query.answer()


async def _show_subdomains_from_whois_card(
    *,
    query: CallbackQuery,
    user: User,
    lang: str,
    domain: str,
    arq_redis: ArqRedis,
) -> None:
    """Кнопка «🛰 Поддомены» на карточке — переиспользует /subdomains поток (TASK-0048: via helper)."""
    try:
        normalized = normalize_domain(domain)
        registrable = registrable_domain(normalized) or normalized
    except Exception:
        await query.answer(t("commands.subdomains.invalid_domain", lang), show_alert=True)
        return

    async with get_session() as session:
        cache_repo = SubdomainEnumCacheRepository(session)
        cached: SubdomainEnumCache | None = await cache_repo.get(registrable)

    is_fresh = bool(cached is not None and cached.subdomains and _is_subdomain_cache_fresh(cached))

    def _render_sub(c: SubdomainEnumCache) -> str:
        subs = c.subdomains or []
        display = from_punycode(registrable)
        count = len(subs)
        fetched_at = format_date(c.fetched_at, lang=lang) if c.fetched_at else "—"
        subdomain_list = "\n".join(
            t("commands.subdomains.list_item", lang, subdomain=from_punycode(sub))
            for sub in subs[:50]
        )
        return (
            t(
                "commands.subdomains.header",
                lang,
                domain=display,
                count=count,
                fetched_at=fetched_at,
            )
            + f"\n\n{subdomain_list}"
        )

    def _mk_markup(c: SubdomainEnumCache) -> InlineKeyboardMarkup:
        return subdomains_keyboard(registrable, c.subdomains or [], lang=lang)

    display = from_punycode(registrable)
    searching = t("commands.subdomains.searching", lang, domain=display)

    await _on_demand_card_view(
        query=query,
        lang=lang,
        registrable=registrable,
        cached=cached,
        is_fresh=is_fresh,
        render=_render_sub,
        reply_markup_factory=_mk_markup,
        arq_redis=arq_redis,
        job_name="check_subdomains",
        searching_text=searching,
    )

    # Лог только при enqueue (helper не знает про user); при fresh — тише (как было)
    # Для простоты логируем всегда trigger (существующее поведение сохраняется в вызывающих)
    logger.info("Subdomains triggered from whois card for %s (user %s)", registrable, user.id)


def _is_subdomain_cache_fresh(cached: SubdomainEnumCache | None) -> bool:
    """Проверка свежести кэша поддоменов (7 дней).

    Прямой доступ к полям (без getattr) — по правилу anti-drift из CLAUDE.md.
    """
    if cached is None or cached.fetched_at is None:
        return False
    age = datetime.now(tz=UTC) - cached.fetched_at
    return age.total_seconds() < (7 * 24 * 60 * 60)


# ---------------------------------------------------------------------------
# TASK-0041: "✉️ Глубокий e-mail" button (ADR 040)
# ---------------------------------------------------------------------------


async def _show_deep_email_from_whois_card(
    *,
    query: CallbackQuery,
    user: User,
    lang: str,
    domain: str,
    arq_redis: ArqRedis,
) -> None:
    """Кнопка «✉️ Глубокий e-mail» на карточке — on-demand deep (TASK-0041 + 0048 via helper).

    Закрывает долги 0039 + устраняет дублирование с subdomains handler.
    """
    try:
        normalized = normalize_domain(domain)
        registrable = registrable_domain(normalized) or normalized
    except Exception:
        await query.answer(t("commands.subdomains.invalid_domain", lang), show_alert=True)
        return

    # Freshness gate (долг из 0039) — anti-drift: прямой доступ, без getattr
    async with get_session() as session:
        deep_repo = EmailDeepCacheRepository(session)
        cached: EmailDeepCache | None = await deep_repo.get(registrable)

    now = datetime.now(tz=UTC)
    is_fresh = cached is not None and cached.next_check_at > now

    def _render_deep(c: EmailDeepCache) -> str:
        return format_email_deep(c, lang=lang)

    # deep email fresh reply не имеет reply_markup (в отличие от subdomains)
    display = from_punycode(registrable)
    searching = t("deep_email.searching", lang, domain=display)

    await _on_demand_card_view(
        query=query,
        lang=lang,
        registrable=registrable,
        cached=cached,
        is_fresh=is_fresh,
        render=_render_deep,
        reply_markup_factory=None,
        arq_redis=arq_redis,
        job_name="check_email_deep",
        searching_text=searching,
    )

    logger.info("Deep email triggered from whois card for %s (user %s)", registrable, user.id)


__all__ = ["router"]
