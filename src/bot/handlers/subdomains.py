"""Хэндлер ``/subdomains`` — поиск поддоменов через crt.sh (ADR 037).

Команда:
- Валидирует домен (ADR 035, guard на публичный суффикс)
- Запрашивает по registrable-домену
- Проверяет кэш — если свежий, рендерит сразу
- Иначе отвечает «ищу…» и ставит ARQ-задачу ``check_subdomains``
- По готовности — результат с inline-кнопками для opt-in через ``/add``
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, Message
from arq import ArqRedis

from src.bot.keyboards import SubdomainAction, subdomains_keyboard
from src.config.limits import Limits
from src.db.models import SubdomainEnumCache, User
from src.db.repositories import DomainRepository, SubdomainEnumCacheRepository, WhoisCacheRepository
from src.db.session import get_session
from src.locales import t
from src.services.domains import DomainService
from src.services.whois_facade import WhoisFacade
from src.utils.domains import is_public_suffix_only, registrable_domain
from src.utils.formatting import format_date
from src.utils.idn import from_punycode, normalize_domain

logger = logging.getLogger(__name__)

router = Router(name="subdomains")

# TTL кэша для считывания "свежим" (соответствует scheduler — 7 дней при успехе)
_CACHE_FRESHNESS_SECONDS = 7 * 24 * 60 * 60  # 7 дней
_MAX_DISPLAY_SUBDOMAINS = 50  # Лимит отображения


@router.message(Command("subdomains"))
async def cmd_subdomains(
    message: Message,
    command: CommandObject,
    user: User,
    lang: str,
    arq_redis: ArqRedis,
) -> None:
    """``/subdomains <domain>`` — показать поддомены registrable-домена."""
    if not command.args:
        await message.answer(t("commands.cmd_arg.prompt", lang, cmd="subdomains"))
        return

    domain_input = command.args.strip().split()[0]

    # 1. Валидация домена (ADR 035)
    try:
        normalized = normalize_domain(domain_input)
    except (ValueError, UnicodeError):
        await message.answer(t("commands.subdomains.invalid_domain", lang))
        return

    # 2. Guard на публичный суффикс
    try:
        is_suffix_only = is_public_suffix_only(normalized)
    except (ValueError, UnicodeError):
        is_suffix_only = False
    if is_suffix_only:
        await message.answer(t("commands.subdomains.public_suffix", lang))
        return

    # 3. Получаем registrable-домен (для запроса к crt.sh)
    registrable = registrable_domain(normalized)
    if not registrable:
        await message.answer(t("commands.subdomains.invalid_domain", lang))
        return

    # 4. Проверяем кэш
    async with get_session() as session:
        cache_repo = SubdomainEnumCacheRepository(session)
        cached = await cache_repo.get(registrable)

    # 5. Если есть свежий кэш — рендерим сразу
    if cached and cached.subdomains and _is_cache_fresh(cached):
        display = from_punycode(registrable)
        count = len(cached.subdomains)
        fetched_at = format_date(cached.fetched_at, lang=lang) if cached.fetched_at else "—"

        # Если слишком много — показываем ошибку
        if count > _MAX_DISPLAY_SUBDOMAINS:
            await message.answer(
                t(
                    "commands.subdomains.too_many",
                    lang,
                    count=count,
                    max=_MAX_DISPLAY_SUBDOMAINS,
                )
            )
            return

        # Формируем список поддоменов для сообщения
        subdomain_list = "\n".join(
            t("commands.subdomains.list_item", lang, subdomain=from_punycode(sub))
            for sub in cached.subdomains[:_MAX_DISPLAY_SUBDOMAINS]
        )

        # Рендерим список с кнопками
        await message.answer(
            t(
                "commands.subdomains.header",
                lang,
                domain=display,
                count=count,
                fetched_at=fetched_at,
            )
            + f"\n\n{subdomain_list}",
            reply_markup=subdomains_keyboard(registrable, cached.subdomains, lang=lang),
        )
        return

    # 6. Если кэш устарел или пуст — ставим задачу
    await arq_redis.enqueue_job("check_subdomains", registrable)
    display = from_punycode(registrable)
    await message.answer(t("commands.subdomains.searching", lang, domain=display))

    logger.info("Enqueued check_subdomains for %s (user %s)", registrable, user.id)


def _is_cache_fresh(cached: SubdomainEnumCache) -> bool:
    """Проверяет, что кэш ещё свежий."""
    if cached.fetched_at is None:
        return False
    age = datetime.now(tz=UTC) - cached.fetched_at
    return age.total_seconds() < _CACHE_FRESHNESS_SECONDS


@router.callback_query(SubdomainAction.filter(F.action == "refresh"))
async def cb_subdomains_refresh(
    callback: CallbackQuery,
    callback_data: SubdomainAction,
    user: User,
    lang: str,
    arq_redis: ArqRedis,
) -> None:
    """Кнопка «🔄 Обновить» — заново запустить проверку."""
    registrable = callback_data.registrable
    await arq_redis.enqueue_job("check_subdomains", registrable)
    display = from_punycode(registrable)
    if callback.message:
        await callback.message.edit_text(  # type: ignore[union-attr]
            t("commands.subdomains.searching", lang, domain=display)
        )
    await callback.answer()
    logger.info("Refreshed subdomains for %s (user %s)", registrable, user.id)


@router.callback_query(SubdomainAction.filter(F.action == "track"))
async def cb_subdomains_track(
    callback: CallbackQuery,
    callback_data: SubdomainAction,
    user: User,
    lang: str,
    arq_redis: ArqRedis,
    limits: Limits,
) -> None:
    """Кнопка «📌 Отслеживать» — добавить поддомен через /add путь."""
    registrable = callback_data.registrable
    idx = callback_data.idx

    # Получаем поддомен из кэша по idx
    async with get_session() as session:
        cache_repo = SubdomainEnumCacheRepository(session)
        cached = await cache_repo.get(registrable)
    if not cached or not cached.subdomains or idx < 0 or idx >= len(cached.subdomains):
        await callback.answer(t("commands.subdomains.no_cache", lang), show_alert=True)
        return
    subdomain = cached.subdomains[idx]

    # Используем DomainService.add_for_user (как /add)
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
            domain_input=subdomain,
        )

    display = from_punycode(result.normalized_domain or subdomain)
    if result.status in ("added", "added_pending", "promoted"):
        await callback.answer(
            t("commands.add.success_no_data", lang, domain=display),
            show_alert=True,
        )
    elif result.status == "already_tracked":
        await callback.answer(
            t("commands.add.already_tracked", lang, domain=display),
            show_alert=True,
        )
    elif result.status == "limit_reached":
        await callback.answer(
            t("errors.limit_reached", lang, limit=result.limit),
            show_alert=True,
        )
    else:
        await callback.answer(t("errors.invalid_domain", lang), show_alert=True)


@router.callback_query(SubdomainAction.filter(F.action == "track_all"))
async def cb_subdomains_track_all(
    callback: CallbackQuery,
    callback_data: SubdomainAction,
    user: User,
    lang: str,
    arq_redis: ArqRedis,
    limits: Limits,
) -> None:
    """Кнопка «📌 Отслеживать все» — добавить все поддомены."""
    registrable = callback_data.registrable

    # Получаем список поддоменов из кэша
    async with get_session() as session:
        subdomain_cache_repo = SubdomainEnumCacheRepository(session)
        cached = await subdomain_cache_repo.get(registrable)

    if not cached or not cached.subdomains:
        await callback.answer(t("commands.subdomains.no_cache", lang), show_alert=True)
        return

    # Добавляем каждый поддомен
    added = 0
    skipped = 0
    error_count = 0

    async with get_session() as session:
        domain_repo = DomainRepository(session)
        whois_cache_repo = WhoisCacheRepository(session)
        facade = WhoisFacade(whois_cache_repo, arq_redis, limits)
        service = DomainService(
            domain_repo=domain_repo,
            cache_repo=whois_cache_repo,
            facade=facade,
            limits=limits,
        )

        for subdomain in cached.subdomains[:_MAX_DISPLAY_SUBDOMAINS]:
            result = await service.add_for_user(
                user_id=user.id,
                notify_days=list(user.notify_days),
                domain_input=subdomain,
            )
            if result.status in ("added", "added_pending", "promoted"):
                added += 1
            elif result.status == "already_tracked":
                skipped += 1
            else:
                error_count += 1

    errors_msg = (
        t("commands.subdomains.track_all_result_errors", lang, errors=error_count)
        if error_count > 0
        else ""
    )
    await callback.answer(
        t(
            "commands.subdomains.track_all_result",
            lang,
            added=added,
            skipped=skipped,
            errors_msg=errors_msg,
        ),
        show_alert=True,
    )
    logger.info(
        "Track all for %s: added=%d skipped=%d errors=%d (user %s)",
        registrable,
        added,
        skipped,
        error_count,
        user.id,
    )


__all__ = ["router"]
