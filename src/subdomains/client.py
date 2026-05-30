"""Async HTTP-клиент к crt.sh (TASK-0023, ADR 037).

Запрашивает поддомены через CT-логи:
- GET https://crt.sh/?q=%25.<registrable>&output=json
- Таймаут для graceful degradation
- Обработка ошибок без исключений наружу
"""

from __future__ import annotations

import json
import logging

import aiohttp

from src.subdomains.parser import parse_crtsh_response
from src.subdomains.types import SubdomainEnumError, SubdomainEnumResult, SubdomainEnumResultOrError
from src.utils.idn import normalize_domain

logger = logging.getLogger(__name__)

# Таймауты crt.sh (seconds)
TOTAL_TIMEOUT = 45

# crt.sh endpoint
CRTSH_URL = "https://crt.sh/"


async def fetch_subdomains(registrable_domain: str) -> SubdomainEnumResultOrError:
    """Запрашивает поддомены для registrable-домена через crt.sh.

    Args:
        registrable_domain: Registrable-домен (eTLD+1, ADR 035)

    Returns:
        SubdomainEnumResult при успехе, SubdomainEnumError при ошибке
    """
    # Нормализация домена
    try:
        normalized = normalize_domain(registrable_domain)
    except Exception as exc:
        return SubdomainEnumError(
            registrable_domain=registrable_domain,
            error_type="parse_error",
            message=f"Invalid domain syntax: {exc}",
        )

    # Формируем URL: %25. для wildcard поиска
    url = f"{CRTSH_URL}?q=%25.{normalized}&output=json"

    timeout = aiohttp.ClientTimeout(total=TOTAL_TIMEOUT)

    try:
        async with (
            aiohttp.ClientSession(timeout=timeout) as session,
            session.get(url) as response,
        ):
            # Проверяем на rate-limit (429)
            if response.status == 429:
                logger.warning("crt.sh rate limit for %s", normalized)
                return SubdomainEnumError(
                    registrable_domain=normalized,
                    error_type="rate_limit",
                    message="crt.sh rate limit exceeded",
                )

            # Проверяем на другие ошибки HTTP
            if response.status >= 400:
                logger.warning("crt.sh returned %s for %s", response.status, normalized)
                return SubdomainEnumError(
                    registrable_domain=normalized,
                    error_type="unavailable",
                    message=f"crt.sh returned HTTP {response.status}",
                )

            # Парсим JSON
            try:
                data = await response.json()
            except (TimeoutError, json.JSONDecodeError) as exc:
                logger.warning("crt.sh invalid JSON for %s: %s", normalized, exc)
                return SubdomainEnumError(
                    registrable_domain=normalized,
                    error_type="parse_error",
                    message=f"Invalid JSON response: {exc}",
                )

            # crt.sh может вернуть не-лист (защита)
            if not isinstance(data, list):
                logger.warning("crt.sh unexpected response type for %s", normalized)
                return SubdomainEnumError(
                    registrable_domain=normalized,
                    error_type="parse_error",
                    message="Unexpected response format",
                )

            # Парсим поддомены
            subdomains = parse_crtsh_response(normalized, data)

            return SubdomainEnumResult(
                registrable_domain=normalized,
                subdomains=subdomains,
                is_reachable=True,
            )

    except aiohttp.ClientError as exc:
        # Сетевые ошибки (timeout, connection failed)
        logger.warning("crt.sh network error for %s: %s", normalized, exc)
        return SubdomainEnumError(
            registrable_domain=normalized,
            error_type="timeout",
            message=f"Network error: {exc}",
        )
    except TimeoutError as exc:
        logger.warning("crt.sh timeout for %s", normalized)
        return SubdomainEnumError(
            registrable_domain=normalized,
            error_type="timeout",
            message=f"Request timeout: {exc}",
        )
    except Exception as exc:
        logger.warning("crt.sh unexpected error for %s: %s", normalized, exc)
        return SubdomainEnumError(
            registrable_domain=normalized,
            error_type="unavailable",
            message=f"Unexpected error: {exc}",
        )


__all__ = [
    "TOTAL_TIMEOUT",
    "fetch_subdomains",
]
