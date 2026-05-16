"""Фасад WHOIS-ядра: ``lookup_domain``.

Внешний код (хэндлеры на Этапе 4, таски воркеров) пользуется ИСКЛЮЧИТЕЛЬНО
этой функцией. Внутри она:

1. Нормализует домен через IDN-конвертер.
2. Пробует RDAP (``whoisit``).
3. При неудаче/unsupported — fallback на WHOIS:43.
4. Возвращает ``WhoisData`` или ``WhoisError``.

Никаких побочных эффектов кроме сетевого I/O. Сохранение в БД, отправка
уведомлений — слой выше.
"""

from __future__ import annotations

import asyncio
import logging

import idna

from src.config.limits import Limits, get_limits
from src.config.settings import get_settings
from src.utils.idn import normalize_domain
from src.whois.parser import parse_rdap, parse_whois_text
from src.whois.rdap import query_rdap
from src.whois.types import WhoisData, WhoisError, WhoisResult
from src.whois.whois_protocol import WhoisProtocolError, query_whois

logger = logging.getLogger(__name__)


async def lookup_domain(domain: str, *, limits: Limits | None = None) -> WhoisResult:
    """Получает WHOIS-данные домена, RDAP с фоллбэком на WHOIS:43.

    ``limits`` параметризован для тестов; в проде берётся синглтон. Возвращает
    либо ``WhoisData``, либо ``WhoisError`` — ни в каком случае не бросает
    исключение.
    """
    cfg = limits if limits is not None else get_limits()
    timeout = float(cfg.whois_timeout_seconds)

    # Нормализация имени: ``Example.COM``/``пример.рф``/``https://...`` →
    # punycode, lowercase, без trailing dot.
    try:
        normalized = normalize_domain(domain)
    except (idna.IDNAError, ValueError, UnicodeError) as exc:
        return WhoisError(
            domain=domain,
            error_type="parse_error",
            message=f"invalid domain syntax: {exc}",
        )

    # --- RDAP ---
    rdap_status, rdap_data = await query_rdap(normalized, timeout=timeout)
    if rdap_status == "found" and rdap_data is not None:
        try:
            return parse_rdap(rdap_data, normalized)
        except Exception:
            # Парсер обещает не падать — но защищаемся на случай регрессий.
            logger.exception("parse_rdap crashed on %s", normalized)
            return WhoisError(
                domain=normalized,
                error_type="parse_error",
                message="RDAP parser crashed (see logs)",
            )
    if rdap_status == "not_found":
        return WhoisData(
            domain=normalized,
            is_registered=False,
            source="rdap",
        )

    # --- WHOIS:43 fallback ---
    try:
        raw_text = await query_whois(
            normalized,
            server_overrides=get_settings().whois_server_overrides,
            timeout=timeout,
        )
    except TimeoutError:
        return WhoisError(domain=normalized, error_type="timeout", message="WHOIS:43 timeout")
    except WhoisProtocolError as exc:
        # Нет известного WHOIS-сервера для TLD — это уже ``unsupported_tld``.
        # Сетевые/таймауты — ``network_error``.
        msg = str(exc)
        if msg.startswith("No WHOIS server"):
            return WhoisError(domain=normalized, error_type="unsupported_tld", message=msg)
        return WhoisError(domain=normalized, error_type="network_error", message=msg)

    try:
        return parse_whois_text(raw_text, normalized)
    except Exception:
        logger.exception("parse_whois_text crashed on %s", normalized)
        return WhoisError(
            domain=normalized,
            error_type="parse_error",
            message="WHOIS parser crashed (see logs)",
            raw_response=raw_text[:5000] if raw_text else None,
        )


async def lookup_with_semaphore(
    domain: str,
    semaphore: asyncio.Semaphore,
    *,
    limits: Limits | None = None,
) -> WhoisResult:
    """``lookup_domain`` под глобальным ``Semaphore``.

    Используется в воркерах (Этап 4), чтобы не превысить
    ``MAX_CONCURRENT_WHOIS`` и не получить бан от RDAP-серверов.
    """
    async with semaphore:
        return await lookup_domain(domain, limits=limits)


__all__ = ["WhoisData", "WhoisError", "WhoisResult", "lookup_domain", "lookup_with_semaphore"]
