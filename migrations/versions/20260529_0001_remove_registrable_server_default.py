"""Remove server_default from registrable_domain.

Revision ID: 20260529_remove_registrable_server_default
Revises: 20260529_registrable_domain
Create Date: 2026-05-29

TASK-0008 — убрать server_default с registrable_domain.
После того как код начал заполнять поле при вставке через PSL,
server_default на уровне БД не нужен и создаёт рассинхрон с моделью.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260529_remove_registrable_server_default"
down_revision: str | None = "20260529_registrable_domain"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Убираем server_default — поле теперь заполняется только кодом
    # через DomainRepository.create_for_user (вычисляет registrable_domain).
    op.alter_column("user_domains", "registrable_domain", server_default=None)


def downgrade() -> None:
    # Восстанавливаем server_default для отката.
    op.alter_column(
        "user_domains", "registrable_domain", server_default=sa.text("")
    )
