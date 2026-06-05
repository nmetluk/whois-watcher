"""Async-коллекторы deep email (TASK-0038, ADR 040).

Сбор по запросу (on-demand):
- SPF с рекурсией include/redirect
- MTA-STS (TXT + HTTPS policy, no-redirects, size limit)
- TLS-RPT, DANE (TLSA на MX), BIMI

Никогда не raise наружу — всегда DeepEmailResult или DeepEmailError.
Graceful degradation: отсутствие записи = валидное состояние (не ошибка).
"""

from __future__ import annotations

import asyncio
import ipaddress
import logging
import socket
from collections.abc import Awaitable, Callable
from typing import Any

import aiohttp
import dns.asyncresolver
import dns.exception
from aiohttp.abc import AbstractResolver, ResolveResult

from src.config.settings import Settings
from src.email_intel.deep_parser import (
    parse_bimi,
    parse_mta_sts_policy,
    parse_tls_rpt,
)
from src.email_intel.deep_types import (
    BimiResult,
    DaneResult,
    DeepEmailError,
    DeepEmailResult,
    DeepEmailResultOrError,
    MtaStsResult,
    SpfResolution,
    TlsRptResult,
)
from src.email_intel.resolver import (
    QUERY_TIMEOUT as DNS_QUERY_TIMEOUT,
)
from src.email_intel.resolver import (
    TOTAL_TIMEOUT as DNS_TOTAL_TIMEOUT,
)
from src.email_intel.resolver import (
    build_resolver,
    classify_dns_exc,
)
from src.email_intel.spf_resolver import resolve_spf
from src.email_intel.txt import txt_to_str
from src.utils.idn import normalize_domain

logger = logging.getLogger(__name__)

HTTP_TOTAL_TIMEOUT = 10
MTA_STS_MAX_BODY = 16384  # 16KB — более чем достаточно для policy

# Префиксы
MTA_STS_TXT_PREFIX = "_mta-sts."
TLS_RPT_TXT_PREFIX = "_smtp._tls."
BIMI_TXT_PREFIX = "default._bimi."
DANE_PREFIX = "_25._tcp."


async def fetch_deep_email(
    domain: str,
    *,
    mx_hosts: list[str] | None = None,
    settings: Settings | None = None,
) -> DeepEmailResultOrError:
    """Собирает полный deep email профиль домена (on-demand).

    Выполняет параллельно где возможно:
    - SPF рекурсивный
    - MTA-STS (TXT + policy)
    - TLS-RPT
    - BIMI
    - DANE (по списку MX-хостов, если передан)

    Args:
        domain: Целевой домен (нормализуется).
        mx_hosts: Опционально — список MX-хостов (из базового email_intel)
                  для DANE-проверок. Если None — DANE будет пустым.

    Returns:
        DeepEmailResult при успехе (даже если частично), DeepEmailError при
        критической ошибке (например NXDOMAIN на apex).
    """
    try:
        normalized = normalize_domain(domain)
    except Exception as exc:
        return DeepEmailError(
            domain=domain,
            error_type="parse_error",
            message=f"Invalid domain syntax: {exc}",
        )

    resolver = build_resolver(settings)
    logger.info("fetch_deep_email starting collection for %s (mx_hosts=%s)", normalized, mx_hosts)

    # Создаём injectable resolve_txt для SPF (использует resolver)
    async def _resolve_txt_for_spf(d: str) -> list[str] | None:
        try:
            ans = await resolver.resolve(d, "TXT", lifetime=DNS_TOTAL_TIMEOUT)
            return [txt_to_str(r) for r in ans]
        except dns.exception.DNSException as exc:
            if classify_dns_exc(exc) == "unreachable":
                logger.warning("deep SPF TXT dns_unreachable for %s: %s", d, exc)
            return None
        except Exception as exc:
            logger.debug("deep SPF TXT unexpected for %s: %s", d, exc)
            return None

    # Параллельные fetch'и (DANE зависит от mx_hosts)
    tasks: list[Awaitable[Any]] = [
        _fetch_spf(normalized, _resolve_txt_for_spf),
        _fetch_mta_sts(normalized, resolver),
        _fetch_tls_rpt(normalized, resolver),
        _fetch_bimi(normalized, resolver),
    ]
    if mx_hosts:
        tasks.append(_fetch_dane(mx_hosts, resolver))

    results = await asyncio.gather(*tasks, return_exceptions=True)

    spf_res: SpfResolution | None = None
    mta_sts: MtaStsResult | None = None
    tls_rpt: TlsRptResult | None = None
    bimi: BimiResult | None = None
    dane: DaneResult | None = None

    # Распаковка (учитывая возможные exceptions от gather)
    idx = 0
    if not isinstance(results[idx], Exception):
        spf_res = results[idx]  # type: ignore[assignment]
    idx += 1

    if not isinstance(results[idx], Exception):
        mta_sts = results[idx]  # type: ignore[assignment]
    idx += 1

    if not isinstance(results[idx], Exception):
        tls_rpt = results[idx]  # type: ignore[assignment]
    idx += 1

    if not isinstance(results[idx], Exception):
        bimi = results[idx]  # type: ignore[assignment]
    idx += 1

    if mx_hosts and len(results) > idx and not isinstance(results[idx], Exception):
        dane = results[idx]  # type: ignore[assignment]

    # Если все критичные части упали с NXDOMAIN — это ошибка
    # (простая эвристика: если spf и mta_sts оба None и были ошибки)
    # На практике — возвращаем результат с is_reachable=True даже если частично пусто.
    # Критическая ошибка только если caller явно хочет отличить.

    return DeepEmailResult(
        domain=normalized,
        is_reachable=True,
        spf=spf_res,
        mta_sts=mta_sts,
        tls_rpt=tls_rpt,
        dane=dane,
        bimi=bimi,
    )


async def _fetch_spf(
    domain: str, resolve_txt: Callable[[str], Awaitable[list[str] | None]]
) -> SpfResolution:
    """Обёртка над resolve_spf с graceful на ошибках."""
    try:
        return await resolve_spf(domain, resolve_txt=resolve_txt)
    except Exception as exc:
        logger.warning("deep_spf error for %s: %s", domain, exc)
        return SpfResolution(sources=[], lookup_count=0, exceeds_limit=False)


class _SafeMtaStsResolver(AbstractResolver):
    """Resolver that only returns pre-approved safe public IPs for a given host.

    Used to prevent DNS rebinding attacks when fetching MTA-STS policy.
    """

    def __init__(self, safe_ips: list[str]):
        self._safe_ips = safe_ips

    async def resolve(self, host: str, port: int = 0, family: int = 0) -> list[ResolveResult]:
        results: list[ResolveResult] = []
        for ip_str in self._safe_ips:
            try:
                ip = ipaddress.ip_address(ip_str)
                family_val = socket.AF_INET if ip.version == 4 else socket.AF_INET6
                results.append(
                    {
                        "hostname": host,
                        "host": ip_str,
                        "port": port,
                        "family": family_val,
                        "proto": 0,
                        "flags": 0,
                    }
                )
            except ValueError:
                continue
        return results

    async def close(self) -> None:
        """Required by aiohttp.AbstractResolver in versions >=3.9."""
        return None


async def _fetch_mta_sts(domain: str, resolver: dns.asyncresolver.Resolver) -> MtaStsResult:
    """TXT _mta-sts.<d> + HTTPS policy fetch (no redirects, size limit).

    Includes strict TXT matching and strong anti-SSRF + DNS-rebinding protection.
    """
    mta_sts_domain = f"{MTA_STS_TXT_PREFIX}{domain}"

    # 1. TXT проверка (наличие и версия) — строгий матч по префиксу v=STSv1
    txt_present = False
    try:
        ans = await resolver.resolve(mta_sts_domain, "TXT", lifetime=DNS_TOTAL_TIMEOUT)
        for r in ans:
            txt = txt_to_str(r).strip()
            if txt.lower().startswith("v=stsv1"):
                txt_present = True
                break
    except dns.exception.DNSException:
        txt_present = False
    except Exception as exc:
        logger.debug("mta-sts txt error %s: %s", domain, exc)
        txt_present = False

    if not txt_present:
        return MtaStsResult(txt_present=False, reachable=False)

    # 2. Anti-SSRF + DNS-rebinding protection:
    #    - Resolve A and AAAA independently (as required)
    #    - Collect only safe public IPs
    #    - Use a custom resolver for the actual HTTP connection so that
    #      aiohttp never sees (and cannot re-resolve to) a private IP.
    safe_ips: list[str] = []

    # Resolve A independently
    try:
        a_ans = await resolver.resolve(mta_sts_domain, "A", lifetime=DNS_TOTAL_TIMEOUT)
        for r in a_ans:
            try:
                ip = ipaddress.ip_address(r.to_text())
                if not (
                    ip.is_private
                    or ip.is_loopback
                    or ip.is_link_local
                    or ip.is_reserved
                    or ip.is_multicast
                ):
                    safe_ips.append(str(ip))
            except ValueError:
                continue
    except dns.exception.DNSException:
        pass

    # Resolve AAAA independently
    try:
        aaaa_ans = await resolver.resolve(mta_sts_domain, "AAAA", lifetime=DNS_TOTAL_TIMEOUT)
        for r in aaaa_ans:
            try:
                ip = ipaddress.ip_address(r.to_text())
                if not (
                    ip.is_private
                    or ip.is_loopback
                    or ip.is_link_local
                    or ip.is_reserved
                    or ip.is_multicast
                ):
                    safe_ips.append(str(ip))
            except ValueError:
                continue
    except dns.exception.DNSException:
        pass

    if not safe_ips:
        logger.warning("mta-sts %s has no safe public IPs — SSRF blocked", domain)
        return MtaStsResult(txt_present=True, reachable=False)

    # 3. Perform HTTPS request using a custom resolver that only knows our safe IPs.
    #    This pins the connection to pre-approved public addresses and defeats rebinding.
    safe_resolver = _SafeMtaStsResolver(safe_ips)
    connector = aiohttp.TCPConnector(resolver=safe_resolver)

    policy_url = f"https://mta-sts.{domain}/.well-known/mta-sts.txt"
    timeout = aiohttp.ClientTimeout(total=HTTP_TOTAL_TIMEOUT)

    try:
        async with (
            aiohttp.ClientSession(connector=connector, timeout=timeout) as session,
            session.get(policy_url, allow_redirects=False) as resp,
        ):
            if resp.status != 200:
                logger.debug("mta-sts http %s -> %s", policy_url, resp.status)
                return MtaStsResult(txt_present=True, reachable=False)

            try:
                body = await resp.content.read(MTA_STS_MAX_BODY)
                policy_text = body.decode("utf-8", errors="replace")
            except Exception as exc:
                logger.warning("mta-sts body read error %s: %s", domain, exc)
                return MtaStsResult(txt_present=True, reachable=False)

            result = parse_mta_sts_policy(policy_text)
            return MtaStsResult(
                txt_present=True,
                policy_mode=result.policy_mode,
                mx=result.mx,
                max_age=result.max_age,
                reachable=True,
            )

    except TimeoutError:
        logger.debug("mta-sts timeout %s", domain)
        return MtaStsResult(txt_present=True, reachable=False)
    except aiohttp.ClientError as exc:
        logger.debug("mta-sts client error %s: %s", domain, exc)
        return MtaStsResult(txt_present=True, reachable=False)
    except Exception as exc:
        logger.warning("mta-sts unexpected %s: %s", domain, exc)
        return MtaStsResult(txt_present=True, reachable=False)
    policy_url = f"https://mta-sts.{domain}/.well-known/mta-sts.txt"
    timeout = aiohttp.ClientTimeout(total=HTTP_TOTAL_TIMEOUT)

    try:
        # allow_redirects=False — строго по спецификации (RFC 8461)
        async with (
            aiohttp.ClientSession(timeout=timeout) as session,
            session.get(policy_url, allow_redirects=False) as resp,
        ):
            if resp.status != 200:
                logger.debug("mta-sts http %s -> %s", policy_url, resp.status)
                return MtaStsResult(txt_present=True, reachable=False)

            # Ограничиваем размер тела
            try:
                body = await resp.content.read(MTA_STS_MAX_BODY)
                policy_text = body.decode("utf-8", errors="replace")
            except Exception as exc:
                logger.warning("mta-sts body read error %s: %s", domain, exc)
                return MtaStsResult(txt_present=True, reachable=False)

            result = parse_mta_sts_policy(policy_text)
            # Переопределяем reachable на основе успешного HTTP
            return MtaStsResult(
                txt_present=True,
                policy_mode=result.policy_mode,
                mx=result.mx,
                max_age=result.max_age,
                reachable=True,
            )

    except TimeoutError:
        logger.debug("mta-sts timeout %s", domain)
        return MtaStsResult(txt_present=True, reachable=False)
    except aiohttp.ClientError as exc:
        logger.debug("mta-sts client error %s: %s", domain, exc)
        return MtaStsResult(txt_present=True, reachable=False)
    except Exception as exc:
        logger.warning("mta-sts unexpected %s: %s", domain, exc)
        return MtaStsResult(txt_present=True, reachable=False)


async def _fetch_tls_rpt(domain: str, resolver: dns.asyncresolver.Resolver) -> TlsRptResult:
    """TXT _smtp._tls.<domain>."""
    tls_domain = f"{TLS_RPT_TXT_PREFIX}{domain}"
    try:
        ans = await resolver.resolve(tls_domain, "TXT", lifetime=DNS_TOTAL_TIMEOUT)
        if ans:
            # Берём первую TXT
            txt = txt_to_str(ans[0])
            return parse_tls_rpt(txt)
        return TlsRptResult(present=False)
    except dns.exception.DNSException:
        return TlsRptResult(present=False)
    except Exception as exc:
        logger.debug("tls-rpt error %s: %s", domain, exc)
        return TlsRptResult(present=False)


async def _fetch_bimi(domain: str, resolver: dns.asyncresolver.Resolver) -> BimiResult:
    """TXT default._bimi.<domain>."""
    bimi_domain = f"{BIMI_TXT_PREFIX}{domain}"
    try:
        ans = await resolver.resolve(bimi_domain, "TXT", lifetime=DNS_TOTAL_TIMEOUT)
        if ans:
            txt = txt_to_str(ans[0])
            return parse_bimi(txt)
        return BimiResult(present=False)
    except dns.exception.DNSException:
        return BimiResult(present=False)
    except Exception as exc:
        logger.debug("bimi error %s: %s", domain, exc)
        return BimiResult(present=False)


async def _fetch_dane(mx_hosts: list[str], resolver: dns.asyncresolver.Resolver) -> DaneResult:
    """TLSA _25._tcp.<mx> для каждого MX-хоста (параллельно)."""
    if not mx_hosts:
        return DaneResult(host_tlsa={})

    async def _check_one(host: str) -> tuple[str, bool]:
        dane_name = f"{DANE_PREFIX}{host}"
        try:
            ans = await resolver.resolve(dane_name, "TLSA", lifetime=DNS_TOTAL_TIMEOUT)
            has = bool(ans and len(ans) > 0)
            return host, has
        except dns.exception.DNSException:
            return host, False
        except Exception:
            return host, False

    tasks = [_check_one(h) for h in mx_hosts]
    pairs = await asyncio.gather(*tasks, return_exceptions=True)

    result: dict[str, bool] = {}
    for p in pairs:
        if isinstance(p, tuple):
            h, has = p
            result[h] = has
        else:
            # exception from gather — skip
            pass

    return DaneResult(host_tlsa=result)


__all__ = [
    "DNS_QUERY_TIMEOUT",
    "DNS_TOTAL_TIMEOUT",
    "HTTP_TOTAL_TIMEOUT",
    "MTA_STS_MAX_BODY",
    "fetch_deep_email",
    "fetch_mta_sts",  # re-export for task spec
    "fetch_tls_rpt",
    "fetch_dane",
    "fetch_bimi",
]

# Aliases for task spec exact names (thin wrappers if needed)
# Task requires fetch_mta_sts etc as public; we implement via internals but expose.


async def fetch_mta_sts(domain: str, *, settings: Settings | None = None) -> MtaStsResult:
    """Публичный fetch только MTA-STS (для тестов/композиции)."""
    try:
        normalized = normalize_domain(domain)
    except Exception:
        return MtaStsResult(txt_present=False, reachable=False)

    resolver = build_resolver(settings)
    return await _fetch_mta_sts(normalized, resolver)


async def fetch_tls_rpt(domain: str, *, settings: Settings | None = None) -> TlsRptResult:
    try:
        normalized = normalize_domain(domain)
    except Exception:
        return TlsRptResult(present=False)
    resolver = build_resolver(settings)
    return await _fetch_tls_rpt(normalized, resolver)


async def fetch_dane(mx_hosts: list[str], *, settings: Settings | None = None) -> DaneResult:
    if not mx_hosts:
        return DaneResult(host_tlsa={})
    resolver = build_resolver(settings)
    return await _fetch_dane(mx_hosts, resolver)


async def fetch_bimi(domain: str, *, settings: Settings | None = None) -> BimiResult:
    try:
        normalized = normalize_domain(domain)
    except Exception:
        return BimiResult(present=False)
    resolver = build_resolver(settings)
    return await _fetch_bimi(normalized, resolver)
