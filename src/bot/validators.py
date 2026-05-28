"""Валидация доменов из пользовательского ввода.

Используется хэндлерами и сервисом ``services/csv_io.py``.
Никаких HTTP-запросов и обращений к БД — только синтаксический разбор.
"""

from __future__ import annotations

import ipaddress
import re

import idna

from src.utils.domains import is_public_suffix_only
from src.utils.idn import normalize_domain

# Полный label: 1–63 символа, буквы/цифры/дефис, не начинается и не кончается дефисом.
# Для IDN валидируем уже после punycode-конверсии, ASCII-варианта достаточно.
_LABEL_RE = re.compile(r"^(?!-)[A-Za-z0-9-]{1,63}(?<!-)$")

# Извлечение «слова, похожего на домен» из произвольного текста.
# Минимум одна точка: ``a.b`` — кандидат, ``a`` — нет. TLD — две и более буквы
# (включая Unicode, для IDN-доменов: ``.рф``, ``.中国`` и т.п.).
_DOMAIN_TOKEN_RE = re.compile(
    r"(?:[\w\-]+\.)+[A-Za-z¡-￿]{2,}",
    re.UNICODE,
)


def _looks_like_ip(s: str) -> bool:
    """True для валидного IPv4/IPv6. URL'ы со схемой сюда не попадают."""
    try:
        ipaddress.ip_address(s)
    except ValueError:
        return False
    return True


def is_valid_domain(s: str) -> bool:
    """Строгая проверка: можно ли это считать доменом для отслеживания.

    Делает полную нормализацию через ``normalize_domain``, затем проверяет
    каждый label по RFC 1035 (ASCII-форма после IDN).

    Не считается доменом:
    - пустая строка
    - IP-адрес (v4/v6)
    - одно-label-строка без точки (``localhost``)
    - email (содержит ``@``)
    - что угодно с пробелами внутри
    """
    if not s or not isinstance(s, str):
        return False
    s = s.strip()
    if not s:
        return False
    if "@" in s or any(ch.isspace() for ch in s):
        return False
    if _looks_like_ip(s):
        return False
    try:
        normalized = normalize_domain(s)
    except (idna.IDNAError, ValueError, UnicodeError):
        return False
    if "." not in normalized:
        return False
    labels = normalized.split(".")
    if any(not _LABEL_RE.match(label) for label in labels):
        return False
    # Общая длина — максимум 253 (без учёта trailing dot).
    if len(normalized) > 253:
        return False
    # TLD не может состоять только из цифр (это IPv4-suffix или просто бред).
    if labels[-1].isdigit():
        return False
    # Отклоняем публичные суффиксы через PSL (co.uk, org.uk, ru и т.п.)
    if is_public_suffix_only(normalized):
        return False
    return True


def extract_domain_from_text(text: str) -> str | None:
    """Извлекает первый похожий на домен токен из произвольного текста.

    Используется для обработки сообщения "не команда": если в тексте есть
    домен — пытаемся показать его WHOIS.

    Возвращает punycode-нормализованную форму или ``None``.
    """
    if not text:
        return None
    # Сначала пробуем целиком (вдруг это URL/строка из одного домена).
    candidates: list[str] = []
    stripped = text.strip()
    if stripped:
        candidates.append(stripped)
    # Затем все токены, похожие на домены.
    candidates.extend(_DOMAIN_TOKEN_RE.findall(text))

    for candidate in candidates:
        if is_valid_domain(candidate):
            try:
                return normalize_domain(candidate)
            except (idna.IDNAError, ValueError, UnicodeError):
                continue
    return None


def looks_like_just_domain(text: str) -> bool:
    """True, если весь текст — это **голый** домен.

    Без схемы, пути, query, fragment, порта, ``@``. Для URL и текста с
    доменом внутри есть ``extract_domain_from_text``.
    Триггер для автоматического запуска ``/whois`` на голое сообщение.
    """
    if not text:
        return False
    s = text.strip()
    if not s or any(ch.isspace() for ch in s):
        return False
    if any(ch in s for ch in ("/", "?", "#", "@", ":")):
        return False
    return is_valid_domain(s)
