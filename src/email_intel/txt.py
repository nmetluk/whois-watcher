"""Извлечение строки из TXT-rdata dnspython (TASK-0089).

Урок инцидента 2026-06-05 (отчёт TASK-0088): по всему email-слою звался
``r.to_unicode()``, которого у TXT-rdata в dnspython **не существует**
(``to_unicode`` есть только у ``dns.name.Name``). Любой домен с
TXT-записями ронял ``fetch_email_intel`` целиком (нет MX/SPF/DMARC) и
``fetch_deep_email`` (пустой deep-отчёт). Тесты были зелёными, потому что
мокали несуществующий метод (``MagicMock(to_unicode=...)``) — четвёртый
инцидент anti-drift-класса (после TASK-0017/0020 и _shape_domain).

Правильный способ: ``r.strings`` — кортеж байтовых сегментов (длинные
записи, например SPF, дробятся по 255 байт); сегменты конкатенируются
без разделителя (RFC 7208 §3.3).
"""

from __future__ import annotations

from typing import Any


def txt_to_str(rdata: Any) -> str:
    """Склеивает сегменты TXT-rdata в одну unicode-строку.

    ``rdata.strings`` — официальный API dnspython для TXT. Нет ``strings``
    (неожиданный тип rdata) → fallback на ``to_text()`` со срезанием
    обрамляющих кавычек.
    """
    strings = getattr(rdata, "strings", None)
    if strings is not None:
        return b"".join(strings).decode("utf-8", errors="replace")
    # fallback: to_text() возвращает '"seg1" "seg2"' — убираем кавычки
    text: str = rdata.to_text()
    if text.startswith('"') and text.endswith('"'):
        return text[1:-1].replace('" "', "")
    return text
