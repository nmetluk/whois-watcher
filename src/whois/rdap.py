"""RDAP-клиент поверх ``whoisit`` (ADR 008).

Возвращает сырой RDAP-JSON (см. RFC 7483), парсинг — отдельно
(``src.whois.parser.parse_rdap``). Это позволяет тестировать парсер
на фикстурах, не дёргая сеть.

``whoisit`` имеет нативный ``domain_async`` (async поверх httpx), так что
никакой ``asyncio.to_thread`` не нужен. Перед первым запросом обязательно
``bootstrap_async`` — он подтягивает IANA-таблицу TLD→RDAP-сервер. Bootstrap
кешируем на процесс через ``asyncio.Lock``.

Возвращаемые исходы:

- ``("found", data)``    — RDAP вернул валидный объект домена
- ``("not_found", None)``— RDAP сказал, что такого домена нет (NXDOMAIN)
- ``("unsupported", None)`` — для этого TLD нет RDAP-сервера
- ``("error", None)``    — таймаут / сеть / rate-limit; решение о повторе
  принимает уровень выше (фасад ``client.py``)
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Literal

import whoisit
from whoisit.errors import (
    BootstrapError,
    QueryError,
    RateLimitedError,
    RemoteServerError,
    ResourceAccessDeniedError,
    ResourceDoesNotExist,
    UnsupportedError,
)

logger = logging.getLogger(__name__)


RdapStatus = Literal["found", "not_found", "unsupported", "error"]
RdapResult = tuple[RdapStatus, dict[str, Any] | None]

# Однопроцессный «синглтон» состояния bootstrap'а. ``whoisit.is_bootstrapped``
# проверяет тот же глобальный кеш, но Lock нужен, чтобы параллельные
# первые запросы не дёргали bootstrap гонкой.
_bootstrap_lock = asyncio.Lock()


async def _ensure_bootstrapped() -> None:
    """Гарантирует, что ``whoisit`` подгрузил IANA-таблицу bootstrap.

    Идемпотентно: повторные вызовы — no-op. При ошибке bootstrap'а
    пробрасываем — фасад превратит в ``WhoisError(network_error)``.
    """
    if whoisit.is_bootstrapped():
        return
    async with _bootstrap_lock:
        if whoisit.is_bootstrapped():
            return
        await whoisit.bootstrap_async()


async def query_rdap(
    domain: str,
    *,
    timeout: float,
    retries: int = 1,
) -> RdapResult:
    """Запрашивает RDAP по домену с одним повтором по таймауту/сети.

    Возвращает сырой JSON-ответ как dict (``whoisit ... raw=True``) — парсинг
    в ``parser.parse_rdap``.

    Повторы: ``retries`` дополнительных попыток сверх первой, с экспоненциальной
    задержкой (1с, 2с, ...). Повторяем только сетевые ошибки и таймауты — на
    ``RateLimitedError`` и ``ResourceDoesNotExist`` повтор бессмысленен.
    """
    try:
        await _ensure_bootstrapped()
    except (BootstrapError, OSError) as exc:
        logger.warning("RDAP bootstrap failed for %s: %s", domain, exc)
        return ("error", None)

    attempt = 0
    while True:
        try:
            data = await asyncio.wait_for(
                whoisit.domain_async(domain, raw=True),
                timeout=timeout,
            )
        except UnsupportedError:
            # Нет RDAP-сервера для этого TLD — переключаемся на WHOIS:43.
            return ("unsupported", None)
        except ResourceDoesNotExist:
            # NXDOMAIN: домен свободен. Заглушка-payload для парсера.
            return ("not_found", None)
        except RateLimitedError:
            logger.info("RDAP rate-limited for %s", domain)
            return ("error", None)
        except ResourceAccessDeniedError as exc:
            # Сервер блокирует наш IP / геозапрет. Не сетевая, но похоже —
            # эскалируем как ошибку, без повтора.
            logger.info("RDAP access denied for %s: %s", domain, exc)
            return ("error", None)
        except TimeoutError:
            if attempt < retries:
                attempt += 1
                await asyncio.sleep(2 ** (attempt - 1))
                continue
            logger.info("RDAP timeout for %s after %d attempt(s)", domain, attempt + 1)
            return ("error", None)
        except (RemoteServerError, QueryError, OSError) as exc:
            if attempt < retries:
                attempt += 1
                await asyncio.sleep(2 ** (attempt - 1))
                logger.debug("RDAP retry %d for %s: %s", attempt, domain, exc)
                continue
            logger.info("RDAP error for %s: %s", domain, exc)
            return ("error", None)
        else:
            if not isinstance(data, dict):
                logger.warning("RDAP returned non-dict for %s: %r", domain, type(data))
                return ("error", None)
            return ("found", data)
