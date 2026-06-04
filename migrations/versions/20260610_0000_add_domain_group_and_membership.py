"""add domain_group + user_domain_group (TASK-0073, ADR 043)

Revision ID: 20260610_domain_group
Revises: 20260609_audit_log
Create Date: 2026-06-10

Группы/теги доменов:
- domain_group: id, user_id (FK users, cascade), name, kind (client|personal),
  color (hue a0-a7), icon (msymbol), created_at=now()
- user_domain_group: составной PK (user_domain_id, group_id), FKs с ON DELETE CASCADE,
  индекс по group_id.

SQL-литералы в server_default (sa.text("now()")), round-trip на Postgres.
См. TASK-0073, MIGRATIONS.md, TASK-0008/0009 уроки.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260610_domain_group"
down_revision: str | None = "20260609_audit_log"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # domain_group — группы пользователя
    op.create_table(
        "domain_group",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("color", sa.Text(), nullable=True),
        sa.Column("icon", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_domain_group_user_id", "domain_group", ["user_id"], unique=False)

    # user_domain_group — membership many-to-many (composite PK)
    op.create_table(
        "user_domain_group",
        sa.Column("user_domain_id", sa.BigInteger(), nullable=False),
        sa.Column("group_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(["user_domain_id"], ["user_domains.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["group_id"], ["domain_group.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_domain_id", "group_id"),
    )
    op.create_index(
        "ix_user_domain_group_group_id", "user_domain_group", ["group_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_user_domain_group_group_id", table_name="user_domain_group")
    op.drop_table("user_domain_group")
    op.drop_index("ix_domain_group_user_id", table_name="domain_group")
    op.drop_table("domain_group")
