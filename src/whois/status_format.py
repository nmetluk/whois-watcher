"""Локализация WHOIS-статусов и сортировка по severity (Этап 8).

Сырые статусы из ``WhoisData.status`` — это EPP-коды (``clientTransferProhibited``,
``pendingDelete``) или regional-варианты вроде ``REGISTERED`` (TCINET),
``connect`` (DENIC), ``ACTIVE`` (AFNIC). Карточка ``/whois`` показывает
их в виде человекочитаемых строк с эмодзи, поэтому маппинг код → текст
+ severity вынесен в локали (``src.locales.ru/en.WHOIS_STATUSES``).

Этот модуль:

- знает структуру таблицы локалей и берёт её по языку
- умеет fallback'ить незнакомый код (camelCase split → «Client hold»)
- сортирует по severity (critical → warning → info → normal), что
  нужно карточке: «опасные сверху»
- подставляет эмодзи по severity, если в локали нет override

Чистый модуль без I/O — удобно тестировать на синтетических входах.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from src.locales.en import WHOIS_STATUSES as EN_STATUSES
from src.locales.ru import WHOIS_STATUSES as RU_STATUSES
from src.locales.ru import StatusSeverity

# Эмодзи по умолчанию для каждой severity, если в таблице локалей
# нет ``emoji_override``.
DEFAULT_EMOJI: dict[StatusSeverity, str] = {
    "normal": "🟢",
    "info": "🔒",
    "warning": "⚠️",
    "critical": "🚨",
}

# Порядок сортировки: меньше → раньше в выводе.
_SEVERITY_RANK: dict[StatusSeverity, int] = {
    "critical": 0,
    "warning": 1,
    "info": 2,
    "normal": 3,
}

# Тривиальные статусы, которые скрываются если есть хотя бы один не-normal:
# дублировать «Активен» рядом с «Скоро будет удалён» — информационный шум.
TRIVIAL_STATUSES: frozenset[str] = frozenset({"ok", "active", "ACTIVE", "REGISTERED", "DELEGATED"})


@dataclass(slots=True, kw_only=True)
class FormattedStatus:
    """Один отформатированный статус для UI.

    ``raw_code`` — исходное значение из ``WhoisData.status`` (для копирования
    юзером, debug-целей и сравнения). ``text`` — локализованный текст.
    ``emoji`` — либо override из таблицы, либо дефолт по severity.
    ``severity`` — для подсветки или сортировки на UI-стороне.
    """

    raw_code: str
    text: str
    emoji: str
    severity: StatusSeverity
    is_known: bool  # False — если код не найден в локали (использован fallback)


def format_statuses(
    raw_statuses: list[str],
    *,
    lang: Literal["ru", "en"] = "ru",
    drop_trivial_when_others_present: bool = True,
) -> list[FormattedStatus]:
    """Превращает сырые WHOIS-статусы в ``FormattedStatus``.

    :param raw_statuses: значения из ``WhoisData.status`` — например
        ``["ok", "clientTransferProhibited", "pendingDelete"]``.
    :param lang: язык карточки. Незнакомый язык → ``"ru"`` (тот же fallback,
        что и в ``src.locales.t``).
    :param drop_trivial_when_others_present: если ``True`` и есть хотя бы
        один не-normal статус, ``ok`` / ``active`` / ``REGISTERED``
        (``TRIVIAL_STATUSES``) выкидываются. Иначе показываются всегда.

    Возвращает список, отсортированный critical → warning → info → normal.
    Дубликаты (один и тот же код встречается несколько раз) схлопываются:
    Verisign иногда дублирует ``Domain Status:`` в thick-WHOIS-ответе.
    """
    table = RU_STATUSES if lang != "en" else EN_STATUSES

    seen: set[str] = set()
    formatted: list[FormattedStatus] = []
    for code in raw_statuses:
        normalized = code.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        formatted.append(_format_one(normalized, table))

    has_non_normal = any(item.severity != "normal" for item in formatted)
    if drop_trivial_when_others_present and has_non_normal:
        formatted = [item for item in formatted if item.raw_code not in TRIVIAL_STATUSES]

    formatted.sort(key=lambda x: (_SEVERITY_RANK[x.severity], x.raw_code))
    return formatted


def _format_one(
    code: str,
    table: dict[str, tuple[StatusSeverity, str, str | None]],
) -> FormattedStatus:
    """Один статус: lookup в таблице → fallback на camelCase split."""
    entry = table.get(code)
    if entry is not None:
        severity, text, emoji_override = entry
        emoji = emoji_override or DEFAULT_EMOJI[severity]
        return FormattedStatus(
            raw_code=code, text=text, emoji=emoji, severity=severity, is_known=True
        )

    # Fallback: camelCase → "Camel case". Для UPPER_SNAKE → нижний регистр +
    # title через split('_'). Для всего остального — оставляем как есть.
    fallback_text = _humanize_code(code)
    fallback_severity: StatusSeverity = "info"
    fallback_emoji = DEFAULT_EMOJI[fallback_severity]
    return FormattedStatus(
        raw_code=code,
        text=fallback_text,
        emoji=fallback_emoji,
        severity=fallback_severity,
        is_known=False,
    )


_CAMEL_SPLIT_RE = re.compile(r"(?<!^)(?=[A-Z])")


def _humanize_code(code: str) -> str:
    """``clientHold`` → ``Client hold``; ``NOT_DELEGATED`` → ``Not delegated``."""
    if "_" in code or " " in code:
        # UPPER_SNAKE_CASE или ALREADY SPACED — нормализуем регистр.
        parts = re.split(r"[_\s]+", code.strip())
        words = [p.lower() for p in parts if p]
        if not words:
            return code
        return " ".join(words).capitalize()
    # camelCase / PascalCase
    spaced = _CAMEL_SPLIT_RE.sub(" ", code).lower()
    return spaced.capitalize() if spaced else code


__all__ = [
    "DEFAULT_EMOJI",
    "FormattedStatus",
    "TRIVIAL_STATUSES",
    "format_statuses",
]
