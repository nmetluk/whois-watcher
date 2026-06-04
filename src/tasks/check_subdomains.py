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
from contextlib import suppress
from datetime import UTC, datetime
from typing import Any

from aiogram import Bot
from arq import ArqRedis
from redis.asyncio import Redis as AsyncRedis

from src.bot.keyboards import subdomains_keyboard
from src.db.repositories import SubdomainEnumCacheRepository
from src.db.session import get_session
from src.locales import t
from src.observability import bind_log_context, clear_log_context
from src.services.audit import audit
from src.subdomains.client import fetch_subdomains
from src.subdomains.diff import compute_subdomain_diff
from src.subdomains.scheduler import calculate_next_subdomain_check
from src.subdomains.types import SubdomainEnumError
from src.tasks._ondemand import deliver_ondemand_failure
from src.utils.formatting import format_date
from src.utils.idn import from_punycode

logger = logging.getLogger(__name__)

_IN_PROGRESS_TTL_SECONDS = 60


def _in_progress_key(registrable_domain: str) -> str:
    return f"subdomain_check_in_progress:{registrable_domain}"


async def check_subdomains(
    ctx: dict[str, Any],
    registrable_domain: str,
    deliver_chat_id: int | None = None,
    deliver_lang: str | None = None,
) -> dict[str, Any]:
    """ARQ-задача: проверить поддомены registrable-домена.

    Args:
        ctx: ARQ context
        registrable_domain: Registrable-домен (eTLD+1, ADR 035)
        deliver_chat_id: если задан (on-demand с кнопки whois-карточки, TASK-0075) —
            после успеха дослать результат в этот чат (bot.send_message).
        deliver_lang: язык для локализации доставленного сообщения.

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

                # TASK-0086: on-demand (с кнопки) — сообщить о фейле, а не молчать
                await deliver_ondemand_failure(
                    ctx,
                    deliver_chat_id,
                    deliver_lang,
                    kind="subdomains",
                    domain=registrable_domain,
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

            # TASK-0075: если вызов был с deliver_chat_id (on-demand кнопка с карточки /whois),
            # досылаем результат в чат кликнувшего (один раз, без повторного нажатия).
            if deliver_chat_id:
                bot: Bot = ctx.get("bot")  # type: ignore[assignment]
                if bot:
                    try:
                        display = from_punycode(registrable_domain)
                        subs = result.subdomains or []
                        count = len(subs)
                        fetched_at = format_date(now, lang=deliver_lang or "ru") if now else "—"
                        subdomain_list = "\n".join(
                            t(
                                "commands.subdomains.list_item",
                                deliver_lang or "ru",
                                subdomain=from_punycode(sub),
                            )
                            for sub in subs[:50]
                        )
                        text = (
                            t(
                                "commands.subdomains.header",
                                deliver_lang or "ru",
                                domain=display,
                                count=count,
                                fetched_at=fetched_at,
                            )
                            + f"\n\n{subdomain_list}"
                        )
                        markup = subdomains_keyboard(
                            registrable_domain, subs, lang=deliver_lang or "ru"
                        )
                        await bot.send_message(deliver_chat_id, text, reply_markup=markup)
                        logger.info(
                            "Delivered on-demand subdomains result to chat %s for %s",
                            deliver_chat_id,
                            registrable_domain,
                        )
                    except Exception as deliver_exc:
                        logger.warning(
                            "Failed to deliver subdomains result to %s: %s",
                            deliver_chat_id,
                            deliver_exc,
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
        with suppress(Exception):  # pragma: no cover
            await audit(
                level="error",
                category="task_failure",
                message="check_subdomains failed",
                actor="system",
                context={
                    "task": "check_subdomains",
                    "registrable_domain": registrable_domain,
                    "error": str(exc),
                },
            )
        # TASK-0086: и при неожиданном падении тоже сообщаем кликнувшему
        await deliver_ondemand_failure(
            ctx, deliver_chat_id, deliver_lang, kind="subdomains", domain=registrable_domain
        )
        return {
            "status": "internal_error",
            "registrable_domain": registrable_domain,
            "error": str(exc),
        }
    finally:
        clear_log_context()


__all__ = ["check_subdomains"]
