"""initial schema

Revision ID: 20260515_init
Revises:
Create Date: 2026-05-15 23:30:00.000000

Создаёт базовую схему БД: users, user_domains, whois_cache,
sent_notifications, domain_changes, system_events. Условные индексы
(``WHERE next_check_at IS NOT NULL``, ``WHERE severity IN ...``) добавлены
вручную — autogenerate Alembic их обычно не подхватывает.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260515_init"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # users
    # ------------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), nullable=False, autoincrement=True),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.Text(), nullable=True),
        sa.Column("language", sa.Text(), nullable=False, server_default="ru"),
        sa.Column(
            "timezone", sa.Text(), nullable=False, server_default="Europe/Moscow"
        ),
        sa.Column(
            "notify_days",
            postgresql.ARRAY(sa.Integer()),
            nullable=False,
            server_default="{30,7,1}",
        ),
        sa.Column(
            "notify_at_hour", sa.Integer(), nullable=False, server_default="9"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "last_active_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "is_blocked", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("telegram_id", name="uq_users_telegram_id"),
    )
    op.create_index("ix_users_telegram_id", "users", ["telegram_id"])

    # ------------------------------------------------------------------
    # user_domains
    # ------------------------------------------------------------------
    op.create_table(
        "user_domains",
        sa.Column("id", sa.BigInteger(), nullable=False, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("domain", sa.Text(), nullable=False),
        sa.Column("notify_days", postgresql.ARRAY(sa.Integer()), nullable=True),
        sa.Column(
            "notify_expiry",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "notify_ns_change",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "notify_registrar_change",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "notify_status_change",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "last_problem_notified_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "added_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE", name="fk_user_domains_user_id"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "domain", name="uq_user_domains_user_domain"
        ),
    )
    op.create_index("ix_user_domains_user_id", "user_domains", ["user_id"])
    op.create_index("ix_user_domains_domain", "user_domains", ["domain"])

    # ------------------------------------------------------------------
    # whois_cache
    # ------------------------------------------------------------------
    op.create_table(
        "whois_cache",
        sa.Column("domain", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at_registrar", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at_registrar", sa.DateTime(timezone=True), nullable=True),
        sa.Column("registrar", sa.Text(), nullable=True),
        sa.Column("status", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("name_servers", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("raw_data", postgresql.JSONB(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "last_successful_fetch_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column("next_check_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "fail_count", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("domain"),
    )
    # Условный индекс: только активные next_check_at.
    op.create_index(
        "ix_whois_cache_next_check_at",
        "whois_cache",
        ["next_check_at"],
        postgresql_where=sa.text("next_check_at IS NOT NULL"),
    )
    op.create_index(
        "ix_whois_cache_expires_at", "whois_cache", ["expires_at"]
    )

    # ------------------------------------------------------------------
    # sent_notifications
    # ------------------------------------------------------------------
    op.create_table(
        "sent_notifications",
        sa.Column("id", sa.BigInteger(), nullable=False, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("domain", sa.Text(), nullable=False),
        sa.Column("notification_type", sa.String(length=32), nullable=False),
        sa.Column("days_before", sa.Integer(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "sent_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
            name="fk_sent_notifications_user_id",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "domain",
            "notification_type",
            "days_before",
            "expires_at",
            name="uq_sent_notifications_dedup",
        ),
    )
    op.create_index(
        "ix_sent_notifications_user_domain",
        "sent_notifications",
        ["user_id", "domain"],
    )

    # ------------------------------------------------------------------
    # domain_changes
    # ------------------------------------------------------------------
    op.create_table(
        "domain_changes",
        sa.Column("id", sa.BigInteger(), nullable=False, autoincrement=True),
        sa.Column("domain", sa.Text(), nullable=False),
        sa.Column("change_type", sa.String(length=32), nullable=False),
        sa.Column("old_value", postgresql.JSONB(), nullable=True),
        sa.Column("new_value", postgresql.JSONB(), nullable=True),
        sa.Column(
            "detected_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_domain_changes_domain_detected",
        "domain_changes",
        ["domain", "detected_at"],
    )

    # ------------------------------------------------------------------
    # system_events
    # ------------------------------------------------------------------
    op.create_table(
        "system_events",
        sa.Column("id", sa.BigInteger(), nullable=False, autoincrement=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("details", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_system_events_type_created",
        "system_events",
        ["event_type", "created_at"],
    )
    op.create_index(
        "ix_system_events_severity_created",
        "system_events",
        ["severity", "created_at"],
        postgresql_where=sa.text("severity IN ('error', 'critical')"),
    )


def downgrade() -> None:
    # Порядок: сначала таблицы с FK, потом users (на которую они ссылаются).
    op.drop_index(
        "ix_system_events_severity_created", table_name="system_events"
    )
    op.drop_index("ix_system_events_type_created", table_name="system_events")
    op.drop_table("system_events")

    op.drop_index(
        "ix_domain_changes_domain_detected", table_name="domain_changes"
    )
    op.drop_table("domain_changes")

    op.drop_index(
        "ix_sent_notifications_user_domain", table_name="sent_notifications"
    )
    op.drop_table("sent_notifications")

    op.drop_index("ix_whois_cache_expires_at", table_name="whois_cache")
    op.drop_index("ix_whois_cache_next_check_at", table_name="whois_cache")
    op.drop_table("whois_cache")

    op.drop_index("ix_user_domains_domain", table_name="user_domains")
    op.drop_index("ix_user_domains_user_id", table_name="user_domains")
    op.drop_table("user_domains")

    op.drop_index("ix_users_telegram_id", table_name="users")
    op.drop_table("users")
