"""ARQ-задача ``check_dns_report``: on-demand расширенный DNS-отчёт (ADR 044).

По кнопке «🧾 DNS-отчёт» в карточке /whois. Собирает все DNS-записи домена
(``fetch_dns_report``), форматирует в текст и **доставляет файлом** в чат
кликнувшего (``deliver_chat_id``). В отличие от email/ssl/subdomains —
без БД-кэша: отчёт одноразовый, защита от спама — короткий redis-guard.

- Redis-guard ``dns_report_in_progress:<domain>`` — один воркер на домен.
- Успех → ``bot.send_document`` с .txt.
- Фейл → ``deliver_ondemand_failure`` (kind="dns"), не молчим (TASK-0086).
"""

from __future__ import annotations

import io
import logging
from contextlib import suppress
from typing import Any

from aiogram import Bot
from aiogram.types import BufferedInputFile
from redis.asyncio import Redis as AsyncRedis

from src.dns_report import DnsReportError, fetch_dns_report, format_dns_report
from src.observability import bind_log_context, clear_log_context
from src.services.audit import audit
from src.tasks._ondemand import deliver_ondemand_failure
from src.utils.idn import normalize_domain

logger = logging.getLogger(__name__)

_IN_PROGRESS_TTL_SECONDS = 90  # сбор + AXFR-пробы могут идти заметно


def _in_progress_key(domain: str) -> str:
    return f"dns_report_in_progress:{domain}"


async def check_dns_report(
    ctx: dict[str, Any],
    domain: str,
    deliver_chat_id: int | None = None,
    deliver_lang: str | None = None,
) -> dict[str, Any]:
    """Собрать расширенный DNS-отчёт и доставить .txt-файлом."""
    redis: AsyncRedis[str] = ctx["sync_redis"]
    bind_log_context(domain=domain, subsystem="dns_report")
    try:
        acquired = await redis.set(
            _in_progress_key(domain), "1", ex=_IN_PROGRESS_TTL_SECONDS, nx=True
        )
        if not acquired:
            logger.info("DNS report already in progress for %s", domain)
            return {"status": "already_in_progress", "domain": domain}

        result = await fetch_dns_report(domain)

        if isinstance(result, DnsReportError):
            logger.warning("DNS report failed for %s: %s", domain, result.message)
            await deliver_ondemand_failure(
                ctx, deliver_chat_id, deliver_lang, kind="dns", domain=domain
            )
            return {"status": "error", "domain": domain, "error_type": result.error_type}

        text = format_dns_report(result)
        if deliver_chat_id:
            bot: Bot | None = ctx.get("bot")
            if bot is not None:
                try:
                    safe = normalize_domain(domain).replace("/", "_")
                    doc = BufferedInputFile(
                        io.BytesIO(text.encode("utf-8")).getvalue(),
                        filename=f"dns_{safe}.txt",
                    )
                    await bot.send_document(deliver_chat_id, doc)
                    logger.info("Delivered DNS report to chat %s for %s", deliver_chat_id, domain)
                except Exception as exc:
                    logger.warning("Failed to deliver DNS report to %s: %s", deliver_chat_id, exc)

        return {
            "status": "success",
            "domain": domain,
            "records": len(result.records),
            "axfr_open": result.axfr_open,
        }

    except Exception as exc:
        logger.exception("Unexpected error in check_dns_report for %s", domain)
        with suppress(Exception):  # pragma: no cover
            await audit(
                level="error",
                category="task_failure",
                message="check_dns_report failed",
                actor="system",
                context={"task": "check_dns_report", "domain": domain, "error": str(exc)},
            )
        await deliver_ondemand_failure(
            ctx, deliver_chat_id, deliver_lang, kind="dns", domain=domain
        )
        return {"status": "internal_error", "domain": domain, "error": str(exc)}
    finally:
        with suppress(Exception):
            await redis.delete(_in_progress_key(domain))
        clear_log_context()


__all__ = ["check_dns_report"]
