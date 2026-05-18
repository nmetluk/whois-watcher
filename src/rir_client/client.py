"""HTTP-клиент к локальному rir2localdb (ADR 031).

Async, aiohttp-based. Стиль зеркалит ``src.whois.proxy_client`` (ADR 028)
для консистентности с уже устоявшимися практиками проекта.

Error policy:

- ``lookup_ip``, ``lookup_asn`` возвращают ``RIRError`` (НЕ raise) на любую
  ошибку — для предсказуемого pattern-matching у callers
- ``healthcheck``, ``get_status`` raise ``RIRUnreachable`` на network/HTTP
  ошибки — используется в cron-таске, где исключения идиоматичнее
"""

from __future__ import annotations

import logging
from typing import Any, Final

import aiohttp
from pydantic import ValidationError

from src.config.settings import get_settings
from src.rir_client.errors import RIRError, RIRUnreachable
from src.rir_client.types import ASNAllocation, IPAllocation, RIRStatus

logger = logging.getLogger(__name__)

# Endpoint paths
HEALTHZ_PATH: Final = "/v1/healthz"
STATUS_PATH: Final = "/v1/status"
IP_PATH: Final = "/v1/ip/{addr}"
ASN_PATH: Final = "/v1/asn/{num}"


def _client_timeout() -> aiohttp.ClientTimeout:
    settings = get_settings()
    return aiohttp.ClientTimeout(
        total=settings.rir2localdb_timeout_seconds,
        connect=settings.rir2localdb_connect_timeout_seconds,
    )


def _url(path: str) -> str:
    base = get_settings().rir2localdb_url.rstrip("/")
    return f"{base}{path}"


async def lookup_ip(
    addr: str,
    *,
    include_rpsl: bool = True,
    session: aiohttp.ClientSession | None = None,
) -> IPAllocation | RIRError:
    """Lookup IP-аллокации в rir2localdb.

    :param addr: IPv4 / IPv6 адрес (строка). Валидируется сервером.
    :param include_rpsl: запрашивать ли RPSL-блок (organisation/inetnum).
    :param session: переиспользуемая ``aiohttp.ClientSession`` или None
        (создаём и закрываем сами).
    """
    settings = get_settings()
    if not settings.rir2localdb_enabled:
        return RIRError(kind="disabled", detail="rir2localdb_enabled=false")

    url = _url(IP_PATH.format(addr=addr))
    params = {"include_rpsl": "true" if include_rpsl else "false"}
    timeout = _client_timeout()

    own = session is None
    if session is None:
        session = aiohttp.ClientSession(timeout=timeout)
    try:
        try:
            async with session.get(url, params=params, timeout=timeout) as resp:
                return await _parse_ip_response(resp, addr)
        except aiohttp.ClientError as exc:
            logger.warning("rir_client.lookup_ip.network_error addr=%s exc=%s", addr, exc)
            return RIRError(kind="unreachable", detail=f"network error: {exc}")
        except TimeoutError:
            logger.warning("rir_client.lookup_ip.timeout addr=%s", addr)
            return RIRError(kind="unreachable", detail="timeout")
    finally:
        if own:
            await session.close()


async def _parse_ip_response(
    resp: aiohttp.ClientResponse,
    addr: str,
) -> IPAllocation | RIRError:
    if resp.status == 200:
        try:
            data = await resp.json()
            return IPAllocation.model_validate(data)
        except ValidationError as exc:
            logger.error(
                "rir_client.lookup_ip.invalid_response addr=%s errors=%d",
                addr,
                exc.error_count(),
            )
            return RIRError(
                kind="invalid_response",
                detail=f"schema mismatch: {exc.error_count()} errors",
                status_code=200,
            )
    if resp.status == 404:
        return RIRError(
            kind="not_found",
            detail=f"IP {addr} not in any RIR allocation",
            status_code=404,
        )
    if resp.status == 400:
        body = (await resp.text())[:200]
        return RIRError(kind="bad_request", detail=body, status_code=400)
    if 500 <= resp.status < 600:
        body = (await resp.text())[:200]
        return RIRError(kind="server_error", detail=body, status_code=resp.status)
    body = (await resp.text())[:100]
    return RIRError(
        kind="server_error",
        detail=f"unexpected status: {body}",
        status_code=resp.status,
    )


async def lookup_asn(
    num: int,
    *,
    include_rpsl: bool = True,
    session: aiohttp.ClientSession | None = None,
) -> ASNAllocation | RIRError:
    """Lookup ASN-информации в rir2localdb.

    :param num: ASN integer (например 15169 для Google).
    :param include_rpsl: запрашивать ли RPSL-блок (aut_num/organisation).
    :param session: переиспользуемая ``aiohttp.ClientSession`` или None.
    """
    settings = get_settings()
    if not settings.rir2localdb_enabled:
        return RIRError(kind="disabled", detail="rir2localdb_enabled=false")

    url = _url(ASN_PATH.format(num=num))
    params = {"include_rpsl": "true" if include_rpsl else "false"}
    timeout = _client_timeout()

    own = session is None
    if session is None:
        session = aiohttp.ClientSession(timeout=timeout)
    try:
        try:
            async with session.get(url, params=params, timeout=timeout) as resp:
                return await _parse_asn_response(resp, num)
        except aiohttp.ClientError as exc:
            logger.warning("rir_client.lookup_asn.network_error asn=%s exc=%s", num, exc)
            return RIRError(kind="unreachable", detail=f"network error: {exc}")
        except TimeoutError:
            logger.warning("rir_client.lookup_asn.timeout asn=%s", num)
            return RIRError(kind="unreachable", detail="timeout")
    finally:
        if own:
            await session.close()


async def _parse_asn_response(
    resp: aiohttp.ClientResponse,
    num: int,
) -> ASNAllocation | RIRError:
    if resp.status == 200:
        try:
            data = await resp.json()
            return ASNAllocation.model_validate(data)
        except ValidationError as exc:
            logger.error(
                "rir_client.lookup_asn.invalid_response asn=%s errors=%d",
                num,
                exc.error_count(),
            )
            return RIRError(
                kind="invalid_response",
                detail=f"schema mismatch: {exc.error_count()} errors",
                status_code=200,
            )
    if resp.status == 404:
        return RIRError(
            kind="not_found",
            detail=f"ASN {num} not in any RIR allocation",
            status_code=404,
        )
    if resp.status == 400:
        body = (await resp.text())[:200]
        return RIRError(kind="bad_request", detail=body, status_code=400)
    if 500 <= resp.status < 600:
        body = (await resp.text())[:200]
        return RIRError(kind="server_error", detail=body, status_code=resp.status)
    body = (await resp.text())[:100]
    return RIRError(
        kind="server_error",
        detail=f"unexpected status: {body}",
        status_code=resp.status,
    )


async def healthcheck(
    *,
    session: aiohttp.ClientSession | None = None,
) -> bool:
    """Пинг ``/v1/healthz``.

    True если сервис ответил 200 с ``{"status":"ok"}``. False если
    ``rir2localdb_enabled=False`` или сервис ответил 200 но статус не ok.

    :raises RIRUnreachable: network failure / non-200 / malformed JSON.
    """
    settings = get_settings()
    if not settings.rir2localdb_enabled:
        return False

    url = _url(HEALTHZ_PATH)
    timeout = _client_timeout()
    own = session is None
    if session is None:
        session = aiohttp.ClientSession(timeout=timeout)
    try:
        try:
            async with session.get(url, timeout=timeout) as resp:
                if resp.status != 200:
                    raise RIRUnreachable(f"healthz returned {resp.status}")
                data = await resp.json()
                return bool(data.get("status") == "ok")
        except aiohttp.ClientError as exc:
            raise RIRUnreachable(f"healthz client error: {exc}") from exc
        except TimeoutError as exc:
            raise RIRUnreachable("healthz timeout") from exc
    finally:
        if own:
            await session.close()


async def get_status(
    *,
    session: aiohttp.ClientSession | None = None,
) -> RIRStatus:
    """Получить детальный ``/v1/status`` (последний sync run, источники).

    :raises RIRUnreachable: network failure / non-200 / схема не валидируется
        (используется в cron, где исключение идиоматично).
    """
    settings = get_settings()
    if not settings.rir2localdb_enabled:
        raise RIRUnreachable("rir2localdb disabled via settings")

    url = _url(STATUS_PATH)
    timeout = _client_timeout()
    own = session is None
    if session is None:
        session = aiohttp.ClientSession(timeout=timeout)
    try:
        try:
            async with session.get(url, timeout=timeout) as resp:
                if resp.status != 200:
                    raise RIRUnreachable(f"status returned {resp.status}")
                data: dict[str, Any] = await resp.json()
                try:
                    return RIRStatus.model_validate(data)
                except ValidationError as exc:
                    raise RIRUnreachable(
                        f"status schema mismatch: {exc.error_count()} errors"
                    ) from exc
        except aiohttp.ClientError as exc:
            raise RIRUnreachable(f"status client error: {exc}") from exc
        except TimeoutError as exc:
            raise RIRUnreachable("status timeout") from exc
    finally:
        if own:
            await session.close()


__all__ = [
    "get_status",
    "healthcheck",
    "lookup_asn",
    "lookup_ip",
]
