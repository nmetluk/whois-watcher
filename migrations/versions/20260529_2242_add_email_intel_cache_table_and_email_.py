"""add email_intel_cache table and email notification toggles

Revision ID: 20260529_email_intel
Revises: 20260529_registrable_domain
Create Date: 2026-05-29 22:42:00.000000

TASK-0015 (ADR 036) — схема email_intel_cache и toggle'ы уведомлений.

Создаёт таблицу ``email_intel_cache`` для хранения email/policy-записей
(MX/SPF/DKIM/DMARC) и добавляет per-domain toggle'ы уведомлений.

Таблица ``email_intel_cache``:
- PK по ``domain`` (как ssl_cache, dns_cache, whois_cache)
- Scheduling-поля: fetched_at, last_successful_check_at, next_check_at
- Reachability: is_reachable
- Email-записи: mx_records (JSONB), spf_record, spf_mode, dmarc_policy,
  dmarc_subpolicy, dmarc_pct, dkim_selectors (JSONB)
- Failure tracking: fail_count, last_error

Toggle'ы в ``user_domains``:
- ``track_email`` (default true) — включать домен в email-intel проверки
- ``notify_email_change`` (default true) — уведомлять об изменениях email/policy
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260529_email_intel"
down_revision: str | None = "20260529_registrable_domain"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Создаём таблицу email_intel_cache
    op.create_table(
        "email_intel_cache",
        sa.Column(
            "domain",
            sa.Text(),
            primary_key=True,
        ),
        # Scheduling
        sa.Column(
            "fetched_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "last_successful_check_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "next_check_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        # Reachability
        sa.Column(
            "is_reachable",
            sa.Boolean(),
            nullable=True,
            comment="True если DNS-запроси успешны, False при ошибках, NULL до первой проверки",
        ),
        # MX records
        sa.Column(
            "mx_records",
            sa.JSONB(),
            nullable=True,
            comment='Список MX-записей [{"priority": 10, "host": "mail.example.com"}]',
        ),
        # SPF
        sa.Column(
            "spf_record",
            sa.Text(),
            nullable=True,
            comment="Сырая SPF-запись",
        ),
        sa.Column(
            "spf_mode",
            sa.Text(),
            nullable=True,
            comment="Режим SPF: none, neutral, pass, fail, softfail, temperror, permerror",
        ),
        # DMARC
        sa.Column(
            "dmarc_policy",
            sa.Text(),
            nullable=True,
            comment="DMARC policy: none, quarantine, reject",
        ),
        sa.Column(
            "dmarc_subpolicy",
            sa.Text(),
            nullable=True,
            comment="DMARC sp/p: none, quarantine, reject",
        ),
        sa.Column(
            "dmarc_pct",
            sa.Integer(),
            nullable=True,
            comment="DMARC pct (0-100), NULL = дефолт 100",
        ),
        # DKIM
        sa.Column(
            "dkim_selectors",
            sa.JSONB(),
            nullable=True,
            comment="Список найденных DKIM-селекторов",
        ),
        # Failure tracking
        sa.Column(
            "fail_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "last_error",
            sa.Text(),
            nullable=True,
        ),
    )

    # Индекс для scheduler (как в ssl_cache, dns_cache)
    op.create_index(
        "ix_email_intel_cache_next_check_at",
        "email_intel_cache",
        ["next_check_at"],
    )

    # Добавляем toggle'ы в user_domains
    # track_email — включать домен в email-intel проверки
    op.add_column(
        "user_domains",
        sa.Column(
            "track_email",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    # notify_email_change — уведомлять об изменениях email/policy
    op.add_column(
        "user_domains",
        sa.Column(
            "notify_email_change",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )


def downgrade() -> None:
    # Удаляем toggle'ы из user_domains
    op.drop_column("user_domains", "notify_email_change")
    op.drop_column("user_domains", "track_email")

    # Удаляем индекс и таблицу email_intel_cache
    op.drop_index("ix_email_intel_cache_next_check_at", table_name="email_intel_cache")
    op.drop_table("email_intel_cache")
