"""Чистые парсеры deep email политик (TASK-0038, ADR 040).

MTA-STS policy, TLS-RPT, BIMI. Не содержат сетевого кода — только разбор строк.
Отсутствие записи — валидное состояние (не ошибка).
"""

from __future__ import annotations

import re
from typing import Literal

from src.email_intel.deep_types import (
    BimiResult,
    MtaStsResult,
    TlsRptResult,
)


def parse_mta_sts_policy(policy_text: str | None) -> MtaStsResult:
    """Парсит содержимое policy-файла MTA-STS (mta-sts.txt).

    Формат (RFC 8461):
        version: STSv1
        mode: enforce | testing | none
        mx: host-or-wildcard
        max_age: seconds

    Args:
        policy_text: Тело ответа или None (файл недоступен/пустой).

    Returns:
        MtaStsResult с parsed полями. Если policy_text None/пустой или
        нет version — возвращает txt_present=False, reachable=False.
        Парсер tolerant: lower-case, игнорирует неизвестные строки.
    """
    if not policy_text or not policy_text.strip():
        return MtaStsResult(txt_present=False, reachable=False)

    text = policy_text.strip().lower()
    # Должна начинаться с version: stsv1 (или просто содержать)
    if "version:" not in text and "sts" not in text[:20]:
        # Не looks like MTA-STS policy
        return MtaStsResult(txt_present=False, reachable=False)

    mode: Literal["enforce", "testing", "none"] | None = None
    mx_list: list[str] = []
    max_age: int | None = None

    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip()
        if not val:
            continue

        if key == "mode":
            if val in ("enforce", "testing", "none"):
                mode = val  # type: ignore[assignment]
        elif key == "mx":
            # Сохраняем как есть (могут быть wildcards *.example.com)
            mx_list.append(val)
        elif key == "max_age":
            try:
                ma = int(val)
                if ma >= 0:
                    max_age = ma
            except ValueError:
                pass

    return MtaStsResult(
        txt_present=True,
        policy_mode=mode,
        mx=mx_list,
        max_age=max_age,
        reachable=True,  # caller решает; здесь если дошли до парса — reachable
    )


def parse_tls_rpt(txt_record: str | None) -> TlsRptResult:
    """Парсит TXT _smtp._tls.<domain> для TLS-RPT (RFC 8460).

    Пример: v=TLSRPTv1; rua=mailto:reports@example.com
    """
    if not txt_record:
        return TlsRptResult(present=False)

    txt = txt_record.strip()
    if not txt.lower().startswith("v=tlsrptv1"):
        return TlsRptResult(present=False)

    rua: str | None = None
    m = re.search(r"\brua=([^;\s]+)", txt, re.IGNORECASE)
    if m:
        rua = m.group(1).strip()

    return TlsRptResult(present=True, rua=rua)


def parse_bimi(txt_record: str | None) -> BimiResult:
    """Парсит TXT default._bimi.<domain> (BIMI, draft)."""
    if not txt_record:
        return BimiResult(present=False)

    txt = txt_record.strip()
    if not txt.lower().startswith("v=bimi1"):
        return BimiResult(present=False)

    logo_url: str | None = None
    vmc_url: str | None = None

    # l= logo
    m = re.search(r"\bl=([^;\s]+)", txt, re.IGNORECASE)
    if m:
        logo_url = m.group(1).strip()

    # a= VMC (optional)
    m = re.search(r"\ba=([^;\s]+)", txt, re.IGNORECASE)
    if m:
        vmc_url = m.group(1).strip()

    return BimiResult(present=True, logo_url=logo_url, vmc_url=vmc_url)


__all__ = [
    "parse_mta_sts_policy",
    "parse_tls_rpt",
    "parse_bimi",
]
