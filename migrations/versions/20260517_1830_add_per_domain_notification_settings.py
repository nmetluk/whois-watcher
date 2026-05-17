"""add is_muted, notify_registrant_change, notify_problem to user_domains

Revision ID: 20260517_pernotif
Revises: 20260517_wishlist
Create Date: 2026-05-17 18:30:00.000000

Этап 11 — гранулярные настройки уведомлений (ADR 029):

- ``is_muted`` — kill-switch, при True подавляет все уведомления
  независимо от индивидуальных ``notify_*`` флагов. Заменяет
  computed-логику ``_is_muted`` из ``services/formatters.py``.
- ``notify_registrant_change`` — отдельный toggle для смены владельца
  (раньше was mapped на ``notify_registrar_change`` в Этапе 8).
- ``notify_problem`` — toggle для уведомлений об ошибках проверки.

Все три — defaults сохраняют backwards compat:
- ``is_muted=False`` — ничего не замьючено, поведение как раньше.
- ``notify_registrant_change=True`` — раньше шло через registrar_change;
  пользователи, которые НЕ отключали registrar_change, получат
  registrant-уведомления как и раньше.
- ``notify_problem=True`` — проблемы и так слались без условия.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260517_pernotif"
down_revision: str | None = "20260517_wishlist"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "user_domains",
        sa.Column(
            "notify_registrant_change",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.add_column(
        "user_domains",
        sa.Column(
            "notify_problem",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.add_column(
        "user_domains",
        sa.Column(
            "is_muted",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("user_domains", "is_muted")
    op.drop_column("user_domains", "notify_problem")
    op.drop_column("user_domains", "notify_registrant_change")
