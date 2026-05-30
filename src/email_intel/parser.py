"""Парсеры email/policy записей (TASK-0016, ADR 036).

Чистые функции для разбора DNS-ответов:
- MX-записи → список MXRecord
- TXT-записи → SPFRecord / DMARCRecord
- DKIM-селекторы → DKIMInfo

Все функции возвращают данные или None при отсутствии записи.
"""

from __future__ import annotations

import re
from typing import Any

from src.email_intel.types import (
    DKIMInfo,
    DMARCPolicy,
    DMARCRecord,
    MXRecord,
    SPFMode,
    SPFRecord,
)

# Предопределённый набор DKIM-селекторов для проверки (ADSEC-поддержка)
DKIM_SELECTORS = [
    "default",
    "google",
    "selector1",
    "selector2",
    "k1",
    "mail",
]


def parse_mx_records(mx_answers: list[Any]) -> list[MXRecord]:
    """Разбор MX-записей из DNS-ответа.

    Args:
        mx_answers: Список ответов dnspython MX query

    Returns:
        Список MXRecord, отсортированный по priority (ascending)
    """
    records = []
    for ans in mx_answers:
        # dnspython: ans.exchange и ans.preference
        if hasattr(ans, "exchange") and hasattr(ans, "preference"):
            records.append(
                MXRecord(
                    host=ans.exchange.to_unicode().strip(".").lower(),
                    priority=ans.preference,
                )
            )
    return sorted(records, key=lambda r: r.priority)


def parse_spf(txt_records: list[str]) -> SPFRecord | None:
    """Разбор SPF-записи из TXT-записей.

    Args:
        txt_records: Список строк TXT-записей домена

    Returns:
        SPFRecord или None если нет SPF

    Note:
        Не выполняет рекурсию по include (только базовый разбор).
        Если несколько SPF-записей — is_multiple=True.
    """
    spf_candidates = []
    for txt in txt_records:
        txt = txt.strip()
        if txt.startswith("v=spf1 "):
            spf_candidates.append(txt)

    if not spf_candidates:
        return None

    # Берём первую найденную (RFC запрещает >1, но мы помечаем)
    raw = spf_candidates[0]
    is_multiple = len(spf_candidates) > 1

    # Определяем режим по механизму *all
    mode = _extract_spf_mode(raw)

    return SPFRecord(
        raw=raw,
        mode=mode,
        is_multiple=is_multiple,
    )


def _extract_spf_mode(spf_record: str) -> SPFMode:
    """Извлечение режима из SPF-записи по механизму *all.

    Приоритет: -all > ~all > ?all > +all
    Если нет all-механизма → none
    """
    # Ищем механизмы в обратном порядке приоритета
    if "-all" in spf_record:
        return "fail"
    if "~all" in spf_record:
        return "softfail"
    if "?all" in spf_record:
        return "neutral"
    if "+all" in spf_record:
        return "pass"

    # Если есть v=spf1 но нет all — считаем none
    if "v=spf1" in spf_record:
        return "none"

    # fallback (не должно дойти)
    return "none"


def parse_dmarc(dmarc_txt: str | None) -> DMARCRecord | None:
    """Разбор DMARC-записи из TXT.

    Args:
        dmarc_txt: Содержимое TXT-записи _dmarc.<domain> или None

    Returns:
        DMARCRecord или None если нет DMARC

    Note:
        Парсит только базовые теги: p=, sp=, pct=
        Если p= отсутствует — возвращает None
    """
    if not dmarc_txt:
        return None

    dmarc_txt = dmarc_txt.strip()

    # DMARC начинается с v=DMARC1
    if not dmarc_txt.startswith("v=DMARC1"):
        return None

    # Извлекаем теги
    policy: DMARCPolicy | None = None
    subpolicy: DMARCPolicy | None = None
    pct: int | None = None

    # Парсим p= (обязательный)
    p_match = re.search(r"\bp=(none|quarantine|reject)\b", dmarc_txt, re.IGNORECASE)
    if p_match:
        policy = p_match.group(1).lower()  # type: ignore
    else:
        return None  # p= обязателен

    # Парсим sp= (опциональный)
    sp_match = re.search(r"\bsp=(none|quarantine|reject)\b", dmarc_txt, re.IGNORECASE)
    if sp_match:
        subpolicy = sp_match.group(1).lower()  # type: ignore

    # Парсим pct= (опциональный)
    pct_match = re.search(r"\bpct=(\d+)\b", dmarc_txt)
    if pct_match:
        try:
            pct_val = int(pct_match.group(1))
            if 0 <= pct_val <= 100:
                pct = pct_val
        except ValueError:
            pass

    return DMARCRecord(
        policy=policy,  # type: ignore
        subpolicy=subpolicy,
        pct=pct,
    )


def parse_dkim_selectors(
    dkim_txt_records: dict[str, str],
) -> DKIMInfo:
    """Разбор DKIM-селекторов из TXT-записей.

    Args:
        dkim_txt_records: Словарь {selector: txt_content} для проверенных селекторов

    Returns:
        DKIMInfo с списком найденных селекторов
    """
    found_selectors = []
    for selector, txt_content in dkim_txt_records.items():
        # DKIM TXT-запись содержит p= (public key)
        if txt_content and "p=" in txt_content:
            found_selectors.append(selector)

    return DKIMInfo(selectors=sorted(found_selectors))


__all__ = [
    "parse_mx_records",
    "parse_spf",
    "parse_dmarc",
    "parse_dkim_selectors",
    "DKIM_SELECTORS",
]
