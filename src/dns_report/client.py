"""Расширенный DNS-обход домена для профессионального отчёта (ADR 044).

On-demand инструмент (кнопка «🧾 DNS-отчёт» в карточке /whois). Резолвит
широкий набор типов записей, обратные PTR для A/AAAA, признак DNSSEC и —
как security-проба — пытается AXFR (трансфер зоны) у NS-серверов.

Принципы (как в email_intel/dns_monitor):
- async везде, общий ``build_resolver`` (timeout/lifetime, override NS).
- Никогда не бросает наружу: сбои отдельных типов → ``errors``; полный
  провал → ``DnsReportError``.
- TXT извлекается через ``txt_to_str`` (урок TASK-0089 — у TXT-rdata нет
  ``to_unicode``).
- DNS-запрос идёт на ИСХОДНОЕ имя (поддомен), не на registrable (ADR 035).
"""

from __future__ import annotations

import asyncio
import logging

import dns.asyncquery
import dns.asyncresolver
import dns.exception
import dns.name
import dns.rdatatype
import dns.resolver
import dns.reversename
import dns.zone

from src.dns_report.types import DnsRecord, DnsReportError, DnsReportResult
from src.email_intel.resolver import build_resolver, classify_dns_exc
from src.email_intel.txt import txt_to_str
from src.utils.idn import from_punycode, normalize_domain

logger = logging.getLogger(__name__)

# Прямые типы, которые тянем у самого домена. SOA/NS/DNSKEY/DS обрабатываем
# отдельно (нужны для DNSSEC/AXFR), остальные — единообразно.
FORWARD_TYPES = ("SOA", "NS", "A", "AAAA", "CNAME", "MX", "TXT", "SRV", "CAA")

AXFR_TIMEOUT = 6.0  # на один NS; короче общего, трансфер обычно либо сразу, либо REFUSED
MAX_PTR = 16  # ограничиваем reverse-резолвы, чтобы не раздуть отчёт/время


def _rdata_to_str(rtype: str, rdata: object) -> str:
    """Человекочитаемое значение rdata; TXT — через txt_to_str (TASK-0089)."""
    if rtype == "TXT":
        return txt_to_str(rdata)
    return str(rdata.to_text())  # type: ignore[attr-defined]


async def _resolve_type(
    resolver: dns.asyncresolver.Resolver,
    domain: str,
    rtype: str,
    result: DnsReportResult,
) -> None:
    """Резолв одного типа; наполняет ``result.records`` или ``result.errors``."""
    try:
        answer = await resolver.resolve(domain, rtype, lifetime=resolver.lifetime)
    except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN):
        return  # нет записей этого типа — норма, не ошибка
    except dns.exception.DNSException as exc:
        kind = classify_dns_exc(exc)
        if kind != "no_records":
            result.errors[rtype] = str(exc) or kind
        return
    except Exception as exc:  # defense-in-depth
        result.errors[rtype] = f"unexpected: {exc}"
        return

    ttl = getattr(answer.rrset, "ttl", None) if answer.rrset is not None else None
    for rdata in answer:
        result.records.append(
            DnsRecord(rtype=rtype, name=domain, value=_rdata_to_str(rtype, rdata), ttl=ttl)
        )


async def _resolve_ptr(resolver: dns.asyncresolver.Resolver, result: DnsReportResult) -> None:
    """Обратные PTR для уже найденных A/AAAA (ограничено ``MAX_PTR``)."""
    ips = [r.value for r in result.records if r.rtype in ("A", "AAAA")][:MAX_PTR]
    for ip in ips:
        try:
            rev = dns.reversename.from_address(ip)
            answer = await resolver.resolve(rev, "PTR", lifetime=resolver.lifetime)
            for rdata in answer:
                result.records.append(
                    DnsRecord(rtype="PTR", name=ip, value=str(rdata.to_text()).rstrip("."))
                )
        except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN):
            continue
        except Exception:
            continue  # PTR опционален — молча пропускаем


async def _try_axfr(
    resolver: dns.asyncresolver.Resolver, domain: str, result: DnsReportResult
) -> None:
    """Security-проба: пытаемся AXFR у каждого NS. Открытый трансфер = finding."""
    ns_hosts = [r.value.rstrip(".") for r in result.records if r.rtype == "NS"]
    if not ns_hosts:
        result.axfr_open = None
        return
    zone_name = dns.name.from_text(domain)
    for ns in ns_hosts:
        try:
            ns_answer = await resolver.resolve(ns, "A", lifetime=resolver.lifetime)
            ns_ip = str(next(iter(ns_answer)).to_text())
        except Exception:
            continue
        try:
            xfr = await dns.asyncquery.xfr(  # type: ignore[attr-defined]
                ns_ip, zone_name, timeout=AXFR_TIMEOUT, lifetime=AXFR_TIMEOUT
            )
            z = await dns.zone.async_from_xfr(xfr)  # type: ignore[attr-defined]
            count = sum(1 for _ in z.iterate_rdatasets())
            result.axfr_open = True
            result.axfr_detail = f"{ns} ({ns_ip}) → зона передана, {count} rrset"
            return  # один открытый NS достаточен
        except Exception:
            continue
    # ни один NS не отдал зону → трансфер закрыт (как и должно быть)
    result.axfr_open = False


async def fetch_dns_report(
    domain: str, *, with_axfr: bool = True
) -> DnsReportResult | DnsReportError:
    """Собрать расширенный DNS-отчёт по домену.

    :param with_axfr: пробовать ли AXFR (security-проба). Можно отключить
        в тестах/ограниченных средах.
    """
    try:
        normalized = normalize_domain(domain)
    except Exception:
        return DnsReportError(domain=domain, error_type="invalid_domain", message="invalid domain")

    resolver = build_resolver()
    result = DnsReportResult(
        domain=normalized,
        unicode_domain=from_punycode(normalized),
        resolver_used=", ".join(resolver.nameservers) if resolver.nameservers else "system",
    )

    # Прямые типы — параллельно (каждый сам ловит свои ошибки)
    await asyncio.gather(*(_resolve_type(resolver, normalized, rt, result) for rt in FORWARD_TYPES))

    # DNSSEC: наличие DNSKEY/DS
    for sec_type in ("DNSKEY", "DS"):
        await _resolve_type(resolver, normalized, sec_type, result)
    result.dnssec = any(r.rtype in ("DNSKEY", "DS") for r in result.records)

    # Полный провал: ни одной записи и есть unreachable-ошибки → фатально
    if result.is_empty and result.errors:
        return DnsReportError(
            domain=normalized,
            error_type="unreachable",
            message="; ".join(f"{k}: {v}" for k, v in result.errors.items())[:300],
        )

    await _resolve_ptr(resolver, result)
    if with_axfr:
        await _try_axfr(resolver, normalized, result)

    return result


__all__ = ["FORWARD_TYPES", "fetch_dns_report"]
