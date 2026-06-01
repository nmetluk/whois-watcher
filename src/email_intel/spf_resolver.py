"""Рекурсивный SPF-резолвер (TASK-0038, ADR 040).

Разворачивает include: и redirect= (RFC 7208), с защитой от циклов
и лимитом lookups (10). Чистая функция с инъекцией resolve_txt для тестов.

Источники (sources) — итоговые авторизующие механизмы после разворачивания
(без самих include/redirect).
"""

from __future__ import annotations

import logging
import re
from collections.abc import Awaitable, Callable

from src.email_intel.deep_types import SpfResolution
from src.utils.idn import normalize_domain, to_punycode

logger = logging.getLogger(__name__)

SPF_LOOKUP_LIMIT = 10

# Извлечение include: и redirect=
INCLUDE_RE = re.compile(r"(?i)\binclude:([^\s]+)")
REDIRECT_RE = re.compile(r"(?i)\bredirect=([^\s]+)")


def _extract_includes_and_redirect(spf_record: str) -> tuple[list[str], str | None]:
    """Извлекает цели include: и redirect= из SPF-записи."""
    includes: list[str] = []
    for m in INCLUDE_RE.finditer(spf_record):
        target = m.group(1).rstrip(".").lower()
        if target:
            includes.append(target)

    redirect: str | None = None
    redirect_match: re.Match[str] | None = REDIRECT_RE.search(spf_record)
    if redirect_match:
        target = redirect_match.group(1).rstrip(".").lower()
        if target:
            redirect = target

    return includes, redirect


def _is_spf_record(txt: str) -> bool:
    """Проверяет, является ли TXT v=spf1 записью."""
    return txt.strip().startswith("v=spf1 ")


def _normalize_spf_target(target: str) -> str:
    """Нормализация цели include/redirect.

    SPF-таргеты часто содержат leading underscore (_spf, _spf2) — idna.encode
    такие лейблы отвергает. Для SPF-целей достаточно lower + strip trailing dot.
    (DNS уже провалидировал, что имя существует.)
    """
    t = target.strip().lower().rstrip(".")
    if not t:
        raise ValueError("empty spf target")
    # Пробуем строгий путь; если падает на _ — возвращаем как есть (lower)
    try:
        return to_punycode(t)
    except Exception:
        return t


async def resolve_spf(
    domain: str,
    *,
    resolve_txt: Callable[[str], Awaitable[list[str] | None]],
    _visited: set[str] | None = None,
    _lookups: int = 0,
) -> SpfResolution:
    """Рекурсивно разворачивает SPF include/redirect.

    Args:
        domain: Домен для SPF (будет нормализован).
        resolve_txt: Инъектируемый резолвер TXT (для тестов и prod).
            Должен возвращать список строк TXT или None при отсутствии.
        _visited / _lookups: Внутренние для рекурсии (не передавать снаружи).

    Returns:
        SpfResolution с sources (терминальные механизмы), счётчиком lookups,
        флагом превышения лимита.

    Инварианты:
    - Циклы детектируются и прерываются (не зависаем).
    - >10 lookups → exceeds_limit=True (даже если частично собрали).
    - Нет SPF-записи → sources=[], lookup_count=1 (или 0?), exceeds=False.
    """
    # Для SPF-таргетов (включая _spf.*) idna может падать — используем relaxed
    try:
        normalized = normalize_domain(domain)
    except Exception:
        try:
            normalized = _normalize_spf_target(domain)
        except Exception:
            return SpfResolution(sources=[], lookup_count=0, exceeds_limit=False)

    visited = _visited or set()
    if normalized in visited:
        # Цикл — прерываем, не увеличиваем счётчик повторно
        return SpfResolution(sources=[], lookup_count=_lookups, exceeds_limit=False)

    visited = visited | {normalized}

    # Базовый "lookup" этого домена (TXT для SPF записи).
    # Корневой (и include/redirect target) fetch НЕ считается в лимите 10
    # (RFC 7208 §4.6.4: считаются только механизмы, вызывающие доп. DNS).
    # Инкремент только при переходе в include/redirect (см. рекурсивные вызовы).
    current_lookups = _lookups
    if current_lookups > SPF_LOOKUP_LIMIT:
        return SpfResolution(sources=[], lookup_count=current_lookups, exceeds_limit=True)

    try:
        txt_records = await resolve_txt(normalized) or []
    except Exception:
        # Ошибка резолва этого уровня — graceful, как будто нет SPF
        return SpfResolution(sources=[], lookup_count=current_lookups, exceeds_limit=False)

    spf_candidates = [t for t in txt_records if _is_spf_record(t)]
    if not spf_candidates:
        # Нет SPF на этом уровне — это не ошибка, просто нет источников
        return SpfResolution(sources=[], lookup_count=current_lookups, exceeds_limit=False)

    # RFC: >1 SPF — multiple, но мы берём первую (is_multiple не сохраняем в результат)
    raw = spf_candidates[0]

    includes, redirect = _extract_includes_and_redirect(raw)

    # Собираем терминальные источники из текущей записи (всё кроме include/redirect)
    # Простой подход: берём все токены, отфильтровываем include/redirect/exp/v= и пустые
    terminal: list[str] = []
    for token in raw.split():
        token = token.strip()
        if not token or token.startswith("v=spf1"):
            continue
        low = token.lower()
        if low.startswith("include:") or low.startswith("redirect=") or low.startswith("exp="):
            continue
        # all ( -all / ~all / ?all / +all ) — не источник, только модификатор результата (TASK-0048)
        if low in {"-all", "~all", "?all", "+all"}:
            continue
        terminal.append(token)

    sources: list[str] = list(terminal)
    exceeds = False

    # Рекурсия по include:
    for inc in includes:
        if current_lookups >= SPF_LOOKUP_LIMIT:
            exceeds = True
            break
        sub = await resolve_spf(
            inc,
            resolve_txt=resolve_txt,
            _visited=visited,
            _lookups=current_lookups + 1,  # include: mechanism costs +1 lookup
        )
        current_lookups = sub.lookup_count
        sources.extend(sub.sources)
        if sub.exceeds_limit:
            exceeds = True
            break

    # redirect= (заменяет, но мы уже собрали терминалы; если redirect — идём по нему)
    if redirect and not exceeds:
        if current_lookups >= SPF_LOOKUP_LIMIT:
            exceeds = True
        else:
            sub = await resolve_spf(
                redirect,
                resolve_txt=resolve_txt,
                _visited=visited,
                _lookups=current_lookups + 1,  # redirect= mechanism costs +1 lookup
            )
            current_lookups = sub.lookup_count
            sources.extend(sub.sources)
            if sub.exceeds_limit:
                exceeds = True

    # Дедуп + порядок стабильный (как нашли)
    seen: set[str] = set()
    deduped: list[str] = []
    for s in sources:
        if s not in seen:
            seen.add(s)
            deduped.append(s)

    return SpfResolution(
        sources=deduped,
        lookup_count=current_lookups,
        exceeds_limit=exceeds or (current_lookups > SPF_LOOKUP_LIMIT),
    )


__all__ = ["SPF_LOOKUP_LIMIT", "resolve_spf"]
