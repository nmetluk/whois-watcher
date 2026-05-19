"""add dns_cache and dns toggles in user_domains

Revision ID: 20260519_dns
Revises: 20260517_ssl
Create Date: 2026-05-19 17:09:46.908221+00:00

Этап 14 (ADR 032) — DNS A/AAAA Monitoring (foundation):

- Новая таблица ``dns_cache`` — параллельно ``ssl_cache`` и ``whois_cache``,
  одна запись на домен (PK = domain text). Хранит A/AAAA/NS-записи,
  ASN-set, resolution_state, NS-mismatch state и scheduling-поля.
- 5 колонок на ``user_domains``:
    - ``track_dns`` (bool default true) — opt-out для DNS-мониторинга
    - ``notify_dns_a_change`` (bool default true)
    - ``notify_dns_aaaa_change`` (bool default true)
    - ``notify_dns_ns_change`` (bool default true) — info + critical (mismatch)
    - ``notify_dns_unreachable`` (bool default true)

Backwards compat: ``track_dns=true`` для всех существующих записей →
сразу после миграции бот начнёт проверять DNS по их доменам. Адаптивный
scheduler (14b/14c) ограничит batch.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260519_dns"
down_revision: str | None = "20260517_ssl"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # dns_cache ---------------------------------------------------------
    op.create_table(
        "dns_cache",
        sa.Column("domain", sa.Text(), nullable=False),
        # Scheduling
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_successful_check_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "next_check_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("last_changed_at", sa.DateTime(timezone=True), nullable=True),
        # DNS records
        sa.Column("a_records", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("aaaa_records", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("ns_records", postgresql.ARRAY(sa.Text()), nullable=True),
        # ASN enrichment — placeholder для v0.8.0 (rir2localdb v0.1.1
        # пока не отдаёт IP→ASN; полная сборка в v0.8.x).
        sa.Column(
            "asn_set",
            postgresql.ARRAY(sa.Integer()),
            nullable=True,
            comment="Unique ASNs from a_records + aaaa_records",
        ),
        # Resolution state
        sa.Column(
            "resolution_state",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'unknown'"),
            comment="resolved / mx_only / no_dns / error / unknown",
        ),
        sa.Column(
            "is_reachable",
            sa.Boolean(),
            nullable=True,
            comment="NULL пока не было ни одной проверки",
        ),
        sa.Column("resolver_used", sa.Text(), nullable=True),
        # NS-mismatch tracking — DNS-NS vs WHOIS-NS, критический сигнал.
        sa.Column(
            "ns_mismatch_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="DNS-NS != WHOIS-NS на момент последней проверки",
        ),
        # Failure tracking — параллельно ssl_cache.
        sa.Column(
            "fail_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("domain"),
    )
    op.create_index(
        "ix_dns_cache_next_check_at",
        "dns_cache",
        ["next_check_at"],
    )

    # user_domains: 5 boolean toggles для DNS-уведомлений ----------------
    op.add_column(
        "user_domains",
        sa.Column(
            "track_dns",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.add_column(
        "user_domains",
        sa.Column(
            "notify_dns_a_change",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.add_column(
        "user_domains",
        sa.Column(
            "notify_dns_aaaa_change",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.add_column(
        "user_domains",
        sa.Column(
            "notify_dns_ns_change",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.add_column(
        "user_domains",
        sa.Column(
            "notify_dns_unreachable",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )


def downgrade() -> None:
    op.drop_column("user_domains", "notify_dns_unreachable")
    op.drop_column("user_domains", "notify_dns_ns_change")
    op.drop_column("user_domains", "notify_dns_aaaa_change")
    op.drop_column("user_domains", "notify_dns_a_change")
    op.drop_column("user_domains", "track_dns")
    op.drop_index("ix_dns_cache_next_check_at", table_name="dns_cache")
    op.drop_table("dns_cache")
