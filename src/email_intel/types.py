"""Типы email-intel подсистемы (TASK-0016, ADR 036).

Парсенные email/policy записи — ``EmailIntelResult``. Любая ошибка
DNS-резолва / парсинга — ``EmailIntelError`` с категорией ``error_type``.
Эти типы — единственный контракт между клиентом (``client.fetch_email_intel``)
и тасками.

Результаты:
- MX: список host+priority
- SPF: сырая запись + режим (all/softfail/neutral/...), флаг множественности
- DMARC: policy, subpolicy (sp), pct
- DKIM: список найденных селекторов

Все домены — punycode (нормализация на входе, см. src/utils/idn.py).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

# Категории ошибок DNS-резолва.
EmailIntelErrorType = Literal[
    "nxdomain",
    "dns_unreachable",  # TASK-0079: реальный DNS-сбой (timeout/NoNameservers/...) ≠ «записей нет»
    "timeout",
    "dns_error",
    "parser_error",
    "internal_error",
]

# Режимы SPF (по значению после -all/~all/?all/+all).
SPFMode = Literal[
    "fail",  # -all
    "softfail",  # ~all
    "neutral",  # ?all
    "pass",  # +all
    "none",  # нет записи или без all
    "permerror",
    "temperror",
]

# DMARC policy.
DMARCPolicy = Literal[
    "none",
    "quarantine",
    "reject",
]


@dataclass(slots=True, kw_only=True, frozen=True)
class MXRecord:
    """MX-запись."""

    host: str
    priority: int


@dataclass(slots=True, kw_only=True, frozen=True)
class SPFRecord:
    """SPF-запись.

    Режим определяется по механизму *all:
    - ``-all`` → fail (строгий)
    - ``~all`` → softfail (мягкий)
    - ``?all`` → neutral (нейтральный)
    - ``+all`` → pass (разрешить все — небезопасно)
    - нет all-механизма → none
    """

    raw: str  # Сырая запись
    mode: SPFMode
    is_multiple: bool  # True если >1 SPF-записи (RFC-нарушение)


@dataclass(slots=True, kw_only=True, frozen=True)
class DMARCRecord:
    """DMARC-запись."""

    policy: DMARCPolicy  # p=
    subpolicy: DMARCPolicy | None = None  # sp= (если есть)
    pct: int | None = None  # pct= (NULL = 100%)


@dataclass(slots=True, kw_only=True, frozen=True)
class DKIMInfo:
    """Информация о DKIM (ADSEC-поддержка).

    Содержит список найденных селекторов из предопределённого набора:
    default, google, selector1, selector2, k1, mail.
    """

    selectors: list[str]  # Найденные селекторы


@dataclass(slots=True, kw_only=True)
class EmailIntelResult:
    """Полный результат сбора email-intel для домена."""

    domain: str
    is_reachable: bool  # True если DNS-резолв успешен

    mx_records: list[MXRecord] = field(default_factory=list)
    spf: SPFRecord | None = None
    dmarc: DMARCRecord | None = None
    dkim: DKIMInfo | None = None


@dataclass(slots=True, kw_only=True)
class EmailIntelError:
    """Описание неудачной попытки сбора email-intel."""

    domain: str
    error_type: EmailIntelErrorType
    message: str


EmailIntelResultOrError = EmailIntelResult | EmailIntelError


__all__ = [
    "MXRecord",
    "SPFRecord",
    "SPFMode",
    "DMARCRecord",
    "DMARCPolicy",
    "DKIMInfo",
    "EmailIntelResult",
    "EmailIntelError",
    "EmailIntelErrorType",
    "EmailIntelResultOrError",
]
