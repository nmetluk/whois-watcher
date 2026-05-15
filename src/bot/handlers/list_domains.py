"""Хэндлер ``/list`` и его callback'и: пагинация, фильтры.

CSV-кнопка — заглушка (CSV — это Этап 6).
"""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from arq import ArqRedis

from src.bot.keyboards import ListFilter as ListFilterCb
from src.bot.keyboards import ListPage as ListPageCb
from src.bot.keyboards import list_filters, list_pagination
from src.config.limits import Limits
from src.db.models import User
from src.db.repositories import DomainRepository, WhoisCacheRepository
from src.db.session import get_session
from src.locales import t
from src.services.domains import DomainService
from src.services.formatters import format_list_row
from src.services.results import ListFilter as ListFilterType
from src.services.whois_facade import WhoisFacade

router = Router(name="list_domains")


_PAGE_SIZE = 50
_VALID_FILTERS: frozenset[str] = frozenset({"all", "expiring", "no_data", "muted"})


@router.message(Command("list"))
async def cmd_list(
    message: Message,
    user: User,
    lang: str,
    arq_redis: ArqRedis,
    limits: Limits,
) -> None:
    await _send_page(
        message=message,
        user=user,
        lang=lang,
        page=0,
        filter_type="all",
        arq_redis=arq_redis,
        limits=limits,
    )


@router.callback_query(ListPageCb.filter())
async def on_list_page(
    query: CallbackQuery,
    callback_data: ListPageCb,
    user: User,
    lang: str,
    arq_redis: ArqRedis,
    limits: Limits,
) -> None:
    """Пагинация ``/list``. На ``filter`` показываем submenu, на ``csv`` —
    заглушка до Этапа 6."""
    await query.answer()
    if not isinstance(query.message, Message):
        return
    if callback_data.action == "filter":
        await query.message.edit_reply_markup(reply_markup=list_filters(lang))
        return
    if callback_data.action == "csv":
        await query.message.answer(t("stubs.coming_soon", lang, command="/csv"))
        return
    await _send_page(
        message=query.message,
        user=user,
        lang=lang,
        page=callback_data.page,
        filter_type="all",
        arq_redis=arq_redis,
        limits=limits,
        edit=True,
    )


@router.callback_query(ListFilterCb.filter())
async def on_list_filter(
    query: CallbackQuery,
    callback_data: ListFilterCb,
    user: User,
    lang: str,
    arq_redis: ArqRedis,
    limits: Limits,
) -> None:
    """Применить фильтр и показать первую страницу."""
    await query.answer()
    if not isinstance(query.message, Message):
        return
    filter_type = callback_data.name if callback_data.name in _VALID_FILTERS else "all"
    await _send_page(
        message=query.message,
        user=user,
        lang=lang,
        page=0,
        filter_type=filter_type,  # type: ignore[arg-type]
        arq_redis=arq_redis,
        limits=limits,
        edit=True,
    )


async def _send_page(
    *,
    message: Message,
    user: User,
    lang: str,
    page: int,
    filter_type: ListFilterType,
    arq_redis: ArqRedis,
    limits: Limits,
    edit: bool = False,
) -> None:
    """Считает страницу через сервис и шлёт (или редактирует) сообщение."""
    async with get_session() as session:
        domain_repo = DomainRepository(session)
        cache_repo = WhoisCacheRepository(session)
        facade = WhoisFacade(cache_repo, arq_redis, limits)
        service = DomainService(
            domain_repo=domain_repo, cache_repo=cache_repo, facade=facade, limits=limits
        )
        page_data = await service.list_for_user(
            user_id=user.id,
            page=page,
            page_size=_PAGE_SIZE,
            filter_type=filter_type,
        )

    if page_data.is_empty:
        body = t("commands.list.empty", lang)
        if edit:
            await message.edit_text(body)
        else:
            await message.answer(body)
        return

    header = t(
        "commands.list.header",
        lang,
        total=page_data.total,
        page=page_data.page + 1,
        total_pages=page_data.total_pages,
    )
    rows = [format_list_row(user_domain, cache, lang=lang) for user_domain, cache in page_data.rows]
    body = header + "\n\n" + "\n".join(rows)
    keyboard = list_pagination(page_data.page, page_data.total_pages, lang=lang)

    if edit:
        await message.edit_text(body, reply_markup=keyboard)
    else:
        await message.answer(body, reply_markup=keyboard)


__all__ = ["router"]
