"""add email_deep_cache table (TASK-0039, ADR 040)

Revision ID: 20260531_email_deep_cache
Revises: 20260530_subdomain_monitor
Create Date: 2026-05-31 00:00:00.000000

TASK-0039 (ADR 040) — кэш deep email (SPF recursion, MTA-STS, TLS-RPT, DANE, BIMI).

Таблица ``email_deep_cache``:
- PK по ``domain``
- JSONB-поля под результаты из deep_types (spf, mta_sts, tls_rpt, dane, bimi)
- Scheduling: fetched_at, next_check_at (короткий TTL для on-demand)
- Reachability + failure tracking (graceful degradation)

Дефолты — валидным SQL (now(), 0), без Python-литералов.
Миграция обратима (просто DROP TABLE).

Связанные: TASK-0038 (коллекторы), TASK-0041 (UX on-demand).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260531_email_deep_cache"
down_revision: str | None = "20260530_subdomain_monitor"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "email_deep_cache",
        sa.Column(
            "domain",
            sa.Text(),
            primary_key=True,
            comment="Домен (punycode), для которого собран deep email",
        ),
        # Deep results (сериализованные dataclass'ы из TASK-0038)
        sa.Column(
            "spf",
            postgresql.JSONB(),
            nullable=True,
            comment="SpfResolution: sources[], lookup_count, exceeds_limit",
        ),
        sa.Column(
            "mta_sts",
            postgresql.JSONB(),
            nullable=True,
            comment="MtaStsResult: txt_present, policy_mode, mx[], max_age, reachable",
        ),
        sa.Column(
            "tls_rpt",
            postgresql.JSONB(),
            nullable=True,
            comment="TlsRptResult: present, rua",
        ),
        sa.Column(
            "dane",
            postgresql.JSONB(),
            nullable=True,
            comment="DaneResult: host_tlsa {host: bool}",
        ),
        sa.Column(
            "bimi",
            postgresql.JSONB(),
            nullable=True,
            comment="BimiResult: present, logo_url, vmc_url",
        ),
        # Scheduling (short TTL, on-demand)
        sa.Column(
            "fetched_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
            comment="Когда последний раз запускали deep сбор",
        ),
        sa.Column(
            "next_check_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
            comment="Когда можно снова запустить on-demand deep (короткий TTL)",
        ),
        # Reachability / failure
        sa.Column(
            "is_reachable",
            sa.Boolean(),
            nullable=True,
            comment="True если deep сбор прошёл без критических ошибок",
        ),
        sa.Column(
            "fail_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
            comment="Количество последовательных неудач deep сбора",
        ),
        sa.Column(
            "last_error",
            sa.Text(),
            nullable=True,
            comment="Текст последней ошибки (если была)",
        ),
    )

    # Индекс для TTL-проверок (хотя в v0.13 scheduler'а нет — для будущих или ad-hoc)
    op.create_index(
        "ix_email_deep_cache_next_check_at",
        "email_deep_cache",
        ["next_check_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_email_deep_cache_next_check_at", table_name="email_deep_cache")
    op.drop_table("email_deep_cache")
