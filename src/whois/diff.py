"""Сравнение двух состояний ``WhoisData`` (старое vs новое).

Используется воркером ``check_domain`` (Этап 4): получив свежий ответ,
сравниваем с тем, что уже лежит в ``whois_cache``, и если что-то
изменилось — запускаем ``send_change_notice`` подписанным пользователям
(ADR 012).

Семантика:

- ``expires_at`` — точное сравнение datetime'ов. Микро-различия (микросекунды,
  таймзонные артефакты) игнорируем через ``_dt_eq``: разрыв ≤ 1 час не
  считается изменением.
- ``registrar`` — точное сравнение строк (с trim).
- ``name_servers``, ``status`` — set-сравнение (порядок не важен, регистр
  у нас уже нормализован парсером).

``compute_diff(old=None, new)`` — пустой diff: это первая проверка, нечего
сравнивать.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from src.whois.types import WhoisData

# Допуск для сравнения дат: меньше — считаем «не изменилось». Это защита
# от микро-различий между источниками (RDAP отдаёт ms, WHOIS — секунды).
_DATE_TOLERANCE = timedelta(hours=1)


@dataclass(slots=True, kw_only=True)
class WhoisDiff:
    """Результат сравнения двух ``WhoisData``.

    ``old_values`` / ``new_values`` хранят только изменившиеся поля —
    удобно для уведомлений (показываем «было → стало»). Ключи в этих
    словарях совпадают с именами полей ``WhoisData``.
    """

    expires_at_changed: bool = False
    registrar_changed: bool = False
    name_servers_changed: bool = False
    status_changed: bool = False
    old_values: dict[str, Any] = field(default_factory=dict)
    new_values: dict[str, Any] = field(default_factory=dict)

    @property
    def has_any_changes(self) -> bool:
        """True, если изменился хотя бы один из отслеживаемых полей."""
        return (
            self.expires_at_changed
            or self.registrar_changed
            or self.name_servers_changed
            or self.status_changed
        )


def compute_diff(old: WhoisData | None, new: WhoisData) -> WhoisDiff:
    """Сравнивает старое и новое состояние домена.

    Если ``old`` None — diff пустой (это первая проверка).
    """
    diff = WhoisDiff()
    if old is None:
        return diff

    if not _dt_eq(old.expires_at, new.expires_at):
        diff.expires_at_changed = True
        diff.old_values["expires_at"] = old.expires_at
        diff.new_values["expires_at"] = new.expires_at

    if _norm_str(old.registrar) != _norm_str(new.registrar):
        diff.registrar_changed = True
        diff.old_values["registrar"] = old.registrar
        diff.new_values["registrar"] = new.registrar

    if set(old.name_servers) != set(new.name_servers):
        diff.name_servers_changed = True
        diff.old_values["name_servers"] = list(old.name_servers)
        diff.new_values["name_servers"] = list(new.name_servers)

    if set(old.status) != set(new.status):
        diff.status_changed = True
        diff.old_values["status"] = list(old.status)
        diff.new_values["status"] = list(new.status)

    return diff


def _dt_eq(a: datetime | None, b: datetime | None) -> bool:
    """Сравнение двух datetime'ов с допуском ``_DATE_TOLERANCE``.

    ``None == None`` → True. ``None vs value`` → False.
    """
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    return abs(a - b) <= _DATE_TOLERANCE


def _norm_str(s: str | None) -> str | None:
    """``None`` остаётся None; иначе trim. ``""`` приравниваем к None."""
    if s is None:
        return None
    stripped = s.strip()
    return stripped or None
