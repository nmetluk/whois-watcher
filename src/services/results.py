"""Result-объекты сервисного слоя.

Сервисы возвращают плотные dataclass'ы, а не tuple'ы или сырые модели. Это:

- даёт хэндлерам предсказуемый ``isinstance(...)`` / ``match`` switch
- описывает все исходы операции на уровне типов (``status: Literal[...]``)
- инкапсулирует «было/стало» — хэндлер не знает, что данные пришли из кэша
  или из live-lookup'а

Никакой бизнес-логики тут нет — это «протокол ответа».
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from src.db.models import UserDomain, WhoisCache
from src.whois.types import WhoisData, WhoisError

# ---------------------------------------------------------------------------
# WhoisFacade.get_or_fetch
# ---------------------------------------------------------------------------


@dataclass(slots=True, kw_only=True)
class FacadeResult:
    """Ответ ``WhoisFacade.get_or_fetch``.

    ``data`` — успешный результат (свежий или stale из кэша).
    ``error`` — фатальная ошибка, когда даже из кэша нечего показать.
    Ровно одно из двух всегда заполнено.

    ``is_stale=True`` означает, что live-lookup упал по таймауту/сети, но в
    кэше нашлись старые данные. ``stale_age_days`` — возраст по ``fetched_at``.
    """

    data: WhoisData | None = None
    error: WhoisError | None = None
    is_stale: bool = False
    stale_age_days: int = 0


# ---------------------------------------------------------------------------
# DomainService.add_for_user
# ---------------------------------------------------------------------------

AddStatus = Literal[
    "added",  # успешно добавлено + есть свежие WHOIS-данные
    "added_pending",  # добавлено, данные подгружаются в фоне
    "already_tracked",  # домен уже у пользователя в списке
    "promoted",  # промоут из wishlist в обычное отслеживание
    "limit_reached",  # достигнут MAX_DOMAINS_PER_USER
    "invalid_domain",  # не похоже на домен
]


@dataclass(slots=True, kw_only=True)
class AddDomainResult:
    """Ответ ``DomainService.add_for_user``."""

    status: AddStatus
    # Нормализованное имя (punycode, lowercase). Пусто только если invalid_domain.
    normalized_domain: str = ""
    # WHOIS-данные — если уже были в общем кэше.
    whois_data: WhoisData | None = None
    # Для удобства локалей: чему равны notify_days пользователя (RU-форматирование).
    notify_days_label: str = ""
    # Текущий лимит — используется для сообщения об ошибке ``limit_reached``.
    limit: int = 0
    # extra — на будущее для деталей, которые могут понадобиться UI'ю.
    extra: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# DomainService.remove_for_user
# ---------------------------------------------------------------------------

RemoveStatus = Literal["removed", "not_tracked", "invalid_domain"]


@dataclass(slots=True, kw_only=True)
class RemoveDomainResult:
    """Ответ ``DomainService.remove_for_user``."""

    status: RemoveStatus
    normalized_domain: str = ""


# ---------------------------------------------------------------------------
# DomainService.list_for_user
# ---------------------------------------------------------------------------

ListFilter = Literal[
    "all",
    "expiring",
    "no_data",
    "muted",
    "critical",  # Этап 9 — есть critical-статусы (clientHold / pendingDelete / …)
    "expired",  # Этап 9 — expires_at в прошлом
    "wishlist",  # Этап 9 — режим «ждём освобождения»
]


@dataclass(slots=True, kw_only=True)
class ListPage:
    """Одна страница ``/list``: ровно те записи, что показываем пользователю."""

    rows: list[tuple[UserDomain, WhoisCache | None]] = field(default_factory=list)
    total: int = 0
    page: int = 0  # 0-индексированная
    page_size: int = 50
    filter_type: ListFilter = "all"
    search_query: str = ""  # Этап 9 — активный текстовый фильтр (пустой = неактивен)

    @property
    def total_pages(self) -> int:
        if self.page_size <= 0 or self.total == 0:
            return 1
        return (self.total + self.page_size - 1) // self.page_size

    @property
    def is_empty(self) -> bool:
        return self.total == 0
