"""Async DNS resolver через dnspython (Этап 14, ADR 032).

По образцу ``src/ssl/client.py`` — never raises, всегда возвращает
``DNSResult``. Цепочка резолверов: пробует первый из
``settings.dns_resolvers``, при ошибке (timeout / SERVFAIL /
NoNameservers) переходит к следующему. NXDOMAIN и invalid_domain —
финальные, по цепочке не идём.
"""

from __future__ import annotations

import logging
from typing import Final

import dns.asyncresolver
import dns.exception
import dns.resolver
import idna

from src.config.settings import get_settings
from src.dns_monitor.types import DNSError, DNSRecords, DNSResult
from src.utils.idn import to_punycode

logger = logging.getLogger(__name__)

# Сколько раз dnspython retry-ит на одном резолвере перед exception
RESOLVER_TRIES: Final = 2

# Какие record-типы запрашиваем. NS — для mismatch-detection
# с WHOIS-NS (critical security signal). MX — для resolution_state
# (mx_only детект); сами MX-записи не сохраняем в кэше.
RECORD_TYPES: Final = ("A", "AAAA", "NS", "MX")


async def resolve_records(domain: str) -> DNSResult:
    """Резолвит DNS-записи домена. Никогда не raise.

    Возвращает ``DNSRecords`` при успехе или ``DNSError`` при сбое.
    Цепочка резолверов: пробует первый из ``settings.dns_resolvers``,
    при ошибке (timeout / SERVFAIL / NoNameservers) переходит к
    следующему. NXDOMAIN / invalid_domain — финальные.

    NB: даже при ``resolution_state="no_dns"`` возвращает ``DNSRecords``
    (домен существует, просто пустой). ``DNSError`` — только при
    реальных сбоях (timeout / network / NXDOMAIN).
    """
    settings = get_settings()

    if not settings.dns_enabled:
        return DNSError(
            domain=domain,
            error_type="disabled",
            message="DNS_ENABLED=false (kill-switch active)",
        )

    # IDN нормализация — те же исключения что в ssl/client.py
    try:
        normalized = to_punycode(domain)
    except (idna.IDNAError, ValueError, UnicodeError) as exc:
        return DNSError(
            domain=domain,
            error_type="invalid_domain",
            message=f"IDN normalization failed: {exc}",
        )

    if not settings.dns_resolvers:
        return DNSError(
            domain=normalized,
            error_type="resolver_unreachable",
            message="no resolvers configured in DNS_RESOLVERS",
        )

    # Цепочка резолверов
    last_error: DNSError | None = None
    for resolver_addr in settings.dns_resolvers:
        result = await _try_resolver(normalized, resolver_addr)
        if isinstance(result, DNSRecords):
            return result
        last_error = result
        # NXDOMAIN / invalid_domain — финальные, не пробуем дальше
        if result.error_type in ("invalid_domain", "nxdomain"):
            return result

    # Если ни один резолвер не ответил — возвращаем последнюю ошибку
    assert last_error is not None  # invariant: цикл выполнился ≥ 1 раз
    return last_error


async def _try_resolver(domain: str, resolver_addr: str) -> DNSResult:
    """Один проход через конкретный резолвер.

    Возвращает ``DNSRecords`` если хоть что-то нашли (включая no_dns
    при отсутствии записей, но без сетевых ошибок), ``DNSError`` —
    при catastrophic failure (NXDOMAIN, all timeouts, all SERVFAIL).
    """
    settings = get_settings()

    resolver = dns.asyncresolver.Resolver(configure=False)
    resolver.nameservers = [resolver_addr]
    resolver.timeout = settings.dns_timeout_seconds
    resolver.lifetime = settings.dns_timeout_seconds * RESOLVER_TRIES

    records: dict[str, list[str]] = {rt: [] for rt in RECORD_TYPES}
    nxdomain = False
    timeout_seen = False
    servfail_seen = False

    for rtype in RECORD_TYPES:
        try:
            answer = await resolver.resolve(domain, rtype, raise_on_no_answer=False)
            if answer.rrset is not None:
                # str(rdata) даёт каноничное представление
                # (без trailing dot для A/AAAA, с trailing dot
                # для NS — нормализуем на стороне diff)
                records[rtype] = sorted(str(r) for r in answer)
        except dns.resolver.NXDOMAIN:
            # NXDOMAIN для одного типа = для всех типов на этом резолвере
            nxdomain = True
            break
        except dns.resolver.NoAnswer:
            # Этого типа записей нет — нормально, продолжаем
            pass
        except dns.exception.Timeout:
            timeout_seen = True
            continue
        except dns.resolver.NoNameservers:
            # SERVFAIL или все NS отказали
            servfail_seen = True
            continue
        except dns.exception.DNSException as exc:
            # Catch-all для редких dnspython exceptions
            logger.warning(
                "dns_client.unexpected domain=%s rtype=%s resolver=%s error=%s",
                domain,
                rtype,
                resolver_addr,
                exc,
            )
            continue

    if nxdomain:
        return DNSError(
            domain=domain,
            error_type="nxdomain",
            message=f"NXDOMAIN at {resolver_addr}",
        )

    has_any_record = any(records[rt] for rt in RECORD_TYPES)

    if not has_any_record:
        # Ни одного типа записей не получили — это либо все
        # timeout/servfail (real failure), либо домен реально
        # пустой (no_dns)
        if timeout_seen:
            return DNSError(
                domain=domain,
                error_type="timeout",
                message=f"all queries timed out at {resolver_addr}",
            )
        if servfail_seen:
            return DNSError(
                domain=domain,
                error_type="servfail",
                message=f"all queries SERVFAIL at {resolver_addr}",
            )
        # Домен существует, но нет ни одного типа записей
        return DNSRecords(
            domain=domain,
            is_reachable=True,
            resolution_state="no_dns",
            resolver_used=resolver_addr,
        )

    # Есть хотя бы что-то. Определяем resolution_state по A/AAAA.
    has_addr_record = bool(records["A"]) or bool(records["AAAA"])

    return DNSRecords(
        domain=domain,
        is_reachable=True,
        a_records=records["A"],
        aaaa_records=records["AAAA"],
        ns_records=records["NS"],
        resolution_state="resolved" if has_addr_record else "mx_only",
        resolver_used=resolver_addr,
    )


__all__ = ["RECORD_TYPES", "RESOLVER_TRIES", "resolve_records"]
