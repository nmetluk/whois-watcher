"""Сравнение двух состояний DNS-записей (Этап 14, ADR 032).

По образцу ``src/ssl/diff.py``. Семантика флагов:

- ``a_changed`` — список IPv4 изменился (даже если ASN тот же)
- ``a_asn_changed`` — ASN-set изменился (true critical signal,
  не CDN noise)
- ``aaaa_changed`` / ``aaaa_asn_changed`` — то же для IPv6
- ``ns_changed`` — список NS изменился (любая смена)
- ``became_unreachable`` — был резолв, стал DNSError (или
  is_reachable=False)
- ``became_reachable`` — обратный переход

``compute_dns_diff(old=None, ...)`` всегда возвращает пустой
diff: первая проверка не может быть "изменением" (тот же
инвариант что в ``src/ssl/diff.py`` для SSL и в
``src/whois/diff.py`` для WHOIS).

NS-mismatch (DNS-NS vs WHOIS-NS) — отдельная функция
``detect_ns_mismatch``, вызывается в ``check_dns.py`` с WHOIS-NS
из ``whois_cache.name_servers`` (это отдельная колонка, не raw_data).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from src.dns_monitor.types import DNSError, DNSResult

if TYPE_CHECKING:
    from datetime import datetime

    from src.db.models import DNSCache


class _DNSCacheLike(Protocol):
    """Структурный протокол для DNSCache + тестовых фейков."""

    a_records: list[str] | None
    aaaa_records: list[str] | None
    ns_records: list[str] | None
    asn_set: list[int] | None
    is_reachable: bool | None
    last_checked_at: datetime | None


@dataclass(slots=True, kw_only=True)
class DNSDiff:
    """Что изменилось между двумя состояниями DNS."""

    a_changed: bool = False
    a_asn_changed: bool = False
    aaaa_changed: bool = False
    aaaa_asn_changed: bool = False
    ns_changed: bool = False
    became_unreachable: bool = False
    became_reachable: bool = False

    @property
    def has_any_changes(self) -> bool:
        return (
            self.a_changed
            or self.aaaa_changed
            or self.ns_changed
            or self.became_unreachable
            or self.became_reachable
        )

    @property
    def has_critical_changes(self) -> bool:
        """Critical changes — те, которые точно требуют внимания.

        ASN-смена (хостинг переехал) и became_unreachable — критичны.
        Простая смена IP в пределах того же ASN (CDN round-robin) —
        не критична. В v0.8.0 ASN всегда [] → ``has_critical_changes``
        отражает только became_unreachable.
        """
        return self.a_asn_changed or self.aaaa_asn_changed or self.became_unreachable


def compute_dns_diff(
    old: DNSCache | _DNSCacheLike | None,
    new: DNSResult,
    new_asn_set: list[int],
) -> DNSDiff:
    """Сравнивает старое состояние из БД и свежий resolve.

    ``old=None`` — первая проверка, пустой diff (first-fetch guard).
    ``old.last_checked_at is None`` — sparse bootstrap-строка,
    созданная ``dns_scheduler_tick`` до первого реального
    ``check_dns``; тоже трактуется как "первая проверка". Без этой
    ветки smoke-test 14e показал 38 ложных уведомлений
    (NULL-записи сравнивались как пустой список против реального
    резолва — давало ``a_changed``/``ns_changed``/``aaaa_changed``).
    Аналогия: WHOIS first-fetch fix v0.3.0 и
    ``not has_certificate`` в ``compute_ssl_diff``.

    NB: ``became_unreachable`` проверяется через ``old.is_reachable``
    — это ПЕРЕХОД, не состояние. На каждом retry в unreachable не
    шлём дубль уведомления (тот же инвариант что в ``ssl/diff.py``).
    """
    diff = DNSDiff()

    # First-fetch guard — нет старого состояния либо bootstrap-row.
    if old is None or old.last_checked_at is None:
        return diff

    # new — ошибка резолва
    if isinstance(new, DNSError):
        # invalid_domain / disabled — не считаем как unreachable
        # (это конфигурационные проблемы, не сетевые)
        if new.error_type not in ("invalid_domain", "disabled") and old.is_reachable is True:
            diff.became_unreachable = True
        return diff

    # new — успешный резолв. Reachable transition.
    if old.is_reachable is False and new.is_reachable:
        diff.became_reachable = True

    # A-записи (нормализованный sort для устойчивого сравнения)
    old_a = sorted(old.a_records or [])
    new_a = sorted(new.a_records)
    if old_a != new_a:
        diff.a_changed = True

    # AAAA-записи
    old_aaaa = sorted(old.aaaa_records or [])
    new_aaaa = sorted(new.aaaa_records)
    if old_aaaa != new_aaaa:
        diff.aaaa_changed = True

    # ASN-set (в v0.8.0 оба будут [], так что не сработает)
    old_asn = sorted(old.asn_set or [])
    new_asn_sorted = sorted(new_asn_set)
    if (
        (old_a or old_aaaa)
        and (new_a or new_aaaa)
        and old_asn
        and new_asn_sorted
        and old_asn != new_asn_sorted
    ):
        # ASN изменился — true critical signal для A и AAAA
        # (один общий ASN-set покрывает оба)
        diff.a_asn_changed = True
        diff.aaaa_asn_changed = True

    # NS-записи
    old_ns = sorted(old.ns_records or [])
    new_ns = sorted(new.ns_records)
    if old_ns != new_ns:
        diff.ns_changed = True

    return diff


def detect_ns_mismatch(dns_ns: list[str], whois_ns: list[str]) -> bool:
    """True если DNS-NS отличаются от WHOIS-NS.

    Critical security signal — несовпадение может означать угон,
    незавершённую миграцию или преступную перевязку DNS на
    стороне регистратора.

    Сравнение case-insensitive с нормализацией trailing dot
    (DNS обычно ``ns1.example.com.``, WHOIS — без точки).

    Если один из списков пуст — возвращает False (недостаточно
    данных для сравнения, не считаем mismatch).
    """
    if not dns_ns or not whois_ns:
        return False

    def normalize(ns: str) -> str:
        return ns.lower().rstrip(".")

    norm_dns = sorted(normalize(n) for n in dns_ns)
    norm_whois = sorted(normalize(n) for n in whois_ns)
    return norm_dns != norm_whois


__all__ = ["DNSDiff", "compute_dns_diff", "detect_ns_mismatch"]
