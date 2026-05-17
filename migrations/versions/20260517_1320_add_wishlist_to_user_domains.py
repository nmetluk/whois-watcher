"""add is_wishlist to user_domains

Revision ID: 20260517_wishlist
Revises: 20260516_registrant
Create Date: 2026-05-17 13:20:00.000000

Этап 9 — wishlist. Один булев флаг на ``user_domains``: если ``True``,
пользователь ждёт когда домен освободится (а не отслеживает обычным
образом). Дефолт — ``false``, никакие существующие подписки не ломаются.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260517_wishlist"
down_revision: str | None = "20260516_registrant"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "user_domains",
        sa.Column(
            "is_wishlist",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("user_domains", "is_wishlist")
