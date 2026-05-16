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


# Роль контакта в WHOIS/RDAP. ``abuse`` — отдельный канал жалоб (берётся
# из RDAP-entities[role=abuse] или из «Registrar Abuse Contact» текстового
# WHOIS); ``billing`` практически нигде не публикуется после GDPR, но
# оставлен для совместимости с парсерами вне gTLD.
ContactRole = Literal["registrant", "admin", "tech", "billing", "abuse"]


@dataclass(slots=True, kw_only=True)
class WhoisContact:
    """Контактные данные одной роли (registrant / admin / tech / abuse / billing).

    Заполняется парсерами «насколько возможно». ``is_redacted=True`` означает,
    что регистрар скрыл идентифицирующие поля (RFC 9537 redacted[], плейсхолдер
    ``REDACTED FOR PRIVACY`` или ``Private Person`` в .ru). В этом случае поля
    ``name``/``organization`` могут быть ``None`` или содержать сам плейсхолдер
    — UI трактует это однообразно через флаг.
    """

    role: ContactRole
    name: str | None = None
    organization: str | None = None
    email: str | None = None
    phone: str | None = None
    country: str | None = None  # ISO-3166 alpha-2, верхний регистр, если удалось
    is_redacted: bool = False


@dataclass(slots=True, kw_only=True)
class WhoisData:
    """Структурированные WHOIS-данные домена.

    Все datetime-поля — timezone-aware UTC. ``raw_data`` хранится для
    отладки и кладётся в ``whois_cache.raw_data`` (JSONB).

    ``is_registered=False`` — домен свободен (NXDOMAIN / "no match"). В этом
    случае остальные поля могут быть пустыми/None.

    ``contacts`` — список контактов всех ролей, найденных в ответе. Порядок
    в списке не нормализован: парсер возвращает их в порядке появления в
    источнике. Для удобного доступа к стандартным ролям — свойства
    ``registrant`` / ``admin`` / ``tech``.
    """

    domain: str
    is_registered: bool
    expires_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    registrar: str | None = None
    status: list[str] = field(default_factory=list)
    name_servers: list[str] = field(default_factory=list)
    contacts: list[WhoisContact] = field(default_factory=list)
    raw_data: dict[str, Any] = field(default_factory=dict)
    source: DataSource = "whois"

    @property
    def registrant(self) -> WhoisContact | None:
        """Возвращает контакт ``registrant`` если он есть."""
        return self._contact_for("registrant")

    @property
    def admin(self) -> WhoisContact | None:
        """Возвращает контакт ``admin`` (administrative) если он есть."""
        return self._contact_for("admin")

    @property
    def tech(self) -> WhoisContact | None:
        """Возвращает контакт ``tech`` (technical) если он есть."""
        return self._contact_for("tech")

    def _contact_for(self, role: ContactRole) -> WhoisContact | None:
        return next((c for c in self.contacts if c.role == role), None)


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


__all__ = [
    "ContactRole",
    "DataSource",
    "WhoisContact",
    "WhoisData",
    "WhoisError",
    "WhoisErrorType",
    "WhoisResult",
]
