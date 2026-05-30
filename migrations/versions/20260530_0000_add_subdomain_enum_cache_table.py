"""add subdomain_enum_cache table (ADR 037)

Revision ID: 20260530_subdomain_enum
Revises: 20260529_email_intel
Create Date: 2026-05-30 00:00:00.000000

TASK-0022 (ADR 037) — схема subdomain_enum_cache для кэширования результатов
enumeration через crt.sh.

Создаёт таблицу ``subdomain_enum_cache`` для хранения найденных поддоменов
per registrable-домен. Повторные вызовы ``/subdomains`` в окне TTL не бьют crt.sh.

Таблица ``subdomain_enum_cache``:
- PK по ``registrable_domain`` (eTLD+1, ADR 035)
- ``subdomains`` (JSONB) — список найденных поддоменов (нормализованных)
- Scheduling-поля: fetched_at, next_check_at
- Reachability: is_reachable
- Failure tracking: fail_count, last_error
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260530_subdomain_enum"
down_revision: str | None = "20260529_email_intel"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Создаём таблицу subdomain_enum_cache
    op.create_table(
        "subdomain_enum_cache",
        sa.Column(
            "registrable_domain",
            sa.Text(),
            primary_key=True,
            comment="Registrable-домен (eTLD+1, ADR 035)",
        ),
        # Subdomains (результат enumeration)
        sa.Column(
            "subdomains",
            postgresql.JSONB(),
            nullable=True,
            comment="Список найденных поддоменов (нормализованных: lowercase, punycode, без wildcard)",
        ),
        # Scheduling
        sa.Column(
            "fetched_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
            comment="Когда последний раз запрашивали у crt.sh",
        ),
        sa.Column(
            "next_check_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
            comment="Когда можно снова обновить (TTL кэша)",
        ),
        # Reachability
        sa.Column(
            "is_reachable",
            sa.Boolean(),
            nullable=True,
            comment="True если crt.sh доступен, False при ошибках, NULL до первой проверки",
        ),
        # Failure tracking
        sa.Column(
            "fail_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
            comment="Количество последовательных неудач",
        ),
        sa.Column(
            "last_error",
            sa.Text(),
            nullable=True,
            comment="Текст последней ошибки (если была)",
        ),
    )

    # Индекс для scheduler (как в ssl_cache, dns_cache, email_intel_cache)
    op.create_index(
        "ix_subdomain_enum_cache_next_check_at",
        "subdomain_enum_cache",
        ["next_check_at"],
    )


def downgrade() -> None:
    # Удаляем индекс и таблицу subdomain_enum_cache
    op.drop_index("ix_subdomain_enum_cache_next_check_at", table_name="subdomain_enum_cache")
    op.drop_table("subdomain_enum_cache")
