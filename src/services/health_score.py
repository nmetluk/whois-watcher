"""Health score computation (single source of truth).

Formula ported from design/webapp/v1/app/data.js (seed generator block `let health=100…`)
for consistency between backend API responses and any frontend.

No random jitter in production computation (jitter was only for demo seeds).
"""

from __future__ import annotations

from dataclasses import dataclass, field

# "Плохие" EPP-статусы, дающие сильный штраф (как в дизайн-формуле).
_BAD_FLAGS: frozenset[str] = frozenset(
    {"clientHold", "serverHold", "pendingDelete", "redemptionPeriod", "BLOCKED", "failed"}
)


@dataclass(slots=True)
class HealthInputs:
    """Inputs needed to compute health (aggregated from whois/ssl/dns/email caches)."""

    no_data: bool = False
    days_left: int | None = None  # from whois expires vs now; can be negative
    has_ssl: bool = False
    ssl_days_left: int | None = None
    spf_ok: bool = False
    dmarc: str | None = None  # 'none' | 'quarantine' | 'reject' | None
    dnssec: bool = False
    flags: list[str] = field(default_factory=list)


def compute_health_score(inputs: HealthInputs) -> int:
    """Compute 0..100 health score.

    Matches the design formula exactly (penalties + clamp), minus the demo jitter.
    """
    if inputs.no_data:
        return 0

    health = 100

    dl = inputs.days_left
    if dl is not None:
        if dl < 0:
            health -= 60
        elif dl < 7:
            health -= 38
        elif dl < 30:
            health -= 20
        elif dl < 90:
            health -= 6

    if inputs.has_ssl:
        sdl = inputs.ssl_days_left
        if sdl is not None:
            if sdl < 0:
                health -= 22
            elif sdl < 14:
                health -= 12
    else:
        health -= 10

    if not inputs.spf_ok:
        health -= 6

    if not inputs.dmarc:
        health -= 8
    elif inputs.dmarc == "none":
        health -= 4

    if not inputs.dnssec:
        health -= 4

    if set(inputs.flags) & _BAD_FLAGS:
        health -= 30

    # No + int(-3,3) here — production is deterministic.
    return max(0, min(100, health))
