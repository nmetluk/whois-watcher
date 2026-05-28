"""add registrable_domain and is_subdomain to user_domains

Revision ID: 20260529_registrable_domain
Revises: 20260519_dns_cache
Create Date: 2026-05-29 00:00:00.000000

TASK-0003 (подэтап 2b) — схема поддоменов.

Добавляет два поля в ``user_domains``:
- ``registrable_domain`` (Text, NOT NULL) — eTLD+1, для WHOIS-джойнов
- ``is_subdomain`` (Boolean, NOT NULL, default false) — признак поддомена

Backfill существующих строк: ``registrable_domain = domain`` (все текущие
домены — apex), ``is_subdomain = false``. Также добавляется индекс на
``registrable_domain`` для WHOIS-джойнов.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260529_registrable_domain"
down_revision: str | None = "20260519_dns_cache"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Добавляем колонки (NOT NULL с дефолтом, чтобы существующие строки не помирали)
    op.add_column(
        "user_domains",
        sa.Column(
            "registrable_domain",
            sa.Text(),
            nullable=False,
            server_default=sa.text(""),
        ),
    )
    op.add_column(
        "user_domains",
        sa.Column(
            "is_subdomain",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    # Backfill: для существующих строк registrable_domain = domain
    op.execute(
        sa.text('UPDATE user_domains SET registrable_domain = domain WHERE registrable_domain = ""')
    )

    # Добавляем индекс на registrable_domain для WHOIS-джойнов
    op.create_index(
        "ix_user_domains_registrable_domain",
        "user_domains",
        ["registrable_domain"],
    )


def downgrade() -> None:
    op.drop_index("ix_user_domains_registrable_domain", table_name="user_domains")
    op.drop_column("user_domains", "is_subdomain")
    op.drop_column("user_domains", "registrable_domain")
