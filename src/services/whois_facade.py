"""Фасад для интерактивного получения WHOIS-данных.

Логика разделения «синхронного» и «асинхронного» пути:

- **Интерактивно** (``/whois``, ``/check``, ``/add`` на свежий домен) пользователь
  ждёт ответ в реальном времени → пробуем кэш, потом короткий live-lookup
  с таймаутом ``whois_sync_lookup_timeout_seconds``.
- **Фоном** (планировщик, периодические проверки) — отдельная задача
  ARQ ``check_domain``, без user-facing таймаута.

Это сервис, не задача: он ничего не пишет в БД (только читает кэш) и
не отправляет уведомлений. Запись в кэш — забота ARQ-задачи или сервиса
доменов; ``WhoisFacade.enqueue_check`` ставит её в очередь.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from arq import ArqRedis

from src.config.limits import Limits
from src.db.repositories import WhoisCacheRepository
from src.services.results import FacadeResult
from src.whois.client import lookup_domain
from src.whois.types import WhoisData, WhoisError

logger = logging.getLogger(__name__)


class WhoisFacade:
    """Кэш + live-lookup + постановка фоновой проверки в очередь."""

    def __init__(
        self, cache_repo: WhoisCacheRepository, arq_redis: ArqRedis, limits: Limits
    ) -> None:
        self._cache_repo = cache_repo
        self._arq = arq_redis
        self._limits = limits

    async def get_or_fetch(
        self,
        domain: str,
        *,
        force_refresh: bool = False,
        sync_timeout: float | None = None,
    ) -> FacadeResult:
        """Возвращает WHOIS-данные для интерактивной команды.

        ``force_refresh=True`` — пропускаем кэш, всегда дёргаем live. Если
        live упал по таймауту/сети, а в кэше что-то есть — отдаём stale
        с пометкой (``is_stale=True``, ``stale_age_days``).

        ``sync_timeout=None`` — берём из ``limits.whois_sync_lookup_timeout_seconds``.
        """
        del sync_timeout  # таймаут берётся внутри lookup_domain через limits

        cached = await self._cache_repo.get(domain)

        if not force_refresh and cached is not None and _is_fresh(cached.fetched_at, self._limits):
            return FacadeResult(data=_cache_to_data(cached, domain), is_stale=False)

        # Live-lookup.
        live = await lookup_domain(domain, limits=self._limits)

        if isinstance(live, WhoisData):
            return FacadeResult(data=live, is_stale=False)

        # WhoisError → пробуем отдать stale-кэш.
        if cached is not None and cached.fetched_at is not None and cached.expires_at is not None:
            age_days = _age_days(cached.fetched_at)
            return FacadeResult(
                data=_cache_to_data(cached, domain),
                is_stale=True,
                stale_age_days=age_days,
            )
        return FacadeResult(error=live)

    async def enqueue_check(self, domain: str) -> None:
        """Ставит фоновую задачу ``check_domain`` в очередь ARQ.

        Используется после ``/add`` для домена, которого ещё нет в кэше:
        отвечаем пользователю «проверяю...», воркер позже пришлёт followup.
        """
        await self._arq.enqueue_job("check_domain", domain)


# ---------------------------------------------------------------------------
# Внутреннее
# ---------------------------------------------------------------------------


def _is_fresh(fetched_at: datetime | None, limits: Limits) -> bool:
    """True, если данные свежее ``whois_cache_fresh_hours``."""
    if fetched_at is None:
        return False
    fresh_window = timedelta(hours=limits.whois_cache_fresh_hours)
    return datetime.now(tz=UTC) - fetched_at <= fresh_window


def _age_days(fetched_at: datetime) -> int:
    return max(0, int((datetime.now(tz=UTC) - fetched_at).total_seconds() // 86400))


def _cache_to_data(cache: object, domain: str) -> WhoisData:
    """Превращает ``WhoisCache`` ORM-запись в ``WhoisData`` для UI.

    Аргумент типизирован как ``object`` намеренно — здесь нам нужен только
    набор атрибутов, и мы избегаем циклического импорта типа ``WhoisCache``
    в подсказках. Парсер сюда не ходит.
    """
    return WhoisData(
        domain=domain,
        is_registered=getattr(cache, "expires_at", None) is not None
        or bool(getattr(cache, "registrar", None)),
        expires_at=getattr(cache, "expires_at", None),
        created_at=getattr(cache, "created_at_registrar", None),
        updated_at=getattr(cache, "updated_at_registrar", None),
        registrar=getattr(cache, "registrar", None),
        status=list(getattr(cache, "status", []) or []),
        name_servers=list(getattr(cache, "name_servers", []) or []),
        raw_data=getattr(cache, "raw_data", None) or {},
        source="rdap",
    )


__all__ = ["FacadeResult", "WhoisError", "WhoisFacade"]
