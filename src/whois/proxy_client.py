"""HTTP-клиент к локальному WHOIS proxy gateway (ADR 028).

Прокси (на 127.0.0.1:8043) сам выбирает upstream (RDAP / WHOIS:43 /
выделенный RU-relay для .ru/.рф/.su) и кэширует ответы. Бот ходит за
WHOIS-данными через ``lookup_via_proxy`` ВСЕГДА (если фича включена в
``Settings.whois_proxy_enabled``); при недоступности прокси
(``ProxyUnreachable``) caller должен fall back на ``lookup_direct`` из
``src.whois.client``.

Спецификация ответа прокси (GET /q/<query> → 200):
- ``query`` — каноническая punycode-форма
- ``source`` — ``"whois" | "whois_ru_upstream" | "rdap" | "none"`` (proxy-side)
- ``cached``, ``fetched_at``, ``ttl_remaining`` — метаданные кеша
- ``ok``, ``data``, ``error``

``source`` proxy-стороны мапится на наш ``DataSource`` literal:
- ``rdap`` → ``proxy_rdap``
- ``whois`` → ``proxy_whois``
- ``whois_ru_upstream`` → ``proxy_whois_ru``
- ``none`` → ``proxy_none``
"""

from __future__ import annotations

import logging
from typing import Any, cast

import aiohttp
import idna

from src.config.settings import get_settings
from src.utils.idn import normalize_domain
from src.whois.parser import looks_like_upstream_error, parse_rdap, parse_whois_text
from src.whois.types import DataSource, WhoisData, WhoisError, WhoisResult

logger = logging.getLogger(__name__)


class ProxyUnreachable(Exception):  # noqa: N818 — публичный API, имя стабильно
    """Прокси недоступен — caller должен сделать fallback на direct lookup."""


_PROXY_TO_OUR_SOURCE: dict[str, DataSource] = {
    "rdap": "proxy_rdap",
    "whois": "proxy_whois",
    "whois_ru_upstream": "proxy_whois_ru",
    "none": "proxy_none",
}


async def lookup_via_proxy(
    domain: str,
    *,
    session: aiohttp.ClientSession | None = None,
) -> WhoisResult:
    """Запрос к WHOIS-proxy через HTTP/JSON.

    :param domain: домен (любая форма — нормализуем в punycode).
    :param session: переиспользуемая ``aiohttp.ClientSession`` или None
        (создадим и закроем сами; для одиночных вызовов из хэндлеров
        это нормально, для воркеров с массовыми проверками рекомендуется
        пробрасывать общую сессию).

    :raises ProxyUnreachable: прокси не отвечает (5xx / network / timeout)
        или отключён в настройках — caller делает fallback.
    """
    settings = get_settings()
    if not settings.whois_proxy_enabled:
        raise ProxyUnreachable("Proxy disabled in settings")

    try:
        normalized = normalize_domain(domain)
    except (idna.IDNAError, ValueError, UnicodeError) as exc:
        return WhoisError(
            domain=domain,
            error_type="parse_error",
            message=f"invalid domain syntax: {exc}",
        )

    url = f"{settings.whois_proxy_url}/q/{normalized}"
    timeout = aiohttp.ClientTimeout(total=settings.whois_proxy_timeout_seconds)

    own_session = session is None
    if session is None:
        session = aiohttp.ClientSession(timeout=timeout)
    try:
        try:
            async with session.get(url, timeout=timeout) as resp:
                if resp.status >= 500:
                    raise ProxyUnreachable(f"Proxy returned HTTP {resp.status}")
                if resp.status == 400:
                    return WhoisError(
                        domain=normalized,
                        error_type="parse_error",
                        message=f"Proxy rejected query: HTTP {resp.status}",
                    )
                if resp.status != 200:
                    raise ProxyUnreachable(f"Unexpected status {resp.status}")
                payload = await resp.json()
        except aiohttp.ClientError as exc:
            raise ProxyUnreachable(f"Network error: {exc}") from exc
        except TimeoutError as exc:
            # ``asyncio.TimeoutError`` в Python 3.11+ — алиас встроенного
            # ``TimeoutError``; обоих ловит одна ветка.
            raise ProxyUnreachable("Timeout calling proxy") from exc

        return _parse_proxy_response(payload, normalized)
    finally:
        if own_session:
            await session.close()


def _parse_proxy_response(payload: dict[str, Any], domain: str) -> WhoisResult:
    """Разбирает JSON-ответ прокси в наши доменные типы.

    Прокси гарантирует следующие ключи: ``source``, ``ok``, ``data``, ``error``,
    ``cached``, ``fetched_at``. Если структура не такая, отдаём
    ``WhoisError(parse_error)`` — это сигнал что прокси сломан, а не что
    домен битый.
    """
    source = str(payload.get("source", "none"))
    ok = bool(payload.get("ok", False))
    data = payload.get("data")
    error = payload.get("error")

    if not ok or source == "none":
        if error == "no_data":
            # Прокси убедительно говорит: домен не зарегистрирован.
            return WhoisData(
                domain=domain,
                is_registered=False,
                raw_data={"proxy_response": payload},
                source="proxy_none",
            )
        return WhoisError(
            domain=domain,
            error_type="parse_error",
            message=f"Proxy error: {error or 'unknown'}",
        )

    if source == "rdap":
        if not isinstance(data, dict):
            return WhoisError(
                domain=domain,
                error_type="parse_error",
                message="Expected dict for RDAP source",
            )
        result = parse_rdap(cast("dict[str, Any]", data), domain)
        result.source = _PROXY_TO_OUR_SOURCE["rdap"]
        _stamp_proxy_meta(result, payload)
        return result

    if source in ("whois", "whois_ru_upstream"):
        if not isinstance(data, str):
            return WhoisError(
                domain=domain,
                error_type="parse_error",
                message=f"Expected str for {source} source",
            )
        # TASK-0092: текст ошибки/рейтлимита/HTML от upstream — это сбой,
        # а не «домен свободен» (класс «сбой ≠ свободен», ср. TASK-0079).
        if looks_like_upstream_error(data):
            return WhoisError(
                domain=domain,
                error_type="unavailable",
                message=f"Upstream returned error-like text via {source}: {data[:120]!r}",
            )
        result = parse_whois_text(data, domain)
        result.source = _PROXY_TO_OUR_SOURCE[source]
        _stamp_proxy_meta(result, payload)
        result.raw_data["proxy_source"] = source
        return result

    return WhoisError(
        domain=domain,
        error_type="parse_error",
        message=f"Unknown proxy source: {source}",
    )


def _stamp_proxy_meta(result: WhoisData, payload: dict[str, Any]) -> None:
    """Добавляет в ``raw_data`` метку «пришло через прокси-кеш»."""
    if payload.get("cached"):
        result.raw_data["proxy_cached"] = True
    if payload.get("fetched_at") is not None:
        result.raw_data["proxy_fetched_at"] = payload["fetched_at"]


async def proxy_healthcheck(
    *,
    session: aiohttp.ClientSession | None = None,
) -> bool:
    """Быстрая liveness-проверка прокси.

    True, если ``/healthz`` ответил 200 за <5с. Любая ошибка/таймаут → False.
    Никогда не бросает — caller использует булеву логику.
    """
    settings = get_settings()
    if not settings.whois_proxy_enabled:
        return False

    timeout = aiohttp.ClientTimeout(total=5)
    own = session is None
    if session is None:
        session = aiohttp.ClientSession(timeout=timeout)
    try:
        async with session.get(f"{settings.whois_proxy_url}/healthz", timeout=timeout) as resp:
            return resp.status == 200
    except Exception as exc:  # — внешняя граница, любые ошибки = False
        logger.warning("Proxy healthcheck failed: %s", exc)
        return False
    finally:
        if own:
            await session.close()


__all__ = ["ProxyUnreachable", "lookup_via_proxy", "proxy_healthcheck"]
