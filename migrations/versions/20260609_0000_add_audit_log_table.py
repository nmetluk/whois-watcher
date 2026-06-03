"""add audit_log table (TASK-0057, ADR 042)

Revision ID: 20260609_audit_log
Revises: 20260531_email_deep_cache
Create Date: 2026-06-09 00:00:00.000000

TASK-0057 (ADR 042) — таблица audit_log для инцидентов (отдельная от system_events).

- id bigserial PK
- created_at timestamptz NOT NULL DEFAULT now() + index
- level text (info|warning|error|critical)
- category text (task_failure|rate_limit|admin_action|webhook|startup|other)
- actor text nullable (user_id или "system")
- message text
- context jsonb nullable

Индекс по (category, created_at).
Дефолты — валидным SQL (now()), без Python-литералов.
Миграция обратима (просто DROP TABLE + drop index).

Связанные: TASK-0061 (вписать audit() + retention cleanup).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260609_audit_log"
down_revision: str | None = "20260531_email_deep_cache"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("level", sa.String(length=16), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("actor", sa.Text(), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("context", postgresql.JSONB(), nullable=True),
    )

    # Индекс по категории + времени (для выборок по category и retention)
    op.create_index(
        "ix_audit_log_category_created",
        "audit_log",
        ["category", "created_at"],
    )

    # Отдельный индекс по created_at (как указано в спецификации таска)
    op.create_index(
        "ix_audit_log_created_at",
        "audit_log",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_audit_log_created_at", table_name="audit_log")
    op.drop_index("ix_audit_log_category_created", table_name="audit_log")
    op.drop_table("audit_log")
