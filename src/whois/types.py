"""Модели данных WHOIS-ядра.

Эти типы — единственный интерфейс между парсером, фасадом ``lookup_domain``
и слоем сохранения в ``whois_cache`` / отправки в diff.

Используем ``dataclasses`` (а не pydantic): валидация на входе не нужна —
данные приходят либо из нашего же парсера, либо из БД через SQLAlchemy.
Заводить лишний слой валидации pydantic тут нет смысла.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

# Откуда получены данные. ``"rdap"`` — RDAP-запрос через ``whoisit``,
# ``"whois"`` — текстовый WHOIS на 43 порту.
DataSource = Literal["rdap", "whois"]


# Категории ошибок WHOIS-запроса. Используются в логике повторов и алертов.
# Список фиксированный, расширять только через ADR.
WhoisErrorType = Literal[
    "timeout",
    "not_found",  # домен не зарегистрирован (см. также WhoisData.is_registered)
    "rate_limited",
    "parse_error",
    "network_error",
    "unsupported_tld",  # ни RDAP, ни известный WHOIS-сервер не определены
]


@dataclass(slots=True, kw_only=True)
class WhoisData:
    """Структурированные WHOIS-данные домена.

    Все datetime-поля — timezone-aware UTC. ``raw_data`` хранится для
    отладки и кладётся в ``whois_cache.raw_data`` (JSONB).

    ``is_registered=False`` — домен свободен (NXDOMAIN / "no match"). В этом
    случае остальные поля могут быть пустыми/None.
    """

    domain: str
    is_registered: bool
    expires_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    registrar: str | None = None
    status: list[str] = field(default_factory=list)
    name_servers: list[str] = field(default_factory=list)
    raw_data: dict[str, Any] = field(default_factory=dict)
    source: DataSource = "whois"


@dataclass(slots=True, kw_only=True)
class WhoisError:
    """Описание неудачной попытки WHOIS-запроса.

    ``raw_response`` хранится опционально (для разбора непонятных кейсов
    в логах админ-канала). Никогда не пишется в БД — только в журнал.
    """

    domain: str
    error_type: WhoisErrorType
    message: str
    raw_response: str | None = None


# Union-тип возвращаемого значения фасада. Хэндлеры и таски проверяют
# через ``isinstance(result, WhoisData)`` / ``WhoisError``.
WhoisResult = WhoisData | WhoisError
