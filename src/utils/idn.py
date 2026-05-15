"""IDN-конверсия и нормализация доменов.

Внутри БД и в кэше домены хранятся **только в punycode** (ASCII).
Конверсия в Unicode — только на границе отображения пользователю.
"""

from __future__ import annotations

import re

import idna

# Регэксп для отрезания схемы (https://, http://, ftp://, ftps://...)
_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.\-]*://")


def to_punycode(domain: str) -> str:
    """Конвертирует доменное имя в ASCII-форму (punycode).

    Уже ASCII-домен возвращается как есть (lowercase).
    На невалидном вводе выбрасывает ``idna.IDNAError``.

    Примеры::

        to_punycode("пример.рф")  -> "xn--e1afmkfd.xn--p1ai"
        to_punycode("Example.COM") -> "example.com"
    """
    domain = domain.strip().lower()
    if not domain:
        raise idna.IDNAError("empty domain")
    # idna.encode уже корректно обрабатывает ASCII-домены, но строго
    # проверяет соответствие IDNA 2008. uts46=True даёт более мягкую
    # обработку устаревших символов.
    encoded = idna.encode(domain, uts46=True)
    return encoded.decode("ascii")


def from_punycode(domain: str) -> str:
    """Конвертирует punycode-домен обратно в Unicode для отображения.

    На невалидном вводе возвращает исходную строку (для UI лучше показать
    как есть, чем уронить хэндлер).
    """
    domain = domain.strip().lower()
    if not domain:
        return domain
    try:
        return idna.decode(domain)
    except idna.IDNAError:
        return domain


def normalize_domain(raw: str, *, strip_www: bool = False) -> str:
    """Нормализует произвольный пользовательский ввод в punycode-домен.

    Снимает:

    - пробелы по краям
    - схему ``http(s)://``, ``ftp://`` и т.п.
    - всё, что после первого ``/`` (путь, query, fragment)
    - порт ``:8080``
    - суффикс ``.`` (root label)
    - опционально префикс ``www.`` (``strip_www=True``)

    Затем приводит к нижнему регистру и кодирует в punycode.
    На невалидном вводе пробрасывает ``idna.IDNAError``.
    """
    s = raw.strip().lower()
    if not s:
        raise idna.IDNAError("empty input")

    # Убираем схему.
    s = _SCHEME_RE.sub("", s)

    # Отрезаем путь / query / fragment.
    for sep in ("/", "?", "#"):
        idx = s.find(sep)
        if idx >= 0:
            s = s[:idx]

    # Срезаем порт (последнее двоеточие, если за ним только цифры).
    if ":" in s:
        host, _, port = s.rpartition(":")
        if port.isdigit():
            s = host

    # Trailing dot (root label).
    s = s.rstrip(".")

    if strip_www and s.startswith("www."):
        s = s[4:]

    if not s:
        raise idna.IDNAError("empty after normalization")

    return to_punycode(s)
