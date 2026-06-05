"""Async DNS-клиент для сбора email/policy записей (TASK-0016, ADR 036).

Резолв MX, SPF (apex TXT), DMARC (_dmarc.<domain> TXT), DKIM-селекторы
(набор предопределённых selector._domainkey.<domain> TXT).

Использует dnspython async resolver. Все исключения превращаются в
``EmailIntelError`` — caller не обрабатывает сетевую кухню.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import dns.asyncresolver  # type annotations only (postponed via __future__.annotations)
import dns.exception
import dns.resolver  # for NXDOMAIN/NoAnswer in _is_nxdomain_like and classify

from src.config.settings import Settings
from src.email_intel.parser import (
    DKIM_SELECTORS,
    parse_dkim_selectors,
    parse_dmarc,
    parse_mx_records,
    parse_spf,
)
from src.email_intel.resolver import (
    QUERY_TIMEOUT,
    TOTAL_TIMEOUT,
    build_resolver,
    classify_dns_exc,
)
from src.email_intel.txt import txt_to_str
from src.email_intel.types import (
    DKIMInfo,
    DMARCRecord,
    EmailIntelError,
    EmailIntelResult,
    EmailIntelResultOrError,
    SPFRecord,
)
from src.utils.idn import normalize_domain

logger = logging.getLogger(__name__)


async def fetch_email_intel(
    domain: str, *, settings: Settings | None = None
) -> EmailIntelResultOrError:
    """Собирает все email/policy записи для домена.

    Резолвит:
    - MX-записи
    - TXT (apex) для SPF
    - TXT _dmarc.<domain> для DMARC
    - TXT <selector>._domainkey.<domain> для DKIM

    Args:
        domain: Домен (может быть IDN, будет нормализован в punycode)
        settings: Опционально — настройки (для dns_nameservers override).
                  Если None — build_resolver использует get_settings() fallback.

    Returns:
        EmailIntelResult при успехе, EmailIntelError при ошибке
    """
    try:
        normalized = normalize_domain(domain)
    except Exception as exc:
        return EmailIntelError(
            domain=domain,
            error_type="parser_error",
            message=f"Invalid domain syntax: {exc}",
        )

    resolver = build_resolver(settings)

    try:
        # Параллельный резолв всех типов записей
        results = await asyncio.gather(
            _resolve_mx(resolver, normalized),
            _resolve_txt(resolver, normalized),
            _resolve_dmarc(resolver, normalized),
            _resolve_dkim(resolver, normalized),
            return_exceptions=True,
        )
        mx_answers, txt_answers, dmarc_txt, dkim_selectors = results

        # Проверяем на критические ошибки
        if isinstance(dmarc_txt, Exception) and _is_nxdomain_like(dmarc_txt):
            # NXDOMAIN на DMARC не критичен (может не быть DMARC)
            dmarc_txt = None
        elif isinstance(dmarc_txt, Exception):
            dmarc_txt = None

        # DKIM-селекторы: если ошибка — пустой результат
        if isinstance(dkim_selectors, Exception):
            dkim_selectors = {}

        # MX-ошибка: NXDOMAIN → nxdomain error; NoAnswer/отсутствие → пустой MX (ok);
        # любой другой DNS-сбой (timeout/NoNameservers/...) → dns_unreachable (НЕ ложное «MX нет»)
        mx_records: list[Any] = []
        if isinstance(mx_answers, Exception):
            if _is_nxdomain_like(mx_answers):
                return EmailIntelError(
                    domain=normalized,
                    error_type="nxdomain",
                    message=f"Domain does not exist: {mx_answers}",
                )
            cls = classify_dns_exc(mx_answers)
            if cls == "no_records":
                # Легитимное «MX-записей нет» (NoAnswer) — валидно, пустой список
                logger.debug("MX no_records (NoAnswer) for %s", normalized)
            else:
                logger.warning(
                    "email_intel MX dns_unreachable for %s: %s (type=%s)",
                    normalized,
                    mx_answers,
                    type(mx_answers).__name__,
                )
                return EmailIntelError(
                    domain=normalized,
                    error_type="dns_unreachable",
                    message=f"DNS unreachable resolving MX: {mx_answers}",
                )
        else:
            mx_records = parse_mx_records(list(mx_answers))  # type: ignore

        # TXT для SPF
        spf_record: SPFRecord | None = None
        if isinstance(txt_answers, Exception):
            if classify_dns_exc(txt_answers) == "unreachable":
                logger.warning(
                    "email_intel TXT dns_unreachable for %s: %s", normalized, txt_answers
                )
            # TXT error — не критично, нет SPF (даже при сбое; graceful)
            txt_records = []
        else:
            txt_records = [txt_to_str(r) for r in list(txt_answers)]
            spf_record = parse_spf(txt_records)

        # DMARC
        dmarc_record: DMARCRecord | None = None
        if dmarc_txt is not None and not isinstance(dmarc_txt, Exception):
            dmarc_record = parse_dmarc(dmarc_txt)  # type: ignore

        # DKIM
        dkim_info: DKIMInfo = parse_dkim_selectors(dkim_selectors)  # type: ignore

        return EmailIntelResult(
            domain=normalized,
            is_reachable=True,
            mx_records=mx_records,
            spf=spf_record,
            dmarc=dmarc_record,
            dkim=dkim_info,
        )
    except Exception as exc:
        logger.warning("email_intel unexpected error for %s: %s", normalized, exc)
        return EmailIntelError(
            domain=normalized,
            error_type="internal_error",
            message=f"Unexpected error: {exc}",
        )


async def _resolve_mx(
    resolver: dns.asyncresolver.Resolver,
    domain: str,
) -> Any:
    """Резолв MX-записей."""
    try:
        answer = await resolver.resolve(domain, "MX", lifetime=TOTAL_TIMEOUT)
        return list(answer)
    except dns.exception.DNSException as exc:
        return exc
    except Exception as exc:
        return exc


async def _resolve_txt(
    resolver: dns.asyncresolver.Resolver,
    domain: str,
) -> Any:
    """Резолв TXT-записей (apex) для SPF."""
    try:
        answer = await resolver.resolve(domain, "TXT", lifetime=TOTAL_TIMEOUT)
        return list(answer)
    except dns.exception.DNSException as exc:
        return exc
    except Exception as exc:
        return exc


async def _resolve_dmarc(
    resolver: dns.asyncresolver.Resolver,
    domain: str,
) -> Any:
    """Резолв DMARC (_dmarc.<domain> TXT)."""
    dmarc_domain = f"_dmarc.{domain}"
    try:
        answer = await resolver.resolve(dmarc_domain, "TXT", lifetime=TOTAL_TIMEOUT)
        if answer:
            return txt_to_str(answer[0])
        return None
    except dns.exception.DNSException as exc:
        return exc
    except Exception as exc:
        return exc


async def _resolve_dkim(
    resolver: dns.asyncresolver.Resolver,
    domain: str,
) -> dict[str, str]:
    """Резолв DKIM-селекторов (selector._domainkey.<domain> TXT).

    Проверяет предопределённый набор селекторов и возвращает найденные.
    """
    results: dict[str, str] = {}

    # Параллельный резолв всех селекторов
    tasks = []
    for selector in DKIM_SELECTORS:
        task = _resolve_dkim_selector(resolver, domain, selector)
        tasks.append(task)

    dkim_results = await asyncio.gather(*tasks, return_exceptions=True)

    for selector, result in zip(DKIM_SELECTORS, dkim_results, strict=False):
        if isinstance(result, str):
            results[selector] = result

    return results


async def _resolve_dkim_selector(
    resolver: dns.asyncresolver.Resolver,
    domain: str,
    selector: str,
) -> Any:
    """Резолв одного DKIM-селектора."""
    dkim_domain = f"{selector}._domainkey.{domain}"
    try:
        answer = await resolver.resolve(dkim_domain, "TXT", lifetime=TOTAL_TIMEOUT)
        if answer:
            return txt_to_str(answer[0])
        return ""
    except dns.exception.DNSException:
        # Нет DKIM-записи — нормально
        return ""
    except Exception as exc:
        return exc


def _is_nxdomain_like(exc: Exception) -> bool:
    """Проверка, является ли исключение NXDOMAIN-подобным."""
    if isinstance(exc, dns.resolver.NXDOMAIN):
        return True
    msg = str(exc).lower()
    return "nxdomain" in msg


__all__ = [
    "QUERY_TIMEOUT",
    "TOTAL_TIMEOUT",
    "fetch_email_intel",
]
