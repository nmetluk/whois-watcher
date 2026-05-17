"""Сравнение двух состояний SSL-сертификата (Этап 12, ADR 030).

Используется задачей ``check_ssl`` после fetch'а: получив свежий
сертификат, сравниваем со старой записью из ``ssl_cache`` и решаем,
надо ли поставить change-уведомление.

Семантика:

- ``not_after_changed`` — поменялась дата истечения (обычно — ротация).
- ``issuer_changed`` — поменялся CN или O издателя (смена CA).
- ``became_unreachable`` — был валидный сертификат, стал недоступен
  (TLS-handshake fail / connection refused / invalid cert).
- ``became_reachable`` — обратное (после периода недоступности
  снова отдаёт валидный cert).

Кейс ``no_https`` НЕ считается ``became_unreachable`` — это просто
«у домена нет HTTPS», валидное состояние без уведомления.

``compute_ssl_diff(old=None, …)`` всегда возвращает пустой diff:
первая проверка не может быть «изменением» (см. фикс после Этапа 9
для WHOIS — тут та же логика).
"""

from __future__ import annotations

from dataclasses import dataclass

from src.ssl.types import SSLCertificate, SSLError, SSLResult


@dataclass(slots=True, kw_only=True)
class SSLDiff:
    """Что изменилось между двумя состояниями SSL-сертификата."""

    not_after_changed: bool = False
    issuer_changed: bool = False
    became_unreachable: bool = False
    became_reachable: bool = False

    @property
    def has_any_changes(self) -> bool:
        return (
            self.not_after_changed
            or self.issuer_changed
            or self.became_unreachable
            or self.became_reachable
        )


def compute_ssl_diff(
    old: SSLCertificate | None,
    new: SSLResult,
) -> SSLDiff:
    """Сравнивает старое и новое состояние SSL-сертификата.

    ``old=None`` — первая проверка, ничего не diff'ится.
    ``old.has_certificate=False`` — у нас не было настоящих данных,
    тоже не diff'им (могла быть только метка «недоступен» или пусто).
    """
    diff = SSLDiff()
    if old is None or not old.has_certificate:
        # При первой проверке или при отсутствии прошлых валидных данных
        # — не считаем переход «нет → есть» изменением. Это покрывает
        # сценарий «только что включили SSL-мониторинг для домена».
        return diff

    # new — ошибка fetch'а. ``became_unreachable`` — это **переход**:
    # фирим только если было True, иначе на каждом retry'е шёл бы дубль.
    if isinstance(new, SSLError):
        if new.error_type != "no_https" and old.is_reachable:
            diff.became_unreachable = True
        return diff

    # new — успешный fetch без сертификата (странный кейс: TLS прошёл,
    # cert не получили). Считаем как unreachable — тоже только при переходе.
    if not new.has_certificate:
        if old.is_reachable:
            diff.became_unreachable = True
        return diff

    # Восстановление после периода unreachable (old был помечен как
    # is_reachable=False, но has_certificate=True ещё с прошлого
    # валидного состояния — теоретически возможно если задача только
    # помечает is_reachable). Прямой сигнал «снова работает».
    if not old.is_reachable and new.is_reachable:
        diff.became_reachable = True

    if old.not_after != new.not_after:
        diff.not_after_changed = True

    if (old.issuer_cn != new.issuer_cn) or (old.issuer_o != new.issuer_o):
        diff.issuer_changed = True

    return diff


__all__ = ["SSLDiff", "compute_ssl_diff"]
