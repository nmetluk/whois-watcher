"""Сравнение двух состояний email-intel (TASK-0016, ADR 036).

Используется задачей ``check_email_intel`` после fetch'а: получив свежие
данные, сравниваем со старой записью из ``email_intel_cache`` и решаем,
надо ли поставить change-уведомление.

Семантика:
- ``mx_changed`` — изменился список MX-записей (host или priority)
- ``spf_changed`` — изменилась SPF-запись (режим или содержимое)
- ``dmarc_changed`` — изменился DMARC (policy/subpolicy/pct)
- ``dkim_changed`` — изменился список DKIM-селекторов
- ``became_unreachable`` — был reachable → ошибка DNS
- ``became_reachable`` — была ошибка → снова reachable

``compute_email_diff(old=None, …)`` всегда возвращает пустой diff:
первая проверка не может быть «изменением».
"""

from __future__ import annotations

from dataclasses import dataclass

from src.email_intel.types import (
    DKIMInfo,
    DMARCRecord,
    EmailIntelError,
    EmailIntelResult,
    EmailIntelResultOrError,
    MXRecord,
    SPFRecord,
)


@dataclass(slots=True, kw_only=True)
class EmailIntelDiff:
    """Что изменилось между двумя состояниями email-intel."""

    mx_changed: bool = False
    spf_changed: bool = False
    dmarc_changed: bool = False
    dkim_changed: bool = False
    became_unreachable: bool = False
    became_reachable: bool = False

    @property
    def has_any_changes(self) -> bool:
        """True если есть хотя бы одно изменение."""
        return (
            self.mx_changed
            or self.spf_changed
            or self.dmarc_changed
            or self.dkim_changed
            or self.became_unreachable
            or self.became_reachable
        )


def compute_email_diff(
    old: EmailIntelResult | None,
    new: EmailIntelResultOrError,
) -> EmailIntelDiff:
    """Сравнивает старое и новое состояние email-intel.

    Args:
        old: Предыдущее состояние (None для первой проверки)
        new: Новое состояние (результат или ошибка)

    Returns:
        EmailIntelDiff с флагами изменений

    Note:
        ``old=None`` — первая проверка, всегда пустой diff.
        ``new`` — ошибка: became_unreachable только при переходе reachable→error.
    """
    diff = EmailIntelDiff()

    if old is None:
        # Первая проверка — не считаем изменениями
        return diff

    # new — ошибка. became_unreachable — это **переход**:
    # фиксируем только если был reachable, иначе на каждом retry'е
    # шёл бы дубль.
    if isinstance(new, EmailIntelError):
        if new.error_type != "nxdomain" and old.is_reachable:
            diff.became_unreachable = True
        return diff

    # new — успешный результат, old был unreachable
    if not old.is_reachable and new.is_reachable:
        diff.became_reachable = True

    # Сравниваем MX-записи
    if _mx_records_changed(old.mx_records, new.mx_records):
        diff.mx_changed = True

    # Сравниваем SPF
    if _spf_changed(old.spf, new.spf):
        diff.spf_changed = True

    # Сравниваем DMARC
    if _dmarc_changed(old.dmarc, new.dmarc):
        diff.dmarc_changed = True

    # Сравниваем DKIM
    if _dkim_changed(old.dkim, new.dkim):
        diff.dkim_changed = True

    return diff


def _mx_records_changed(old: list[MXRecord], new: list[MXRecord]) -> bool:
    """Проверка изменения MX-записей.

    Сравнивает по (host, priority) парам. Порядок не важен.
    """
    old_pairs = {(r.host, r.priority) for r in old}
    new_pairs = {(r.host, r.priority) for r in new}
    return old_pairs != new_pairs


def _spf_changed(old: SPFRecord | None, new: SPFRecord | None) -> bool:
    """Проверка изменения SPF.

    Считается изменением если:
    - Один None, другой нет (появился/исчез)
    - Режим изменился
    - Сырая запись изменилась (даже если режим тот же)
    """
    if old is None and new is None:
        return False
    if (old is None) != (new is None):
        return True
    assert old is not None and new is not None  # для mypy
    return old.mode != new.mode or old.raw != new.raw


def _dmarc_changed(old: DMARCRecord | None, new: DMARCRecord | None) -> bool:
    """Проверка изменения DMARC.

    Сравнивает policy, subpolicy, pct.
    """
    if old is None and new is None:
        return False
    if (old is None) != (new is None):
        return True
    assert old is not None and new is not None  # для mypy
    return old.policy != new.policy or old.subpolicy != new.subpolicy or old.pct != new.pct


def _dkim_changed(old: DKIMInfo | None, new: DKIMInfo | None) -> bool:
    """Проверка изменения DKIM-селекторов.

    Сравнивает списки селекторов.
    """
    if old is None and new is None:
        return False
    if (old is None) != (new is None):
        return True
    assert old is not None and new is not None  # для mypy
    return set(old.selectors) != set(new.selectors)


__all__ = ["EmailIntelDiff", "compute_email_diff"]
