"""add wishlist table and migrate data (ADR 039 TASK-0031)

Revision ID: 20260530_wishlist
Revises: 20260530_subdomain_enum
Create Date: 2026-05-30 20:47:53.563648+00:00

TASK-0031 (ADR 039) — separate wishlist table.

Развязывает «слежение» (user_domains) и «wishlist» в две независимые
сущности на уровне схемы. После миграции домен может одновременно быть
и в /list, и в /wishlist.

Миграция:
1. Создаёт таблицу wishlist с полями: id, user_id, domain, registrable_domain,
   is_subdomain, added_at, last_notified_at
2. Переносит данные из user_domains WHERE is_wishlist = true
3. Удаляет wishlist-строки из user_domains
4. Удаляет колонку is_wishlist из user_domains

Обратимость (downgrade):
1. Восстанавливает колонку is_wishlist в user_domains
2. Переносит данные из wishlist обратно в user_domains (с is_wishlist=true,
   гася notify_* флаги как делал старый add_to_wishlist)
3. Удаляет таблицу wishlist
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260530_wishlist"
down_revision: str | None = "20260530_subdomain_enum"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Создаём таблицу wishlist
    op.create_table(
        "wishlist",
        sa.Column(
            "id",
            sa.BigInteger(),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            nullable=False,
            comment="ID пользователя (FK → users.id ON DELETE CASCADE)",
        ),
        sa.Column(
            "domain",
            sa.Text(),
            nullable=False,
            comment="Домен в punycode (нормализованный)",
        ),
        sa.Column(
            "registrable_domain",
            sa.Text(),
            nullable=False,
            comment="Registrable-домен (eTLD+1, ADR 035) для WHOIS-джойна",
        ),
        sa.Column(
            "is_subdomain",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="Признак поддомена: True если domain != registrable_domain",
        ),
        sa.Column(
            "added_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
            comment="Когда добавлен в wishlist",
        ),
        sa.Column(
            "last_notified_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
            comment="Когда последнее уведомление об освобождении (для одноразовости)",
        ),
        sa.PrimaryKeyConstraint("id", name="wishlist_pkey"),
        sa.UniqueConstraint("user_id", "domain", name="uq_wishlist_user_domain"),
        comment="Wishlist: домены, за которыми пользователь следит (ожидание освобождения)",
    )
    # Индексы
    op.create_index("ix_wishlist_user_id", "wishlist", ["user_id"])
    op.create_index("ix_wishlist_domain", "wishlist", ["domain"])
    op.create_index("ix_wishlist_registrable_domain", "wishlist", ["registrable_domain"])

    # FK на users.id (after table creation, PostgreSQL syntax)
    op.execute(
        """
        ALTER TABLE wishlist
        ADD CONSTRAINT wishlist_user_id_fkey
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        """
    )

    # 2. Переносим данные из user_domains WHERE is_wishlist = true
    op.execute(
        """
        INSERT INTO wishlist (user_id, domain, registrable_domain, is_subdomain, added_at)
        SELECT user_id, domain, registrable_domain, is_subdomain, added_at
        FROM user_domains
        WHERE is_wishlist = true
        """
    )

    # 3. Удаляем wishlist-строки из user_domains
    op.execute("DELETE FROM user_domains WHERE is_wishlist = true")

    # 4. Удаляем колонку is_wishlist из user_domains
    op.drop_column("user_domains", "is_wishlist")


def downgrade() -> None:
    # 1. Восстанавливаем колонку is_wishlist в user_domains
    op.add_column(
        "user_domains",
        sa.Column(
            "is_wishlist",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    # 2. Переносим данные из wishlist обратно в user_domains
    # Используем только существующие колонки (без устаревших subdomain полей)
    op.execute(
        """
        INSERT INTO user_domains (
            user_id, domain, registrable_domain, is_subdomain,
            added_at, is_wishlist,
            notify_days, notify_expiry, notify_ns_change,
            notify_registrar_change, notify_status_change, notify_registrant_change,
            notify_problem, is_muted,
            track_ssl, notify_ssl_expiry, notify_ssl_change_issuer, notify_ssl_days_override,
            track_dns, notify_dns_a_change, notify_dns_aaaa_change,
            notify_dns_ns_change, notify_dns_unreachable,
            track_email, notify_email_change
        )
        SELECT
            w.user_id, w.domain, w.registrable_domain, w.is_subdomain,
            w.added_at, true,  -- is_wishlist = true
            NULL,  -- notify_days = NULL (wishlist не уведомляет об expiry)
            false, false, false,  -- notify_expiry, ns_change, registrar_change
            false, false, false,  -- status_change, registrant_change, problem
            false,  -- is_muted
            false, false, false, NULL,  -- SSL
            false, false, false, false, false,  -- DNS
            false, false  -- email
        FROM wishlist w
        ON CONFLICT (user_id, domain) DO UPDATE SET
            is_wishlist = true,
            notify_days = NULL,
            notify_expiry = false,
            notify_ns_change = false,
            notify_registrar_change = false,
            notify_status_change = false,
            notify_registrant_change = false,
            notify_problem = false,
            is_muted = false,
            track_ssl = false,
            notify_ssl_expiry = false,
            notify_ssl_change_issuer = false,
            notify_ssl_days_override = NULL,
            track_dns = false,
            notify_dns_a_change = false,
            notify_dns_aaaa_change = false,
            notify_dns_ns_change = false,
            notify_dns_unreachable = false,
            track_email = false,
            notify_email_change = false
        """
    )

    # 3. Удаляем таблицу wishlist (с индексами и FK)
    op.execute("ALTER TABLE wishlist DROP CONSTRAINT IF EXISTS wishlist_user_id_fkey")
    op.drop_index("ix_wishlist_registrable_domain", table_name="wishlist")
    op.drop_index("ix_wishlist_domain", table_name="wishlist")
    op.drop_index("ix_wishlist_user_id", table_name="wishlist")
    op.drop_table("wishlist")
