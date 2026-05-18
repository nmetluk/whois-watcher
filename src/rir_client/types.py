"""Pydantic models for rir2localdb API responses (v0.1.1).

См. https://github.com/nmetluk/rir2localdb для API-контракта.

Дизайн-решение: блок ``rpsl`` в ``IPAllocation`` и ``ASNAllocation`` оставлен
как ``dict[str, Any]`` для v0.7. Типизированный доступ (RpslInetnum,
RpslOrganisation и т. п.) добавится в v0.8, когда DNS-мониторинг реально
начнёт применять organisation-данные. Это держит surface v0.7 минимальной
и устойчивой к доработкам RPSL-ETL в rir2localdb (на v0.1.1 в RPSL для
не-RIPE блоков доминируют APNIC IANA-NETBLOCK placeholder'ы).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class IPAllocation(BaseModel):
    """Ответ ``GET /v1/ip/{addr}``.

    Поля зеркалят ``IpLookupResponse`` из openapi.json rir2localdb v0.1.1.
    """

    address: str
    family: Literal[4, 6]
    rir: str
    cc: str | None = None
    start: str
    value: int
    prefix_length: int | None = None
    status: str
    allocated_on: date | None = None
    opaque_id: str | None = None
    first_seen_run: int
    last_seen_run: int
    is_stale: bool = False
    # RPSL — untyped в v0.7, см. module docstring.
    rpsl: dict[str, Any] | None = None


class ASNAllocation(BaseModel):
    """Ответ ``GET /v1/asn/{num}``.

    Поля зеркалят ``AsnLookupResponse`` из openapi.json rir2localdb v0.1.1.
    """

    asn: int
    rir: str
    cc: str | None = None
    start_asn: int
    count: int
    status: str
    allocated_on: date | None = None
    opaque_id: str | None = None
    first_seen_run: int
    last_seen_run: int
    is_stale: bool = False
    rpsl: dict[str, Any] | None = None


class SyncRun(BaseModel):
    """Один ETL-прогон внутри ``RIRStatus.latest_sync_run``.

    Используется ``rir_health_check`` для проверки свежести данных.
    """

    id: int
    tier: str
    started_at: datetime
    finished_at: datetime | None = None
    status: str
    stats: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class Source(BaseModel):
    """Per-RIR freshness конкретного источника (delegated/RPSL-файла)."""

    url: str
    rir: str
    kind: Literal["delegated", "rpsl-gz", "rpsl-split-gz"]
    last_status: str
    last_fetched_at: datetime | None = None
    last_parsed_at: datetime | None = None
    last_size: int = 0


class RIRStatus(BaseModel):
    """Ответ ``GET /v1/status``."""

    latest_sync_run: SyncRun | None = None
    sources: list[Source] = Field(default_factory=list)
    db_alive: bool


__all__ = [
    "ASNAllocation",
    "IPAllocation",
    "RIRStatus",
    "Source",
    "SyncRun",
]
