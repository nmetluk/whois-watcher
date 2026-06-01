"""ARQ-задача ``check_email_deep``: on-demand углублённый почтовый разбор (ADR 040).

По нажатию кнопки «Глубокий e-mail» (TASK-0041) ставится эта задача.
- Redis-guard ``email_deep_in_progress:<domain>`` — один воркер на домен.
- Вызывает коллекторы из TASK-0038 (fetch_deep_email).
- Успех → UPSERT в ``email_deep_cache`` с коротким TTL.
- Ошибка → update_fail + сохранённое «недоступно».
- Возвращает статус для хэндлера (чтобы ответить пользователю).

Короткий TTL (10 минут) защищает от повторных тяжёлых DNS/HTTP запросов
при быстром повторном нажатии кнопки.
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from typing import Any

from redis.asyncio import Redis as AsyncRedis

from src.db.repositories import EmailDeepCacheRepository, EmailIntelCacheRepository
from src.db.session import get_session
from src.email_intel.deep_client import fetch_deep_email
from src.email_intel.deep_types import DeepEmailError, DeepEmailResult
from src.observability import bind_log_context, clear_log_context

logger = logging.getLogger(__name__)

_IN_PROGRESS_TTL_SECONDS = 90  # чуть дольше, чем типичный сбор deep (MTA-STS + per-MX DANE)
DEEP_EMAIL_TTL_SECONDS = 10 * 60  # 10 минут — короткий TTL для on-demand (повтор не бьёт сеть)


def _in_progress_key(domain: str) -> str:
    return f"email_deep_in_progress:{domain}"


def _serialize_deep_result(result: DeepEmailResult) -> dict[str, Any]:
    """Сериализует DeepEmailResult в JSONB-совместимый dict."""
    return {
        "spf": asdict(result.spf) if result.spf else None,
        "mta_sts": asdict(result.mta_sts) if result.mta_sts else None,
        "tls_rpt": asdict(result.tls_rpt) if result.tls_rpt else None,
        "dane": asdict(result.dane) if result.dane else None,
        "bimi": asdict(result.bimi) if result.bimi else None,
        "is_reachable": result.is_reachable,
    }


async def check_email_deep(ctx: dict[str, Any], domain: str) -> dict[str, Any]:
    """ARQ-задача: выполнить deep email сбор для домена (on-demand)."""
    redis: AsyncRedis[str] = ctx["sync_redis"]

    bind_log_context(domain=domain, subsystem="email_deep")
    try:
        # Redis-guard: не запускаем параллельно для одного домена
        acquired = await redis.set(
            _in_progress_key(domain),
            "1",
            ex=_IN_PROGRESS_TTL_SECONDS,
            nx=True,
        )
        if not acquired:
            logger.info("Deep email check already in progress for %s", domain)
            return {"status": "already_in_progress", "domain": domain}

        logger.info("Starting deep email collection for %s", domain)

        # Читаем MX из базового кэша (TASK-0041) — нужно для DANE
        async with get_session() as intel_session:
            intel_repo = EmailIntelCacheRepository(intel_session)
            intel = await intel_repo.get(domain)
            mx_hosts: list[str] | None = None
            if intel and intel.mx_records:
                mx_hosts = [h for m in intel.mx_records if (h := m.get("host")) is not None]

        # Передаём mx_hosts → DANE будет работать (закрыт долг из 0039)
        result = await fetch_deep_email(domain, mx_hosts=mx_hosts)

        async with get_session() as session:
            repo = EmailDeepCacheRepository(session)
            now = datetime.now(tz=UTC)
            next_check_at = now + timedelta(seconds=DEEP_EMAIL_TTL_SECONDS)

            if isinstance(result, DeepEmailError):
                logger.warning("Deep email collection failed for %s: %s", domain, result.message)
                await repo.update_fail(
                    domain=domain,
                    error=result.message,
                    next_check_at=next_check_at,
                )
                return {
                    "status": "error",
                    "domain": domain,
                    "error_type": result.error_type,
                    "message": result.message,
                }

            # Успех — сериализуем и upsert
            data = _serialize_deep_result(result)
            await repo.upsert(
                domain,
                spf=data["spf"],
                mta_sts=data["mta_sts"],
                tls_rpt=data["tls_rpt"],
                dane=data["dane"],
                bimi=data["bimi"],
                fetched_at=now,
                next_check_at=next_check_at,
                is_reachable=True,
                fail_count=0,
                last_error=None,
            )

            logger.info(
                "Deep email collection completed for %s (spf=%s, mta_sts=%s, bimi=%s)",
                domain,
                "ok" if data["spf"] else "none",
                "ok" if data["mta_sts"] else "none",
                "ok" if data["bimi"] else "none",
            )

            return {
                "status": "success",
                "domain": domain,
                "fetched_at": now.isoformat(),
                "next_check_at": next_check_at.isoformat(),
            }

    except Exception as exc:
        logger.exception("Unexpected error in check_email_deep for %s", domain)
        return {
            "status": "internal_error",
            "domain": domain,
            "error": str(exc),
        }
    finally:
        clear_log_context()


__all__ = ["check_email_deep", "DEEP_EMAIL_TTL_SECONDS"]
