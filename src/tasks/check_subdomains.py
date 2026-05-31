"""ARQ-задача ``check_subdomains``: проверка поддоменов через crt.sh.

Принципы (как у check_email_intel):

- Redis-флаг ``subdomain_check_in_progress:<registrable>`` гарантирует один воркер.
- Успех → UPSERT в ``subdomain_enum_cache`` + расчёт next_check_at.
- Ошибка → ``SubdomainEnumCacheRepository.update_fail`` + пересчёт next_check_at.
- Для команды ``/subdomains`` — результат возвращается (но в v0.11 команда сама
  читает из кэша; ARQ-задача только обновляет).
- **TASK-0028 (ADR 038)**: diff с предыдущим состоянием, enqueue notify при изменениях.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from arq import ArqRedis
from redis.asyncio import Redis as AsyncRedis

from src.db.repositories import SubdomainEnumCacheRepository
from src.db.session import get_session
from src.observability import bind_log_context, clear_log_context
from src.subdomains.client import fetch_subdomains
from src.subdomains.diff import compute_subdomain_diff
from src.subdomains.scheduler import calculate_next_subdomain_check
from src.subdomains.types import SubdomainEnumError

logger = logging.getLogger(__name__)

_IN_PROGRESS_TTL_SECONDS = 60


def _in_progress_key(registrable_domain: str) -> str:
    return f"subdomain_check_in_progress:{registrable_domain}"


async def check_subdomains(ctx: dict[str, Any], registrable_domain: str) -> dict[str, Any]:
    """ARQ-задача: проверить поддомены registrable-домена.

    Args:
        ctx: ARQ context
        registrable_domain: Registrable-домен (eTLD+1, ADR 035)

    Returns:
        dict с результатом для хэндлера (или команды)
    """
    redis: AsyncRedis[str] = ctx["sync_redis"]

    bind_log_context(registrable_domain=registrable_domain, subsystem="subdomain_enum")
    try:
        # Redis-guard: не запускаем параллельно для одного домена
        acquired = await redis.set(
            _in_progress_key(registrable_domain),
            "1",
            ex=_IN_PROGRESS_TTL_SECONDS,
            nx=True,
        )
        if not acquired:
            logger.info("Subdomain check already in progress for %s", registrable_domain)
            return {"status": "already_in_progress", "registrable_domain": registrable_domain}

        logger.info("Starting subdomain enumeration for %s", registrable_domain)

        # Запрашиваем у crt.sh
        result = await fetch_subdomains(registrable_domain)

        async with get_session() as session:
            repo = SubdomainEnumCacheRepository(session)

            # Получаем старое состояние кэша
            old_cache = await repo.get(registrable_domain)

            if isinstance(result, SubdomainEnumError):
                # Ошибка — обновляем fail_count и next_check_at
                logger.warning(
                    "Subdomain enumeration failed for %s: %s", registrable_domain, result.message
                )

                # Текущий fail_count (0 если записи нет)
                current_fail_count = old_cache.fail_count if old_cache else 0
                next_check_at = calculate_next_subdomain_check(
                    has_subdomains=False,
                    fail_count=current_fail_count
                    + 1,  # счётчик ПОСЛЕ фейла, согласован с update_fail
                )

                await repo.update_fail(
                    registrable_domain=registrable_domain,
                    error=result.message,
                    next_check_at=next_check_at,
                )

                return {
                    "status": "error",
                    "registrable_domain": registrable_domain,
                    "error_type": result.error_type,
                    "message": result.message,
                }

            # Успех — берём старый subdomains ДО upsert (для diff)
            old_subdomains = old_cache.subdomains if old_cache else None

            # Считаем минимальный интервал от подписчиков (для next_check_at)
            success_interval_days = await repo.get_min_check_interval(registrable_domain)

            now = datetime.now(tz=UTC)
            next_check_at = calculate_next_subdomain_check(
                has_subdomains=bool(result.subdomains),
                success_interval_days=success_interval_days,
            )

            # Upsert в кэш
            await repo.upsert(
                registrable_domain,
                subdomains=result.subdomains,
                fetched_at=now,
                next_check_at=next_check_at,
                is_reachable=True,
                fail_count=0,  # сброс при успехе
                last_error=None,
            )

            # Diff с предыдущим состоянием (ADR 038)
            diff = compute_subdomain_diff(old_subdomains, result.subdomains)
            if diff.has_any_changes:
                # Enqueue уведомление об изменениях (реализация в TASK-0029)
                arq_redis: ArqRedis = ctx["redis"]
                await arq_redis.enqueue_job(
                    "notify_subdomain_changes",
                    registrable_domain=registrable_domain,
                    diff={"new": diff.new, "removed": diff.removed},
                )
                logger.info(
                    "Subdomain changes detected for %s: %d new, %d removed",
                    registrable_domain,
                    len(diff.new),
                    len(diff.removed),
                )

            logger.info(
                "Subdomain enumeration completed for %s: %d subdomains found",
                registrable_domain,
                len(result.subdomains),
            )

            return {
                "status": "success",
                "registrable_domain": registrable_domain,
                "subdomains": result.subdomains,
                "count": len(result.subdomains),
            }

    except Exception as exc:
        logger.exception("Unexpected error in check_subdomains for %s", registrable_domain)
        return {
            "status": "internal_error",
            "registrable_domain": registrable_domain,
            "error": str(exc),
        }
    finally:
        clear_log_context()


__all__ = ["check_subdomains"]
