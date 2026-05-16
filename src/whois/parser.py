"""Парсинг RDAP-ответов и сырого WHOIS-текста в ``WhoisData``.

Принципы:

- **Толерантность.** Лучше вернуть частичные данные, чем упасть исключением:
  у разных регистраторов разный формат, и каждый парсер исключений — это
  пропущенное продление домена.
- **Никаких побочных эффектов.** Чистые функции, без I/O. Это упрощает
  тестирование на синтетических фикстурах.
- **Структурированные предупреждения.** При нераспознанной дате / поле —
  ``structlog.warning``, без падения.

Парсер дат построен поверх ``dateutil.parser`` с предварительной чисткой
строки и набором ручных форматов для редких кейсов (типа .ru `paid-till: ...`).
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from typing import Any

from dateutil import parser as dateutil_parser

from src.whois.types import WhoisData

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Словари синонимов: ключ WHOIS-текста (нижний регистр, без двоеточия) → поле
# ---------------------------------------------------------------------------

# Дата истечения.
EXPIRY_KEYS: frozenset[str] = frozenset(
    {
        "expiration date",
        "expires",
        "expires on",
        "expire",
        "expiry date",
        "expire date",  # .it
        "registry expiry date",
        "registrar registration expiration date",
        "renewal date",
        "paid-till",  # .ru / .su / .рф
    }
)

# Дата регистрации.
CREATED_KEYS: frozenset[str] = frozenset(
    {
        "creation date",
        "created",
        "created on",
        "registered",
        "registered on",
        "registration date",
        "registration time",
        "domain created",  # .kz (TCI-style)
        "domain registered",  # .kz alternative phrasing
    }
)

# Дата последнего изменения.
UPDATED_KEYS: frozenset[str] = frozenset(
    {
        "updated date",
        "last updated",
        "last update",
        "last modified",
        "modified",
        "changed",  # .de (DENIC)
        "last modification date",  # .kz
    }
)

# Регистратор.
REGISTRAR_KEYS: frozenset[str] = frozenset(
    {
        "registrar",
        "sponsoring registrar",
        "registrar name",
        "registrar.organization",  # .it
        "current registrar",  # .kz
    }
)

# EPP-статус домена. Многострочное поле.
STATUS_KEYS: frozenset[str] = frozenset(
    {
        "status",
        "domain status",
        "state",
    }
)

# Nameservers. Многострочное поле.
NS_KEYS: frozenset[str] = frozenset(
    {
        "name server",
        "nserver",
        "nameserver",
        "name servers",
        "nameservers",  # .it
        "primary name server",  # .kz
        "secondary name server",  # .kz
    }
)

# Признаки «домен не зарегистрирован» — подстроки в нижнем регистре, ищутся
# по полному ответу. Регистрарские реализации сильно отличаются, набор
# приходится держать широким.
NOT_FOUND_PATTERNS: tuple[str, ...] = (
    "no match for",
    "no match found",
    "not found",
    "no entries found",
    "no data found",
    "domain not found",
    "no such domain",
    "status: free",
    "status: available",
    "no information available",
    "domain status: available",
    "available for registration",
)

# Регулярка для строки ``key: value`` или ``key:value`` (с любым количеством
# пробелов). Не используем split(":", 1), потому что некоторые сервера
# отдают многострочные значения через продолжение строк — для таких полей
# отдельная обработка ниже. Символ ``.`` в ключе нужен для .it
# (``Registrar.Organization: ...``).
_KV_RE = re.compile(r"^\s*([A-Za-z][A-Za-z0-9 _\-/.]*?)\s*:\s*(.*)$")


# ---------------------------------------------------------------------------
# Парсер дат
# ---------------------------------------------------------------------------


def parse_whois_date(raw: str) -> datetime | None:
    """Толерантный парсер даты из WHOIS-строки.

    Принимает ISO 8601, ``DD.MM.YYYY``, ``DD-MMM-YYYY``, ``YYYY-MM-DD HH:MM:SS``,
    с/без таймзоны. Если не удалось разобрать — ``None`` (не исключение).
    Результат всегда timezone-aware UTC.
    """
    if not raw or not raw.strip():
        return None
    cleaned = raw.strip()
    # Многие сервера дописывают «marker», который мешает dateutil: ``# foobar``,
    # `<<<...>>>`, скобочные комментарии. Срезаем их.
    cleaned = re.sub(r"\s*#.*$", "", cleaned)
    cleaned = re.sub(r"\s*<<<.*?>>>\s*", "", cleaned)
    cleaned = re.sub(r"\s*\(.*?\)\s*$", "", cleaned)
    cleaned = cleaned.strip()

    # .ru paid-till: 2027-03-15T21:00:00Z — обычный ISO, dateutil справится.
    # .com: 15-Mar-2027 10:00:00 UTC — тоже dateutil.
    # .рф: 2027.03.15 — dateutil.
    # Русский dd.mm.yyyy: dateutil без dayfirst=True даст mm.dd.yyyy. Делаем
    # эвристику: если первая часть ``> 12``, это явно день, dayfirst=True.
    dayfirst = _looks_like_dayfirst(cleaned)

    try:
        parsed = dateutil_parser.parse(cleaned, dayfirst=dayfirst)
    except (ValueError, OverflowError, TypeError):
        logger.warning("Could not parse WHOIS date: %r", raw)
        return None

    # Приводим к UTC: naive datetime считаем уже в UTC (большинство WHOIS-серверов
    # отдают UTC, даже если явно не указано).
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


def _looks_like_dayfirst(s: str) -> bool:
    """Эвристика: похожа ли строка на формат ``DD.MM.YYYY`` / ``DD/MM/YYYY``."""
    m = re.match(r"^\s*(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})", s)
    if not m:
        return False
    first, second, third = int(m.group(1)), int(m.group(2)), int(m.group(3))
    # YYYY-MM-DD: первый компонент явно год → не dayfirst.
    if first >= 1900:
        return False
    # DD.MM.YYYY: первый компонент > 12 → точно день.
    if first > 12:
        return True
    # MM/DD/YYYY: второй компонент > 12 → точно месяц.
    if second > 12:
        return False
    # 03.04.2027: неоднозначно. Если третий компонент — год (>= 1900 или
    # двузначный), оставляем default-поведение dateutil (mm.dd.yyyy). На
    # таких форматах оба варианта дают валидный datetime, и точность
    # выбора не критична — это в любом случае подозрительный ввод.
    del third
    return False


# ---------------------------------------------------------------------------
# Парсер WHOIS-текста
# ---------------------------------------------------------------------------


def parse_whois_text(text: str, domain: str) -> WhoisData:
    """Разбирает текстовый WHOIS-ответ в ``WhoisData``.

    Если ответ — «нет такого домена» (любой из ``NOT_FOUND_PATTERNS``),
    возвращает ``WhoisData(is_registered=False)`` с пустыми полями.

    Никогда не бросает исключение. Нераспознанные поля — игнорируются.

    Особенности форматов:

    - **.de (DENIC)** не публикует дату истечения — это политика реестра,
      а не баг парсинга. ``expires_at`` будет ``None``; на уровне ``info``
      это логируется (один раз на ответ), без warning.
    - **.it (NIC.it)** отдаёт nameservers блоком с продолжением строк
      (``Nameservers:\\n    ns1...\\n    ns2...``) — разбирается отдельно.
    - **REDACTED FOR PRIVACY** и подобные плейсхолдеры в значениях
      игнорируются: лучше ``None``, чем строка ``"REDACTED"``.
    """
    raw_data: dict[str, Any] = {"raw_text": text}

    if _looks_like_not_found(text):
        return WhoisData(
            domain=domain,
            is_registered=False,
            raw_data=raw_data,
            source="whois",
        )

    expires_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    registrar: str | None = None
    status: list[str] = []
    name_servers: list[str] = []

    # Multi-line блок текущего «списочного» ключа: используется для .it
    # ``Nameservers:`` с продолжением на следующих indented-строках.
    continuation_list: list[str] | None = None

    for line in text.splitlines():
        stripped = line.strip()
        # Комментарии WHOIS — строки, начинающиеся с ``%`` (RIPE-style) или ``#``.
        if not stripped or stripped.startswith(("%", "#", ">>>")):
            continuation_list = None
            continue

        # Если идёт multi-line блок (например Nameservers): строки без ``:``
        # с продолжением — это значения списка. Прерываем по пустой строке
        # или по новой паре ``key:`` (это покрывается ниже).
        m = _KV_RE.match(line)
        if m is None:
            if continuation_list is not None and line.startswith((" ", "\t")):
                # indented продолжение — берём весь токен
                ns = _clean_ns(stripped)
                if ns and ns not in continuation_list:
                    continuation_list.append(ns)
            continue

        key = m.group(1).lower().strip()
        value = m.group(2).strip()

        # Новый KV прерывает блок продолжения.
        continuation_list = None

        # Игнорируем плейсхолдеры приватности — лучше None, чем мусор в БД.
        if _looks_like_redacted(value):
            value = ""

        if not value:
            # Список с продолжением: ``Nameservers:\n    ns1\n    ns2``.
            if key in NS_KEYS:
                continuation_list = name_servers
            continue

        # Первое непустое значение для каждого «одиночного» поля; для списочных
        # (status, name_servers) — копим.
        if key in EXPIRY_KEYS and expires_at is None:
            expires_at = parse_whois_date(value)
        elif key in CREATED_KEYS and created_at is None:
            created_at = parse_whois_date(value)
        elif key in UPDATED_KEYS and updated_at is None:
            updated_at = parse_whois_date(value)
        elif key in REGISTRAR_KEYS and registrar is None:
            registrar = value
        elif key in STATUS_KEYS:
            status.append(_clean_status(value))
        elif key in NS_KEYS:
            ns = _clean_ns(value)
            if ns and ns not in name_servers:
                name_servers.append(ns)

    # .de WHOIS никогда не показывает expires_at — это особенность DENIC,
    # документируется в публичной политике. Не warning, а info: «всё ок».
    if expires_at is None and domain.lower().endswith(".de"):
        logger.info(
            "WHOIS for .de domain has no expires_at (DENIC policy)",
            extra={"domain": domain},
        )

    return WhoisData(
        domain=domain,
        is_registered=True,
        expires_at=expires_at,
        created_at=created_at,
        updated_at=updated_at,
        registrar=registrar,
        status=status,
        name_servers=name_servers,
        raw_data=raw_data,
        source="whois",
    )


# Плейсхолдеры приватности в WHOIS-ответах (нижний регистр). При попадании
# в значение → трактуем как пустое.
_REDACTED_VALUES: frozenset[str] = frozenset(
    {
        "redacted for privacy",
        "redacted",
        "not disclosed",
        "data protected",
        "privacy protect",
    }
)


def _looks_like_redacted(value: str) -> bool:
    """True, если значение целиком — плейсхолдер приватности."""
    return value.strip().lower() in _REDACTED_VALUES


def _looks_like_not_found(text: str) -> bool:
    """Грубый поиск признаков «домен свободен» в произвольном WHOIS-тексте."""
    lower = text.lower()
    return any(pattern in lower for pattern in NOT_FOUND_PATTERNS)


def _clean_status(value: str) -> str:
    """Срезает URL-ссылку рядом со статусом: ``ok https://...`` → ``ok``.

    Многие реестры рендерят статус как ``clientTransferProhibited
    https://icann.org/epp#clientTransferProhibited``. Нам нужен только ключ.
    """
    return value.split()[0] if value else value


def _clean_ns(value: str) -> str:
    """Нормализует имя NS: lowercase, без trailing dot, без IP-адреса рядом.

    Формат у разных регистраторов разный:
    - ``ns1.example.com``
    - ``ns1.example.com.``
    - ``ns1.example.com 192.0.2.1`` (.ru-style)
    """
    # Берём только первое «слово» — это hostname.
    first = value.split()[0] if value else ""
    return first.rstrip(".").lower()


# ---------------------------------------------------------------------------
# Парсер RDAP
# ---------------------------------------------------------------------------


def parse_rdap(data: dict[str, Any], domain: str) -> WhoisData:
    """Разбирает RDAP-ответ (RFC 7483) в ``WhoisData``.

    Если ``data`` пустой/None — возвращаем «не зарегистрирован». Иначе
    надёжно извлекаем поля. Так как RDAP — JSON со схемой, тут проще
    чем с текстом, но регистрары всё равно вольно интерпретируют части
    стандарта (особенно entities), поэтому везде .get с дефолтами.
    """
    raw_data: dict[str, Any] = dict(data) if data else {}

    if not data:
        return WhoisData(
            domain=domain,
            is_registered=False,
            raw_data=raw_data,
            source="rdap",
        )

    # events[] с разными eventAction. RFC 7483 §4.5.
    expires_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    for event in _iter_dicts(data.get("events")):
        action = str(event.get("eventAction", "")).lower()
        when = event.get("eventDate")
        if not when:
            continue
        parsed = parse_whois_date(str(when))
        if parsed is None:
            continue
        if action == "expiration" and expires_at is None:
            expires_at = parsed
        elif action == "registration" and created_at is None:
            created_at = parsed
        elif action in {"last changed", "last update of rdap database"} and updated_at is None:
            updated_at = parsed

    # status[] — EPP-статусы (или их аналоги).
    status_raw = data.get("status") or []
    status: list[str] = [str(item) for item in status_raw if isinstance(item, str)]

    # nameservers[].ldhName
    name_servers: list[str] = []
    for ns in _iter_dicts(data.get("nameservers")):
        ldh = ns.get("ldhName") or ns.get("unicodeName")
        if ldh:
            cleaned = str(ldh).rstrip(".").lower()
            if cleaned and cleaned not in name_servers:
                name_servers.append(cleaned)

    # entities[] с ролью "registrar". В разных серверах имя лежит в
    # ``handle`` или в ``vcardArray`` — берём первое, что нашли.
    registrar: str | None = _extract_registrar(data)

    return WhoisData(
        domain=domain,
        is_registered=True,
        expires_at=expires_at,
        created_at=created_at,
        updated_at=updated_at,
        registrar=registrar,
        status=status,
        name_servers=name_servers,
        raw_data=raw_data,
        source="rdap",
    )


def _iter_dicts(value: Any) -> list[dict[str, Any]]:
    """Возвращает list[dict] из произвольного value — пустой при несоответствии типа."""
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _extract_registrar(data: dict[str, Any]) -> str | None:
    """Ищет регистратора в ``entities[]`` с ролью ``registrar``.

    Имя берём из vCard FN-поля; при его отсутствии — из ``handle``.
    """
    for entity in _iter_dicts(data.get("entities")):
        roles = entity.get("roles") or []
        if not isinstance(roles, list) or "registrar" not in roles:
            continue
        # vCard: ["vcard", [["version", {}, "text", "4.0"], ["fn", {}, "text", "GoDaddy"]]]
        vcard = entity.get("vcardArray")
        if isinstance(vcard, list) and len(vcard) >= 2 and isinstance(vcard[1], list):
            for prop in vcard[1]:
                if isinstance(prop, list) and len(prop) >= 4 and prop[0] == "fn":
                    name = prop[3]
                    if isinstance(name, str) and name.strip():
                        return name.strip()
        handle = entity.get("handle")
        if isinstance(handle, str) and handle.strip():
            return handle.strip()
    return None
