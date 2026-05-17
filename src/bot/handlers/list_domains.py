"""Хэндлер ``/list`` и его callback'и: пагинация, фильтры, поиск (Этап 9).

Filter и search-query сохраняются в Redis HASH ``list_state:{user_id}``
с TTL 30 минут — иначе пагинация prev/next теряла бы выбранный фильтр.

CSV-кнопка делегирует в ``csv_export`` через `/csv` (тот хэндлер уже
существует и не зависит от состояния списка).
"""

from __future__ import annotations

import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from arq import ArqRedis
from redis.asyncio import Redis

from src.bot.keyboards import ListFilter as ListFilterCb
from src.bot.keyboards import ListPage as ListPageCb
from src.bot.keyboards import ListSearch as ListSearchCb
from src.bot.keyboards import list_filters, list_pagination
from src.bot.states import ListSearchStates
from src.config.limits import Limits
from src.db.models import User
from src.db.repositories import DomainRepository, WhoisCacheRepository
from src.db.session import get_session
from src.locales import t
from src.services.domains import DomainService
from src.services.formatters import format_list_row
from src.services.results import ListFilter as ListFilterType
from src.services.whois_facade import WhoisFacade

logger = logging.getLogger(__name__)

router = Router(name="list_domains")


_PAGE_SIZE = 50
_VALID_FILTERS: frozenset[str] = frozenset(
    {"all", "expiring", "no_data", "muted", "critical", "expired"}
)
_SEARCH_QUERY_MAX_LEN = 64
_LIST_STATE_TTL_SECONDS = 30 * 60


def _state_key(user_id: int) -> str:
    return f"list_state:{user_id}"


async def _read_state(redis: Redis[str], user_id: int) -> tuple[str, str]:
    """Возвращает ``(filter_type, search_query)`` из Redis. Дефолт — all/пусто.

    Поля HASH: ``f`` (filter), ``q`` (query). Короткие имена — экономия места
    и быстрее сериализация redis-resp.
    """
    raw = await redis.hgetall(_state_key(user_id))
    filter_type = raw.get("f", "all") if raw else "all"
    if filter_type not in _VALID_FILTERS:
        filter_type = "all"
    search_query = raw.get("q", "") if raw else ""
    return filter_type, search_query


async def _write_state(
    redis: Redis[str],
    user_id: int,
    *,
    filter_type: str | None = None,
    search_query: str | None = None,
) -> None:
    """Обновляет filter/search в Redis. Передаём только то, что меняем."""
    key = _state_key(user_id)
    pipe = redis.pipeline()
    if filter_type is not None:
        pipe.hset(key, "f", filter_type)
    if search_query is not None:
        pipe.hset(key, "q", search_query)
    pipe.expire(key, _LIST_STATE_TTL_SECONDS)
    await pipe.execute()


async def _reset_state(redis: Redis[str], user_id: int) -> None:
    await redis.delete(_state_key(user_id))


# ---------------------------------------------------------------------------
# /list
# ---------------------------------------------------------------------------


@router.message(Command("list"))
async def cmd_list(
    message: Message,
    user: User,
    lang: str,
    arq_redis: ArqRedis,
    limits: Limits,
    redis: Redis[str],
    state: FSMContext,
) -> None:
    """Команда ``/list`` сбрасывает search/filter — пользователь хочет
    обзорный список «с нуля». FSM-state тоже сбрасываем на случай,
    если был активный поиск.
    """
    await state.clear()
    await _reset_state(redis, user.id)
    await _send_page(
        message=message,
        user=user,
        lang=lang,
        page=0,
        filter_type="all",
        search_query="",
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
    redis: Redis[str],
) -> None:
    """Пагинация ``/list``. На ``filter`` показываем submenu, на ``csv`` —
    подсказку перейти в /csv (Этап 9 — отдельная команда, кнопка-ярлык)."""
    await query.answer()
    if not isinstance(query.message, Message):
        return
    if callback_data.action == "filter":
        await query.message.edit_reply_markup(reply_markup=list_filters(lang))
        return
    if callback_data.action == "csv":
        await query.message.answer(t("commands.list.csv_hint", lang))
        return
    filter_type, search_query = await _read_state(redis, user.id)
    await _send_page(
        message=query.message,
        user=user,
        lang=lang,
        page=callback_data.page,
        filter_type=filter_type,  # type: ignore[arg-type]
        search_query=search_query,
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
    redis: Redis[str],
) -> None:
    """Применить фильтр и показать первую страницу. Поиск сохраняется."""
    await query.answer()
    if not isinstance(query.message, Message):
        return
    filter_type = callback_data.name if callback_data.name in _VALID_FILTERS else "all"
    await _write_state(redis, user.id, filter_type=filter_type)
    _, search_query = await _read_state(redis, user.id)
    await _send_page(
        message=query.message,
        user=user,
        lang=lang,
        page=0,
        filter_type=filter_type,  # type: ignore[arg-type]
        search_query=search_query,
        arq_redis=arq_redis,
        limits=limits,
        edit=True,
    )


# ---------------------------------------------------------------------------
# Поиск
# ---------------------------------------------------------------------------


@router.callback_query(ListSearchCb.filter())
async def on_list_search(
    query: CallbackQuery,
    callback_data: ListSearchCb,
    user: User,
    lang: str,
    arq_redis: ArqRedis,
    limits: Limits,
    redis: Redis[str],
    state: FSMContext,
) -> None:
    """Включить ввод поиска или сбросить активный."""
    await query.answer()
    if not isinstance(query.message, Message):
        return
    if callback_data.action == "clear":
        await _write_state(redis, user.id, search_query="")
        filter_type, _ = await _read_state(redis, user.id)
        await _send_page(
            message=query.message,
            user=user,
            lang=lang,
            page=0,
            filter_type=filter_type,  # type: ignore[arg-type]
            search_query="",
            arq_redis=arq_redis,
            limits=limits,
            edit=True,
        )
        return
    # open: переключаемся в FSM и просим ввести подстроку.
    await state.set_state(ListSearchStates.waiting_for_query)
    await query.message.answer(t("list.search.prompt", lang))


@router.message(ListSearchStates.waiting_for_query)
async def on_search_query_submitted(
    message: Message,
    user: User,
    lang: str,
    arq_redis: ArqRedis,
    limits: Limits,
    redis: Redis[str],
    state: FSMContext,
) -> None:
    """Принимает подстроку поиска, валидирует, перерисовывает страницу."""
    raw = (message.text or "").strip()
    # /cancel перехватывается отдельным хэндлером help_cancel — сюда не
    # доходит. Но защита от пустого / слишком длинного — нелишняя.
    if not raw:
        await message.answer(t("list.search.prompt", lang))
        return
    if len(raw) > _SEARCH_QUERY_MAX_LEN:
        raw = raw[:_SEARCH_QUERY_MAX_LEN]

    await state.clear()
    # Намеренно НЕ логируем сам query — это персональный интерес пользователя.
    logger.info("list search submitted", extra={"user_id": user.id, "query_len": len(raw)})

    await _write_state(redis, user.id, search_query=raw)
    filter_type, _ = await _read_state(redis, user.id)
    await _send_page(
        message=message,
        user=user,
        lang=lang,
        page=0,
        filter_type=filter_type,  # type: ignore[arg-type]
        search_query=raw,
        arq_redis=arq_redis,
        limits=limits,
    )


# ---------------------------------------------------------------------------
# Рендер страницы
# ---------------------------------------------------------------------------


async def _send_page(
    *,
    message: Message,
    user: User,
    lang: str,
    page: int,
    filter_type: ListFilterType,
    search_query: str,
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
            search_query=search_query,
        )

    if page_data.is_empty:
        body = (
            t("list.search.empty", lang, query=search_query)
            if search_query
            else t("commands.list.empty", lang)
        )
        if edit:
            await message.edit_text(body)
        else:
            await message.answer(body)
        return

    header_parts = [
        t(
            "commands.list.header",
            lang,
            total=page_data.total,
            page=page_data.page + 1,
            total_pages=page_data.total_pages,
        )
    ]
    if search_query:
        header_parts.append(t("list.search.current", lang, query=search_query))
    header = "\n".join(header_parts)
    rows = [format_list_row(user_domain, cache, lang=lang) for user_domain, cache in page_data.rows]
    body = header + "\n\n" + "\n".join(rows)
    keyboard = list_pagination(
        page_data.page,
        page_data.total_pages,
        lang=lang,
        has_search=bool(search_query),
    )

    if edit:
        await message.edit_text(body, reply_markup=keyboard)
    else:
        await message.answer(body, reply_markup=keyboard)


__all__ = ["router"]
