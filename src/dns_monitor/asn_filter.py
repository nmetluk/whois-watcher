"""ASN-обогащение IP из DNS-записей (Этап 14, ADR 032).

ВАЖНОЕ ПРИМЕЧАНИЕ: rir2localdb v0.1.1 в ``/v1/ip/{addr}`` НЕ возвращает
ASN — это IP allocation lookup, не ASN lookup. Endpoint ``/v1/asn/{num}``
требует знать ASN заранее.

Для v0.8.0 функция возвращает пустой list. ``compute_dns_diff``
работает без ASN-фильтра (любая смена IP → ``a_changed=True``).
Это OK как baseline — пользователи получат больше уведомлений
о CDN round-robin, но не пропустят реальные смены хостинга.

В v0.8.x — координация с владельцем rir2localdb на добавление
endpoint ``/v1/ip/{addr}/asn`` через RPSL ``inetnum.origin``. После
этого функция начнёт работать без code change в client.py /
check_dns.py.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable

logger = logging.getLogger(__name__)


async def enrich_with_asn(ips: Iterable[str]) -> list[int]:
    """Lookup ASN для каждого IP, вернуть отсортированный list
    уникальных ASN.

    v0.8.0: возвращает пустой list (rir2localdb не поддерживает
    IP→ASN). v0.8.x активирует реальный lookup без изменений
    callers.
    """
    ip_list = list(ips)
    if not ip_list:
        return []

    # TODO в v0.8.x: использовать rir_client.lookup_ip_asn()
    # когда rir2localdb добавит endpoint
    return []


__all__ = ["enrich_with_asn"]
