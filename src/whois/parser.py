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

from src.whois.types import ContactRole, WhoisContact, WhoisData

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Ключи контактных полей — маппинг префиксов в текстовом WHOIS на роль
# ---------------------------------------------------------------------------

# Префиксы для thick-WHOIS (Verisign/MarkMonitor для .com/.net и подобные).
# Ключ парсится как ``<prefix> <field>``, prefix в нижнем регистре. Значения
# из ``Tech``/``Admin``/``Billing`` идут только если упомянуто это слово —
# одиночное ``Name:`` или ``Email:`` без префикса трактовать нельзя
# (слишком много ложных срабатываний).
_CONTACT_ROLE_PREFIXES: dict[str, ContactRole] = {
    "registrant": "registrant",
    "admin": "admin",
    "administrative": "admin",
    "tech": "tech",
    "technical": "tech",
    "billing": "billing",
}

# Подфилды контакта внутри prefix-блока, нормализованные ключи.
# Значение → атрибут WhoisContact. Не упомянутые поля игнорируются:
# адреса, fax, и пр. не нужны для текущей карточки.
_CONTACT_FIELD_NAMES: dict[str, str] = {
    "name": "name",
    "organization": "organization",
    "org": "organization",
    "email": "email",
    "e-mail": "email",
    "phone": "phone",
    "tel": "phone",
    "telephone": "phone",
    "country": "country",
    # .it-формат: ``Registrant.Name``, ``Registrant.Country`` — точку и
    # пробел разделителем считает _split_contact_key ниже.
    "name (raw)": "name",
    "holder": "name",  # .fr: «registrant: holder name»
}

# Плейсхолдеры приватности в значениях контактных полей: после strip()/lower()
# точное совпадение → значение трактуем как «скрыто», поле остаётся None,
# но WhoisContact.is_redacted=True.
_PRIVACY_TOKENS: frozenset[str] = frozenset(
    {
        "redacted for privacy",
        "redacted",
        "not disclosed",
        "data protected",
        "privacy protect",
        "private person",
        "gdpr masked",
        "personal data",
        "withheld for privacy",
    }
)


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

# Признаки того, что «ответ» — на самом деле ошибка upstream'а (рейтлимит,
# заглушка, HTML), а не WHOIS-данные. Такой текст НЕЛЬЗЯ трактовать как
# «домен свободен» (TASK-0092, класс «сбой ≠ свободен», ср. TASK-0079).
UPSTREAM_ERROR_PATTERNS: tuple[str, ...] = (
    "exceeded allowed connection rate",
    "rate limit",
    "ratelimit",
    "too many requests",
    "try again later",
    "quota exceeded",
    "service unavailable",
    "temporarily unavailable",
    "connection refused",
    "<html",
    "<!doctype",
    "502 bad gateway",
    "504 gateway",
)


def looks_like_upstream_error(text: str) -> bool:
    """Текст похож на ошибку/заглушку upstream'а, а не на WHOIS-ответ."""
    lower = text.lower()
    return any(pattern in lower for pattern in UPSTREAM_ERROR_PATTERNS)


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
    # Контакты накапливаем в словаре, чтобы поля, пришедшие порционно
    # (``Registrant Name`` → ``Registrant Email`` → ...) собрались в один
    # ``WhoisContact``. В finalize-фазе превратим в список.
    contacts_acc: dict[ContactRole, dict[str, Any]] = {}

    # Для .ru/.рф/.su trigger'им отдельный набор ключей: значения там без
    # role-префикса (``person:``, ``org:``, ``e-mail:``) и относятся к
    # registrant'у. Признак включаем заранее по TLD-суффиксу.
    is_ru_like = _is_ru_like_tld(domain)

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
        raw_value = m.group(2).strip()

        # Новый KV прерывает блок продолжения.
        continuation_list = None

        # 1. Контактные поля — обрабатываем ПЕРВЫМИ, с сырым значением:
        # маркеры приватности здесь должны проставить ``is_redacted=True``,
        # а не молча обнулиться (как для обычных полей).
        if _try_absorb_contact_field(
            key=key,
            raw_value=raw_value,
            accumulator=contacts_acc,
            is_ru_like=is_ru_like,
        ):
            continue

        # 2. Стандартные поля. Здесь privacy-маркер → пустое значение, чтоб
        # не писать «REDACTED FOR PRIVACY» в registrar или status.
        value = raw_value
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

    contacts = _finalize_contacts(contacts_acc)

    return WhoisData(
        domain=domain,
        is_registered=True,
        expires_at=expires_at,
        created_at=created_at,
        updated_at=updated_at,
        registrar=registrar,
        status=status,
        name_servers=name_servers,
        contacts=contacts,
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


# ---------------------------------------------------------------------------
# Парсер контактных полей текстового WHOIS
# ---------------------------------------------------------------------------


# Ключи .ru/.рф/.su, относящиеся к registrant'у (формат TCINET).
_RU_REGISTRANT_KEYS: dict[str, str] = {
    "org": "organization",
    "person": "name",  # вместе с признаком redacted при «Private Person»
    "e-mail": "email",
    "phone": "phone",
}


def _is_ru_like_tld(domain: str) -> bool:
    """True для доменов в .ru / .su / .рф (включая punycode xn--p1ai)."""
    d = domain.lower()
    return d.endswith((".ru", ".su", ".xn--p1ai"))


def _split_contact_key(key: str) -> tuple[ContactRole, str] | None:
    """Раскладывает 'registrant name' / 'registrant.name' / 'admin email'
    в пару (role, field). Возвращает None для не-контактных ключей.
    """
    # Перебираем возможные разделители — пробел или точка. Hyphen не берём:
    # ``admin-contact`` в .ru — это URL, а ``e-mail`` — корневой ключ.
    for sep in (".", " "):
        if sep in key:
            prefix, _, rest = key.partition(sep)
            role = _CONTACT_ROLE_PREFIXES.get(prefix.strip())
            if role is None:
                continue
            field_name = _CONTACT_FIELD_NAMES.get(rest.strip())
            if field_name is None:
                continue
            return (role, field_name)
    return None


def _try_absorb_contact_field(
    *,
    key: str,
    raw_value: str,
    accumulator: dict[ContactRole, dict[str, Any]],
    is_ru_like: bool,
) -> bool:
    """Если ``key`` — поле контакта, сохраняет ``raw_value`` в аккумулятор.

    Возвращает ``True`` если ключ распознан как контактный (и значит, цикл
    парсера может ``continue`` без дальнейшей обработки) и ``False`` иначе.

    Алгоритм:

    1. ``registrant name`` / ``admin.email`` — generic prefix-field.
    2. Для .ru/.рф/.su: одиночные ключи (``org``, ``person``, ``e-mail``,
       ``phone``) идут в registrant.
    3. ``registrant`` / ``holder`` без подполя → registrant.organization
       или .name (для .fr / DENIC).

    Плейсхолдеры приватности оставляют поле пустым, но выставляют флаг
    ``is_redacted`` у контакта.
    """
    parsed: tuple[ContactRole, str] | None = _split_contact_key(key)
    if parsed is None and is_ru_like and key in _RU_REGISTRANT_KEYS:
        parsed = ("registrant", _RU_REGISTRANT_KEYS[key])
    elif parsed is None and key in {"registrant", "holder", "registrant holder"}:
        # ``Registrant Holder:`` (DENIC) — берём в organization, потому
        # что чаще это юр.лицо. Для физлица будет точно так же отображено.
        parsed = ("registrant", "organization")
    if parsed is None:
        return False

    role, field_name = parsed
    # admin-contact в .ru — это URL, а не email; защита от ложноположительных.
    if raw_value.lower().startswith(("http://", "https://")):
        return True

    contact = accumulator.setdefault(role, {})

    if _looks_like_privacy_value(raw_value) or _looks_like_redacted(raw_value):
        contact["is_redacted"] = True
        # Если это поле name/organization — сохраняем как None, но всё равно
        # отмечаем что контакт существовал в ответе.
        contact.setdefault(field_name, None)
        return True

    if not raw_value.strip():
        # Пустое значение для контактного поля — ничего интересного, но
        # формально ключ распознан, чтоб не упасть в общий маршрут.
        return True

    # Country приводим к ISO-alpha-2 верхним регистром если строка ≤ 3 символов.
    if field_name == "country":
        cleaned = raw_value.strip()
        contact[field_name] = cleaned.upper() if 2 <= len(cleaned) <= 3 else cleaned
        return True

    contact[field_name] = raw_value.strip()
    return True


def _looks_like_privacy_value(value: str) -> bool:
    """True, если значение — плейсхолдер приватности (RFC 9537-стиль / `.ru` `Private Person`)."""
    return value.strip().lower() in _PRIVACY_TOKENS


def _finalize_contacts(
    accumulator: dict[ContactRole, dict[str, Any]],
) -> list[WhoisContact]:
    """Превращает накопленные словари в ``WhoisContact``. Пустые — отбрасываем.

    ``is_redacted=True`` ставится автоматически если для роли пришли только
    маркеры приватности, без идентифицирующих данных.
    """
    out: list[WhoisContact] = []
    for role, data in accumulator.items():
        name = data.get("name")
        org = data.get("organization")
        email = data.get("email")
        phone = data.get("phone")
        country = data.get("country")
        is_redacted = bool(data.get("is_redacted", False))

        # Auto-redacted: ни name, ни org не найдено, и нет полезных полей.
        # Пустая запись без флага редакции — пропускаем (например, .it оставляет
        # блок Tech полностью пустым после redaction'ов).
        if not name and not org and not email and not phone and not country and not is_redacted:
            continue
        # Auto-redacted из значения «Private Person» (registrant name пришёл
        # как маркер): уже был выставлен в _try_absorb_contact_field.
        if isinstance(name, str) and _looks_like_privacy_value(name):
            is_redacted = True

        out.append(
            WhoisContact(
                role=role,
                name=name if isinstance(name, str) and name.strip() else None,
                organization=org if isinstance(org, str) and org.strip() else None,
                email=email if isinstance(email, str) and email.strip() else None,
                phone=phone if isinstance(phone, str) and phone.strip() else None,
                country=country if isinstance(country, str) and country.strip() else None,
                is_redacted=is_redacted,
            )
        )
    return out


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

    # entities[] с ролями registrant/admin/tech/abuse/billing. RFC 9537
    # ``redacted[]`` подсказывает, какие vCard-поля скрыты регистратором.
    redacted_paths = _collect_redacted_paths(data)
    contacts = _extract_contacts(data, redacted_paths)

    return WhoisData(
        domain=domain,
        is_registered=True,
        expires_at=expires_at,
        created_at=created_at,
        updated_at=updated_at,
        registrar=registrar,
        status=status,
        name_servers=name_servers,
        contacts=contacts,
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


# ---------------------------------------------------------------------------
# Извлечение контактов из RDAP
# ---------------------------------------------------------------------------


# RDAP-роль (RFC 7483 §10.2) → наша ContactRole. Не упомянутые роли —
# ``proxy``, ``noc``, ``reseller``, ``sponsor`` — карточке не нужны.
_RDAP_ROLE_MAP: dict[str, ContactRole] = {
    "registrant": "registrant",
    "administrative": "admin",
    "admin": "admin",
    "technical": "tech",
    "tech": "tech",
    "billing": "billing",
    "abuse": "abuse",
}


def _collect_redacted_paths(data: dict[str, Any]) -> set[str]:
    """Собирает множество ``prePath`` из RFC 9537 ``redacted[]``.

    Не парсим JSONPath полностью — нам достаточно знать, что у роли X
    что-то отредактировано, чтобы пометить ``is_redacted=True`` для всего
    контакта. Возвращаем строки prePath как есть.
    """
    out: set[str] = set()
    for item in _iter_dicts(data.get("redacted")):
        prepath = item.get("prePath") or item.get("postPath")
        if isinstance(prepath, str):
            out.add(prepath)
    return out


def _role_is_redacted_by_paths(role: ContactRole, paths: set[str]) -> bool:
    """Эвристика: упоминается ли роль в RFC 9537 prePath/postPath."""
    if not paths:
        return False
    # RDAP-имя роли встречается в prePath: проверим обе версии (короткую и длинную).
    role_aliases = {
        "registrant": ("registrant",),
        "admin": ("administrative", "admin"),
        "tech": ("technical", "tech"),
        "billing": ("billing",),
        "abuse": ("abuse",),
    }[role]
    for path in paths:
        lower = path.lower()
        if any(alias in lower for alias in role_aliases):
            return True
    return False


def _extract_contacts(
    data: dict[str, Any],
    redacted_paths: set[str],
) -> list[WhoisContact]:
    """Возвращает список контактов из RDAP-entities + вложенных entities.

    Заходим на один уровень вложенности: типично abuse-контакт лежит внутри
    entity с ролью ``registrar``. Глубже не идём — RDAP ограничивает
    разумную глубину.
    """
    out: list[WhoisContact] = []
    seen_roles: set[ContactRole] = set()

    def consume(entity_dicts: list[dict[str, Any]]) -> None:
        for entity in entity_dicts:
            roles = entity.get("roles") or []
            if not isinstance(roles, list):
                continue
            for raw_role in roles:
                if not isinstance(raw_role, str):
                    continue
                mapped = _RDAP_ROLE_MAP.get(raw_role.lower())
                if mapped is None or mapped in seen_roles:
                    continue
                contact = _entity_to_contact(entity, mapped, redacted_paths)
                if contact is not None:
                    out.append(contact)
                    seen_roles.add(mapped)
                    break  # одну entity — на одну роль

    top = _iter_dicts(data.get("entities"))
    consume(top)
    for entity in top:
        consume(_iter_dicts(entity.get("entities")))
    return out


def _entity_to_contact(
    entity: dict[str, Any],
    role: ContactRole,
    redacted_paths: set[str],
) -> WhoisContact | None:
    """Превращает одну RDAP-entity в ``WhoisContact``.

    Возвращает None, если нет ничего ценного (ни name, ни org, ни email,
    ни флага редакции) — пустые роли в карточке не отражаются.
    """
    name = None
    org = None
    email = None
    phone = None
    country = None

    vcard = entity.get("vcardArray")
    if isinstance(vcard, list) and len(vcard) >= 2 and isinstance(vcard[1], list):
        for prop in vcard[1]:
            if not isinstance(prop, list) or len(prop) < 4:
                continue
            name_key = prop[0]
            value = prop[3]
            if name_key == "fn" and isinstance(value, str) and value.strip():
                name = value.strip()
            elif name_key == "org":
                org_str = _flatten_vcard_value(value)
                if org_str:
                    org = org_str
            elif name_key == "email" and isinstance(value, str) and value.strip():
                email = value.strip()
            elif name_key == "tel":
                tel_str = value.strip() if isinstance(value, str) else None
                if tel_str:
                    # RDAP отдаёт `tel:+1.5551234567` — снимаем URI-префикс.
                    if tel_str.lower().startswith("tel:"):
                        tel_str = tel_str[4:]
                    phone = tel_str
            elif name_key == "adr":
                country = _country_from_adr(value)

    # Если есть RFC 9537 redacted-пометка для этой роли — считаем контакт скрытым.
    is_redacted = _role_is_redacted_by_paths(role, redacted_paths)

    # Авто-эвристика: ни name, ни org, ни email, ни phone — но entity есть в RDAP.
    # Скорее всего vCard вырезана (RFC 9537 / GDPR redaction).
    has_anything = any([name, org, email, phone, country])
    if not has_anything:
        if not is_redacted and not _looks_like_remarks_redacted(entity):
            return None
        is_redacted = True

    # Плейсхолдеры внутри значений (Markmonitor шлёт ``Data Protected``).
    for candidate in (name, org):
        if isinstance(candidate, str) and candidate.strip().lower() in _PRIVACY_TOKENS:
            is_redacted = True
            break

    return WhoisContact(
        role=role,
        name=name,
        organization=org,
        email=email,
        phone=phone,
        country=country,
        is_redacted=is_redacted,
    )


def _flatten_vcard_value(value: Any) -> str | None:
    """vCard ``org`` может быть строкой или списком частей: объединяем."""
    if isinstance(value, str):
        v = value.strip()
        return v or None
    if isinstance(value, list):
        parts = [str(p).strip() for p in value if isinstance(p, str) and p.strip()]
        joined = ", ".join(parts) if parts else ""
        return joined or None
    return None


def _country_from_adr(value: Any) -> str | None:
    """adr — список из 7 элементов, последний — country-name (vCard 4.0)."""
    if not isinstance(value, list) or len(value) < 7:
        return None
    candidate = value[6]
    if isinstance(candidate, str) and candidate.strip():
        cleaned = candidate.strip()
        return cleaned.upper() if 2 <= len(cleaned) <= 3 else cleaned
    return None


def _looks_like_remarks_redacted(entity: dict[str, Any]) -> bool:
    """RDAP-`remarks[]` может содержать сообщение об усечённых данных."""
    remarks = entity.get("remarks")
    if not isinstance(remarks, list):
        return False
    for r in remarks:
        if not isinstance(r, dict):
            continue
        title = r.get("title") or ""
        if isinstance(title, str) and "redact" in title.lower():
            return True
        rtype = r.get("type")
        if isinstance(rtype, str) and "truncat" in rtype.lower():
            return True
    return False
