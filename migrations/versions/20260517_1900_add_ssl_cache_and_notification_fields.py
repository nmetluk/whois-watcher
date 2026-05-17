"""add ssl_cache table and SSL notification fields

Revision ID: 20260517_ssl
Revises: 20260517_pernotif
Create Date: 2026-05-17 19:00:00.000000

Этап 12 (ADR 030) — SSL Certificate Monitoring:

- Новая таблица ``ssl_cache`` — параллельно ``whois_cache``, одна запись
  на домен (PK = domain text). Хранит парсенный X.509 + scheduling-поля.
- ``users.notify_ssl_days_before`` — глобальный default списка дней
  предупреждения (``{14, 7, 3, 1}``), параллельно ``notify_days``.
- 4 колонки на ``user_domains``:
    - ``track_ssl`` (bool default true) — opt-out для SSL-мониторинга
    - ``notify_ssl_expiry`` (bool default true) — toggle reminder'ов
    - ``notify_ssl_change_issuer`` (bool default true) — toggle change-notice
    - ``notify_ssl_days_override`` (int[] nullable) — per-domain override
      списка дней; NULL → используем user-level.

Backwards compat: ``track_ssl=true`` для всех существующих записей →
сразу после миграции бот начнёт проверять SSL по их доменам. Адаптивный
scheduler ограничен 50 доменов/тик, тики каждые 5 мин — большие
портфели (1000+) покроются за ~1.5–2 часа.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260517_ssl"
down_revision: str | None = "20260517_pernotif"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ssl_cache ---------------------------------------------------------
    op.create_table(
        "ssl_cache",
        sa.Column("domain", sa.Text(), nullable=False),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_successful_check_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "next_check_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("is_reachable", sa.Boolean(), nullable=True),
        sa.Column("has_certificate", sa.Boolean(), nullable=True),
        sa.Column("not_before", sa.DateTime(timezone=True), nullable=True),
        sa.Column("not_after", sa.DateTime(timezone=True), nullable=True),
        sa.Column("issuer_cn", sa.String(length=256), nullable=True),
        sa.Column("issuer_o", sa.String(length=256), nullable=True),
        sa.Column("subject_cn", sa.String(length=256), nullable=True),
        sa.Column(
            "subject_alt_names",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("serial_number", sa.String(length=128), nullable=True),
        sa.Column("fingerprint_sha256", sa.String(length=64), nullable=True),
        sa.Column("signature_algorithm", sa.String(length=64), nullable=True),
        sa.Column("fail_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("domain"),
    )
    op.create_index("ix_ssl_cache_next_check_at", "ssl_cache", ["next_check_at"])
    op.create_index("ix_ssl_cache_not_after", "ssl_cache", ["not_after"])

    # users.notify_ssl_days_before -------------------------------------
    op.add_column(
        "users",
        sa.Column(
            "notify_ssl_days_before",
            postgresql.ARRAY(sa.Integer()),
            nullable=False,
            server_default="{14,7,3,1}",
        ),
    )

    # user_domains: 4 новых колонки ------------------------------------
    op.add_column(
        "user_domains",
        sa.Column(
            "track_ssl",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.add_column(
        "user_domains",
        sa.Column(
            "notify_ssl_expiry",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.add_column(
        "user_domains",
        sa.Column(
            "notify_ssl_change_issuer",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.add_column(
        "user_domains",
        sa.Column(
            "notify_ssl_days_override",
            postgresql.ARRAY(sa.Integer()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("user_domains", "notify_ssl_days_override")
    op.drop_column("user_domains", "notify_ssl_change_issuer")
    op.drop_column("user_domains", "notify_ssl_expiry")
    op.drop_column("user_domains", "track_ssl")
    op.drop_column("users", "notify_ssl_days_before")
    op.drop_index("ix_ssl_cache_not_after", table_name="ssl_cache")
    op.drop_index("ix_ssl_cache_next_check_at", table_name="ssl_cache")
    op.drop_table("ssl_cache")
