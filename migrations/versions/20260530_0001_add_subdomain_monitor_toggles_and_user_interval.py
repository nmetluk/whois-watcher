"""add subdomain monitor toggles and user interval (ADR 038)

Revision ID: 20260530_subdomain_monitor
Revises: 20260530_wishlist
Create Date: 2026-05-30 00:01:00.000000

TASK-0027 (ADR 038) — схема для мониторинга поддоменов.

Добавляет 5 полей:
- ``users.subdomain_check_interval_days`` (int, default 7) — per-user интервал
- ``user_domains.track_subdomains`` (bool, default false) — opt-in toggle
- ``user_domains.notify_subdomain_new`` (bool, default true) — алерт на новые
- ``user_domains.notify_subdomain_removed`` (bool, default true) — алерт на исчезнувшие
- ``user_domains.subdomain_check_interval_override`` (int, nullable) — per-domain override

Дефолты — валидным SQL (false/true/7), тест на Postgres (TASK-0009).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260530_subdomain_monitor"
down_revision: str | None = "20260530_wishlist"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # users.subdomain_check_interval_days
    op.add_column(
        "users",
        sa.Column(
            "subdomain_check_interval_days",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("7"),
        ),
    )

    # user_domains.track_subdomains (opt-in, default false)
    op.add_column(
        "user_domains",
        sa.Column(
            "track_subdomains",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    # user_domains.notify_subdomain_new (default true)
    op.add_column(
        "user_domains",
        sa.Column(
            "notify_subdomain_new",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )

    # user_domains.notify_subdomain_removed (default true)
    op.add_column(
        "user_domains",
        sa.Column(
            "notify_subdomain_removed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )

    # user_domains.subdomain_check_interval_override (nullable, no default)
    op.add_column(
        "user_domains",
        sa.Column(
            "subdomain_check_interval_override",
            sa.Integer(),
            nullable=True,
        ),
    )


def downgrade() -> None:
    # Удаляем в обратном порядке
    op.drop_column("user_domains", "subdomain_check_interval_override")
    op.drop_column("user_domains", "notify_subdomain_removed")
    op.drop_column("user_domains", "notify_subdomain_new")
    op.drop_column("user_domains", "track_subdomains")
    op.drop_column("users", "subdomain_check_interval_days")
