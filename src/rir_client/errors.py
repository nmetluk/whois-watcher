"""Error types for ``src.rir_client`` (ADR 031).

Two-tier model:

1. ``RIRError`` — returned (not raised) from ``lookup_ip``/``lookup_asn`` for
   recoverable failures: timeouts, network errors, 404 not_found, 5xx server
   errors, validation failures, disabled-by-settings. Callers pattern-match
   on ``kind`` to decide behaviour.

2. ``RIRUnreachable`` — raised only by ``healthcheck()`` and ``get_status()``.
   These are used in the ARQ cron health-check task where exception flow is
   more idiomatic than returning a sentinel.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ErrorKind = Literal[
    "unreachable",  # network failure: timeout, connect refused, DNS fail
    "not_found",  # 404 — IP/ASN not in any RIR allocation
    "bad_request",  # 400 — invalid input (caller bug)
    "server_error",  # 5xx — rir2localdb internal error
    "invalid_response",  # 200 но JSON-схема не матчит наши pydantic-модели
    "disabled",  # rir2localdb_enabled=False в settings
]


@dataclass(frozen=True, slots=True)
class RIRError:
    """Returned from ``lookup_*`` on failure — НЕ raise.

    Pattern-matching::

        result = await lookup_ip("8.8.8.8")
        match result:
            case IPAllocation():
                ...  # success
            case RIRError(kind="not_found"):
                ...  # IP не в RIR-аллокациях
            case RIRError(kind="unreachable"):
                ...  # сервис лёг — fallback / degrade
            case RIRError():
                ...  # прочие — лог и пропустить
    """

    kind: ErrorKind
    detail: str
    status_code: int | None = None


class RIRUnreachable(Exception):  # noqa: N818 — публичный API, имя стабильно
    """rir2localdb недоступен (network / non-200 / схема не парсится).

    Поднимается из ``healthcheck()`` и ``get_status()``. Cron-таска
    ``rir_health_check`` ловит и шлёт critical-alert в админ-канал.
    Lookup-функции вместо этого возвращают ``RIRError(kind='unreachable')``.
    """


__all__ = ["ErrorKind", "RIRError", "RIRUnreachable"]
