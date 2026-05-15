"""``DomainService`` — бизнес-логика ``/add``, ``/rmv``, ``/list``.

Хэндлеры зовут только эти методы. Внутри:

- нормализация и валидация домена (через ``utils.idn`` и ``bot.validators``)
- проверка лимитов
- работа с репозиториями ``UserDomain`` / ``WhoisCache``
- постановка фоновой проверки в очередь, если домена нет в общем кэше

Никаких аиограм-объектов и сетевых запросов — только БД и Redis (через
``WhoisFacade``).
"""

from __future__ import annotations

import logging

import idna

from src.bot.validators import is_valid_domain
from src.config.limits import Limits
from src.db.repositories import DomainRepository, WhoisCacheRepository
from src.services.results import (
    AddDomainResult,
    FacadeResult,
    ListFilter,
    ListPage,
    RemoveDomainResult,
)
from src.services.whois_facade import WhoisFacade
from src.utils.idn import normalize_domain
from src.whois.types import WhoisData

logger = logging.getLogger(__name__)


class DomainService:
    """Бизнес-логика управления портфелем доменов пользователя."""

    def __init__(
        self,
        *,
        domain_repo: DomainRepository,
        cache_repo: WhoisCacheRepository,
        facade: WhoisFacade,
        limits: Limits,
    ) -> None:
        self._domains = domain_repo
        self._cache = cache_repo
        self._facade = facade
        self._limits = limits

    # ------------------------------------------------------------------
    # /add
    # ------------------------------------------------------------------
    async def add_for_user(
        self,
        *,
        user_id: int,
        notify_days: list[int],
        domain_input: str,
    ) -> AddDomainResult:
        """Добавляет домен в портфель пользователя.

        ``notify_days`` — текущие дни напоминаний пользователя (для UI).
        Сам по себе сервис их не использует, кроме как для возврата label'а
        в результате.
        """
        try:
            normalized = normalize_domain(domain_input)
        except (idna.IDNAError, ValueError, UnicodeError):
            return AddDomainResult(status="invalid_domain")
        if not is_valid_domain(normalized):
            return AddDomainResult(status="invalid_domain", normalized_domain=normalized)

        # Проверка лимита и дубля.
        current_count = await self._domains.count_by_user(user_id)
        if current_count >= self._limits.max_domains_per_user:
            return AddDomainResult(
                status="limit_reached",
                normalized_domain=normalized,
                limit=self._limits.max_domains_per_user,
            )
        if await self._domains.exists(user_id, normalized):
            cached = await self._cache.get(normalized)
            return AddDomainResult(
                status="already_tracked",
                normalized_domain=normalized,
                whois_data=_cache_to_data(cached, normalized) if cached else None,
                notify_days_label=_format_days(notify_days),
            )

        # Вставка в user_domains.
        await self._domains.add(user_id, normalized)

        # Что насчёт общего кэша?
        cached = await self._cache.get(normalized)
        if cached is not None and cached.expires_at is not None:
            return AddDomainResult(
                status="added",
                normalized_domain=normalized,
                whois_data=_cache_to_data(cached, normalized),
                notify_days_label=_format_days(notify_days),
            )

        # Кэша нет — заводим строку и ставим задачу.
        await self._cache.upsert(normalized)  # пустая строка с PK
        await self._facade.enqueue_check(normalized)
        return AddDomainResult(
            status="added_pending",
            normalized_domain=normalized,
            notify_days_label=_format_days(notify_days),
        )

    # ------------------------------------------------------------------
    # /rmv
    # ------------------------------------------------------------------
    async def remove_for_user(
        self,
        *,
        user_id: int,
        domain_input: str,
    ) -> RemoveDomainResult:
        """Удаляет домен из портфеля пользователя.

        ``whois_cache``-запись НЕ трогаем (ADR 020): её подхватит сборщик
        мусора, если ни у кого больше нет этого домена.
        """
        try:
            normalized = normalize_domain(domain_input)
        except (idna.IDNAError, ValueError, UnicodeError):
            return RemoveDomainResult(status="invalid_domain")
        if not is_valid_domain(normalized):
            return RemoveDomainResult(status="invalid_domain", normalized_domain=normalized)

        removed = await self._domains.remove(user_id, normalized)
        return RemoveDomainResult(
            status="removed" if removed else "not_tracked",
            normalized_domain=normalized,
        )

    # ------------------------------------------------------------------
    # /list
    # ------------------------------------------------------------------
    async def list_for_user(
        self,
        *,
        user_id: int,
        page: int = 0,
        page_size: int = 50,
        filter_type: ListFilter = "all",
    ) -> ListPage:
        """Страница списка доменов с фильтром и пагинацией."""
        page = max(0, page)
        page_size = max(1, page_size)
        rows, total = await self._domains.list_with_whois_filtered(
            user_id,
            filter_type=filter_type,
            limit=page_size,
            offset=page * page_size,
        )
        return ListPage(
            rows=list(rows),
            total=total,
            page=page,
            page_size=page_size,
            filter_type=filter_type,
        )

    # ------------------------------------------------------------------
    # /whois — переиспользует фасад напрямую
    # ------------------------------------------------------------------
    async def lookup_for_user(
        self,
        domain_input: str,
        *,
        force_refresh: bool = False,
    ) -> FacadeResult:
        """Делегирует в ``WhoisFacade.get_or_fetch`` с предварительной нормализацией."""
        try:
            normalized = normalize_domain(domain_input)
        except (idna.IDNAError, ValueError, UnicodeError):
            from src.whois.types import WhoisError

            return FacadeResult(
                error=WhoisError(
                    domain=domain_input, error_type="parse_error", message="invalid domain"
                )
            )
        return await self._facade.get_or_fetch(normalized, force_refresh=force_refresh)


# ---------------------------------------------------------------------------
# Внутреннее
# ---------------------------------------------------------------------------


def _format_days(days: list[int]) -> str:
    """``[30, 7, 1]`` → ``"30, 7, 1"`` (порядок сохраняем)."""
    return ", ".join(str(d) for d in days) if days else "—"


def _cache_to_data(cache: object | None, domain: str) -> WhoisData | None:
    """Делегат в фасадный конвертер — отдельно, чтобы не плодить импорты в хэндлерах."""
    if cache is None:
        return None
    from src.services.whois_facade import _cache_to_data as _impl

    return _impl(cache, domain)
