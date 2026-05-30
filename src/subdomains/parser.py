"""Парсер crt.sh ответов (TASK-0023, ADR 037).

Чистая функция для парсинга JSON-выдачи crt.sh:
- Извлечение name_value (может быть многострочным)
- Нормализация: punycode (idna), lowercase, dedup
- Фильтрация wildcard (*.example.com)
- Отбрасывание самого registrable
- Сохранение только поддоменов запрошенного registrable (PSL, ADR 035)
"""

from __future__ import annotations

from typing import Any

import idna


def parse_crtsh_response(
    registrable_domain: str,
    response_data: list[dict[str, Any]],
) -> list[str]:
    """Парсит ответ crt.sh и возвращает нормализованный список поддоменов.

    Args:
        registrable_domain: Registrable-домен (eTLD+1, ADR 035)
        response_data: JSON-ответ от crt.sh (список dict)

    Returns:
        Список поддоменов (нормализованных: lowercase, punycode, без wildcard)

    Пример ответа crt.sh:
        [
            {"name_value": "example.com\\nwww.example.com\\nmail.example.com"},
            {"name_value": "api.example.com"},
        ]
    """
    if not response_data:
        return []

    # Нормализуем registrable_domain для сравнения (punycode + lowercase)
    try:
        registrable_normalized = idna.encode(registrable_domain.lower()).decode("ascii")
    except (idna.IDNAError, UnicodeError):
        # Если registrable уже ASCII или невалидный — оставляем как есть
        registrable_normalized = registrable_domain.lower()

    subdomains = set()

    for entry in response_data:
        name_value = entry.get("name_value", "")
        if not name_value:
            continue

        # crt.sh возвращает многострочные значения (разделены \\n)
        for line in name_value.split("\\n"):
            line = line.strip()
            if not line:
                continue

            # Punycode конверсия (для IDN) — делаем первой, чтобы потом корректно
            # работали lowercase и сравнения
            try:
                normalized = idna.encode(line).decode("ascii")
            except (idna.IDNAError, UnicodeError):
                # Невалидный домен — пропускаем
                continue

            # Lowercase (после punycode — только ASCII)
            normalized = normalized.lower()

            # Отбрасываем wildcard
            if normalized.startswith("*."):
                continue

            # Отбрасываем сам registrable
            if normalized == registrable_normalized:
                continue

            # Проверяем, что это поддомен запрошенного registrable
            # (не public suffix и не чужой домен)
            if not _is_subdomain_of(normalized, registrable_normalized):
                continue

            subdomains.add(normalized)

    return sorted(subdomains)


def _is_subdomain_of(domain: str, registrable: str) -> bool:
    """Проверяет, что domain является поддоменом registrable.

    Args:
        domain: Проверяемый домен
        registrable: Registrable-родитель

    Returns:
        True если domain — поддомен registrable
    """
    # Для корректного сравнения приводим к lowercase
    domain_lower = domain.lower()
    registrable_lower = registrable.lower()

    # Точное совпадение не считается поддоменом
    if domain_lower == registrable_lower:
        return False

    # Поддомен заканчивается на .registrable
    # (например, www.example.com является поддоменом example.com)
    return domain_lower.endswith(f".{registrable_lower}")


__all__ = ["parse_crtsh_response"]
