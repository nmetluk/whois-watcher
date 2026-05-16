"""add registrant fields to whois_cache

Revision ID: 20260516_registrant
Revises: 20260515_init
Create Date: 2026-05-16 23:10:00.000000

Этап 8 — расширенная карточка /whois с владельцем. Добавляем
денормализованные ``registrant_*`` колонки и JSONB ``contacts_data``
для полного списка контактов (admin/tech/abuse).

Заполняются автоматически при следующей плановой проверке домена
(``check_domain``-таска UPSERT'ит эти поля вместе с остальными). До
того как воркер дойдёт до конкретного домена, поля останутся NULL —
карточка просто не покажет блок «Владелец» (см. формattter, который
скрывает секцию для NULL).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260516_registrant"
down_revision: str | None = "20260515_init"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "whois_cache",
        sa.Column("registrant_name", sa.String(length=256), nullable=True),
    )
    op.add_column(
        "whois_cache",
        sa.Column("registrant_org", sa.String(length=256), nullable=True),
    )
    op.add_column(
        "whois_cache",
        sa.Column("registrant_country", sa.String(length=8), nullable=True),
    )
    op.add_column(
        "whois_cache",
        sa.Column("registrant_email", sa.String(length=256), nullable=True),
    )
    op.add_column(
        "whois_cache",
        sa.Column(
            "registrant_is_redacted",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "whois_cache",
        sa.Column("contacts_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("whois_cache", "contacts_data")
    op.drop_column("whois_cache", "registrant_is_redacted")
    op.drop_column("whois_cache", "registrant_email")
    op.drop_column("whois_cache", "registrant_country")
    op.drop_column("whois_cache", "registrant_org")
    op.drop_column("whois_cache", "registrant_name")
