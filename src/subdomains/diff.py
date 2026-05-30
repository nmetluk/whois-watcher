"""Сравнение списков поддоменов (TASK-0028, ADR 038).

Используется задачей ``check_subdomains`` после enumeration: получив
свежий список поддоменов, сравниваем со старой записью из ``subdomain_enum_cache``
и решаем, надо ли поставить change-уведомление.

Семантика:
- ``new`` — поддомены, которые появились с последней проверки.
- ``removed`` — поддомены, которые исчезли.

Инвариант: порядок и дубликаты не влияют — работаем на множествах
(set). Входные списки уже нормализованы (lowercase, punycode, без wildcard)
из ADR 037 (parser).

``compute_subdomain_diff(old=None, …)`` всегда возвращает пустой diff:
первая проверка не может быть «изменением» (по образцу SSL, ADR 030).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True, kw_only=True)
class SubdomainDiff:
    """Что изменилось между двумя состояниями поддоменов."""

    new: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)

    @property
    def has_any_changes(self) -> bool:
        return bool(self.new or self.removed)


def compute_subdomain_diff(
    old: list[str] | None,
    new: list[str],
) -> SubdomainDiff:
    """Сравнивает старый и новый списки поддоменов.

    ``old=None`` — первая проверка, ничего не diff'имся.
    Игнорирует порядок и дубликаты (работа на set).

    Args:
        old: Список поддоменов из предыдущей проверки (может быть None)
        new: Свежий список поддоменов из enumeration

    Returns:
        Объект SubdomainDiff с new/removed списками
    """
    if old is None:
        # Первая проверка — не считаем изменением
        return SubdomainDiff()

    old_set = set(old)
    new_set = set(new)

    return SubdomainDiff(
        new=sorted(new_set - old_set),
        removed=sorted(old_set - new_set),
    )


__all__ = ["SubdomainDiff", "compute_subdomain_diff"]
