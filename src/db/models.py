"""SQLAlchemy 2.0-модели приложения.

Схема описана в ``docs/architecture.md`` (раздел "Схема базы данных").
Используем декларативный 2.0-стиль: ``DeclarativeBase`` + ``Mapped[...]`` +
``mapped_column``. Все timestamp-поля — ``timestamptz``.

При изменении модели — сгенерировать миграцию Alembic, **не** выполнять
``CREATE TABLE`` где-либо в коде.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    ARRAY,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Базовый декларативный класс. Один MetaData на весь пакет.

    Импортируется в ``migrations/env.py`` для ``target_metadata = Base.metadata``.
    """


# ---------------------------------------------------------------------------
# users
# ---------------------------------------------------------------------------
class User(Base):
    """Пользователь бота (один Telegram-аккаунт)."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    username: Mapped[str | None] = mapped_column(Text, nullable=True)

    language: Mapped[str] = mapped_column(Text, nullable=False, server_default="ru")
    timezone: Mapped[str] = mapped_column(Text, nullable=False, server_default="Europe/Moscow")

    # int[] — массив целых: дни до истечения, за которые слать напоминания
    notify_days: Mapped[list[int]] = mapped_column(
        ARRAY(Integer),
        nullable=False,
        server_default="{30,7,1}",
    )
    notify_at_hour: Mapped[int] = mapped_column(Integer, nullable=False, server_default="9")
    # Этап 12 (ADR 030): дни-предупреждения для SSL-сертификатов. SSL живёт
    # короче WHOIS (LE — 90 дней), поэтому дефолт более частый.
    notify_ssl_days_before: Mapped[list[int]] = mapped_column(
        ARRAY(Integer),
        nullable=False,
        server_default="{14,7,3,1}",
    )
    # Этап 17 (ADR 038): интервал проверки поддоменов (дни). Задаёт
    # частоту periodic monitor'инга новых/исчезнувших поддоменов.
    subdomain_check_interval_days: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="7"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_active_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    is_blocked: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")

    domains: Mapped[list[UserDomain]] = relationship(
        "UserDomain",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    wishlist_items: Mapped[list[Wishlist]] = relationship(
        "Wishlist",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    domain_groups: Mapped[list[DomainGroup]] = relationship(
        "DomainGroup",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User id={self.id} tg={self.telegram_id} lang={self.language!r}>"


# ---------------------------------------------------------------------------
# user_domains
# ---------------------------------------------------------------------------
class UserDomain(Base):
    """Связь пользователь ↔ домен с настройками уведомлений (ADR 012)."""

    __tablename__ = "user_domains"
    __table_args__ = (
        UniqueConstraint("user_id", "domain", name="uq_user_domains_user_domain"),
        Index("ix_user_domains_user_id", "user_id"),
        Index("ix_user_domains_domain", "domain"),
        Index("ix_user_domains_registrable_domain", "registrable_domain"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    # punycode-форма (нормализация на стороне приложения, см. utils/idn.py)
    domain: Mapped[str] = mapped_column(Text, nullable=False)
    # registrable-домен (eTLD+1) — для WHOIS-джойнов. Для apex-доменов == domain.
    registrable_domain: Mapped[str] = mapped_column(Text, nullable=False)
    # Признак поддомена: True если domain != registrable_domain
    is_subdomain: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")

    # NULL = берём notify_days из users
    notify_days: Mapped[list[int] | None] = mapped_column(ARRAY(Integer), nullable=True)
    notify_expiry: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    notify_ns_change: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    notify_registrar_change: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    notify_status_change: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    # Этап 11: смена владельца — отдельный toggle (раньше шло через
    # notify_registrar_change-mapping, см. ADR 029).
    notify_registrant_change: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    # Этап 11: проблемы с проверкой WHOIS — отдельный toggle.
    notify_problem: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    # Этап 11: kill-switch (replaces computed _is_muted из formatters).
    # True → подавляет ВСЕ уведомления независимо от индивидуальных
    # ``notify_*`` флагов. При unmute индивидуальные настройки сохраняются.
    is_muted: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))

    # Этап 12 (ADR 030): SSL-мониторинг. ``track_ssl=False`` исключает
    # домен из ssl_scheduler — экономим ресурсы и не плодим уведомлений.
    track_ssl: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    notify_ssl_expiry: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    notify_ssl_change_issuer: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    # NULL → используем ``User.notify_ssl_days_before``.
    notify_ssl_days_override: Mapped[list[int] | None] = mapped_column(
        ARRAY(Integer), nullable=True
    )

    # Этап 14 (ADR 032): DNS-мониторинг. ``track_dns=False`` исключает
    # домен из dns_scheduler — экономим ресурсы и не плодим уведомлений.
    track_dns: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    notify_dns_a_change: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    notify_dns_aaaa_change: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    # Гибридная семантика: обычная смена NS-записей (info) И расхождение
    # DNS-NS vs WHOIS-NS (critical) — оба под этим одним toggle'ом, но
    # с разным эмодзи/тоном в сообщении.
    notify_dns_ns_change: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    notify_dns_unreachable: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )

    # Этап 15 (ADR 036): Email-intel мониторинг. ``track_email=False`` исключает
    # домен из email_intel_scheduler — экономим ресурсы и не плодим уведомления.
    track_email: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    notify_email_change: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )

    # Этап 17 (ADR 038): мониторинг поддоменов. Opt-in (default false), т.к.
    # enumeration бьёт crt.sh — только явный запрос. NULL → берём интервал
    # из User.subdomain_check_interval_days.
    track_subdomains: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    notify_subdomain_new: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    notify_subdomain_removed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    subdomain_check_interval_override: Mapped[int | None] = mapped_column(Integer, nullable=True)

    last_problem_notified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    user: Mapped[User] = relationship("User", back_populates="domains")

    groups: Mapped[list[DomainGroup]] = relationship(
        "DomainGroup",
        secondary="user_domain_group",
        back_populates="domains",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<UserDomain user={self.user_id} domain={self.domain!r}>"


# ---------------------------------------------------------------------------
# domain_group + membership (TASK-0073, ADR 043)
# ---------------------------------------------------------------------------
class DomainGroup(Base):
    """Группа/тег доменов пользователя (клиентские или личные).
    Используется для группировки в WebApp (список, дашборд, экран Группы).
    """

    __tablename__ = "domain_group"
    __table_args__ = (Index("ix_domain_group_user_id", "user_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)  # 'client' | 'personal'
    color: Mapped[str | None] = mapped_column(Text, nullable=True)  # hue token 'a0'..'a7'
    icon: Mapped[str | None] = mapped_column(Text, nullable=True)  # e.g. 'folder_special'
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    user: Mapped[User] = relationship("User", back_populates="domain_groups")

    domains: Mapped[list[UserDomain]] = relationship(
        "UserDomain",
        secondary="user_domain_group",
        back_populates="groups",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<DomainGroup user={self.user_id} name={self.name!r} kind={self.kind}>"


class UserDomainGroup(Base):
    """Membership: many-to-many связь user_domain <-> domain_group.
    Составной PK, без дополнительных полей. Каскады на удаление сторон.
    """

    __tablename__ = "user_domain_group"
    __table_args__ = (
        PrimaryKeyConstraint("user_domain_id", "group_id"),
        Index("ix_user_domain_group_group_id", "group_id"),
    )

    user_domain_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("user_domains.id", ondelete="CASCADE"),
        primary_key=True,
    )
    group_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("domain_group.id", ondelete="CASCADE"),
        primary_key=True,
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<UserDomainGroup ud={self.user_domain_id} g={self.group_id}>"


# ---------------------------------------------------------------------------
# whois_cache
# ---------------------------------------------------------------------------
class WhoisCache(Base):
    """Общий кэш WHOIS-данных по доменам (ADR 006).

    PK = ``domain`` (punycode). Одна запись на домен на всех подписчиков.
    """

    __tablename__ = "whois_cache"
    __table_args__ = (
        # Условный индекс — только активные next_check_at.
        # autogenerate Alembic такое часто пропускает, см. миграцию.
        Index(
            "ix_whois_cache_next_check_at",
            "next_check_at",
            postgresql_where=text("next_check_at IS NOT NULL"),
        ),
        Index("ix_whois_cache_expires_at", "expires_at"),
    )

    domain: Mapped[str] = mapped_column(Text, primary_key=True)

    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at_registrar: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    updated_at_registrar: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    registrar: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    name_servers: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    raw_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    # Денормализованные поля владельца (Этап 8). NULL для записей, созданных
    # до миграции; при следующей плановой проверке заполняются парсером.
    # Хранится в денормализованном виде, чтобы карточка /whois и
    # diff-сравнение не парсили JSON каждый раз.
    registrant_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    registrant_org: Mapped[str | None] = mapped_column(String(256), nullable=True)
    registrant_country: Mapped[str | None] = mapped_column(String(8), nullable=True)
    registrant_email: Mapped[str | None] = mapped_column(String(256), nullable=True)
    registrant_is_redacted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    # Полный список контактов (включая admin/tech/abuse) — для «Полного ответа»
    # и потенциального сравнения версий без парса raw_data.
    contacts_data: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)

    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_successful_fetch_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    next_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    fail_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<WhoisCache domain={self.domain!r} expires={self.expires_at}>"


# ---------------------------------------------------------------------------
# sent_notifications
# ---------------------------------------------------------------------------
class SentNotification(Base):
    """Журнал отправленных уведомлений (для дедупликации).

    UNIQUE по (user_id, domain, notification_type, days_before, expires_at)
    защищает от повторов даже после продления домена: при новом expires_at
    можно слать заново.
    """

    __tablename__ = "sent_notifications"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "domain",
            "notification_type",
            "days_before",
            "expires_at",
            name="uq_sent_notifications_dedup",
        ),
        Index("ix_sent_notifications_user_domain", "user_id", "domain"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    domain: Mapped[str] = mapped_column(Text, nullable=False)
    # 'expiry' | 'ns_change' | 'registrar_change' | 'status_change' | 'problem'
    notification_type: Mapped[str] = mapped_column(String(32), nullable=False)
    # Заполнен только для notification_type='expiry'
    days_before: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Снапшот expires_at — чтобы после продления можно было слать заново
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<SentNotification user={self.user_id} domain={self.domain!r} "
            f"type={self.notification_type!r}>"
        )


# ---------------------------------------------------------------------------
# domain_changes
# ---------------------------------------------------------------------------
class DomainChange(Base):
    """История изменений по доменам (для аналитики и истории)."""

    __tablename__ = "domain_changes"
    __table_args__ = (
        Index(
            "ix_domain_changes_domain_detected",
            "domain",
            "detected_at",
            postgresql_using="btree",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    domain: Mapped[str] = mapped_column(Text, nullable=False)
    # 'expires_at' | 'registrar' | 'ns' | 'status'
    change_type: Mapped[str] = mapped_column(String(32), nullable=False)
    old_value: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    new_value: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


# ---------------------------------------------------------------------------
# system_events
# ---------------------------------------------------------------------------
class SystemEvent(Base):
    """Журнал системных событий для алертов и аналитики (ADR 019)."""

    __tablename__ = "system_events"
    __table_args__ = (
        Index("ix_system_events_type_created", "event_type", "created_at"),
        Index(
            "ix_system_events_severity_created",
            "severity",
            "created_at",
            postgresql_where=text("severity IN ('error', 'critical')"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # 'whois_failed' | 'rate_limit_hit' | ...
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    # 'info' | 'warning' | 'error' | 'critical'
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


# ---------------------------------------------------------------------------
# audit_log (ADR 042, TASK-0057)
# ---------------------------------------------------------------------------
class AuditLog(Base):
    """Журнал инцидентов/аудита для разбора нештатных ситуаций (retention 90д).

    Отдельная от ``system_events`` (аналитика, retention 30д). См. ADR 042.
    """

    __tablename__ = "audit_log"
    __table_args__ = (Index("ix_audit_log_category_created", "category", "created_at"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    # 'info' | 'warning' | 'error' | 'critical'
    level: Mapped[str] = mapped_column(String(16), nullable=False)
    # 'task_failure' | 'rate_limit' | 'admin_action' | 'webhook' | 'startup' | 'other'
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    # user_id (str) или "system"
    actor: Mapped[str | None] = mapped_column(Text, nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    context: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AuditLog id={self.id} level={self.level} category={self.category}>"


# ---------------------------------------------------------------------------
# ssl_cache (Этап 12, ADR 030)
# ---------------------------------------------------------------------------
class SSLCache(Base):
    """Общий кэш SSL-сертификатов по доменам (ADR 030).

    Параллельно ``whois_cache``: одна запись на домен (PK ``domain``),
    обслуживает всех подписчиков. Adaptive ``next_check_at`` зависит от
    близости истечения сертификата (см. ``src.ssl.scheduler``).
    """

    __tablename__ = "ssl_cache"
    __table_args__ = (
        Index(
            "ix_ssl_cache_next_check_at",
            "next_check_at",
        ),
        Index("ix_ssl_cache_not_after", "not_after"),
    )

    domain: Mapped[str] = mapped_column(Text, primary_key=True)

    # Scheduling
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_successful_check_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    next_check_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Reachability
    is_reachable: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    has_certificate: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    # Certificate dates
    not_before: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    not_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Issuer (отслеживаем смену CA)
    issuer_cn: Mapped[str | None] = mapped_column(String(256), nullable=True)
    issuer_o: Mapped[str | None] = mapped_column(String(256), nullable=True)

    # Subject (информативно)
    subject_cn: Mapped[str | None] = mapped_column(String(256), nullable=True)
    subject_alt_names: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)

    # Identifiers
    serial_number: Mapped[str | None] = mapped_column(String(128), nullable=True)
    fingerprint_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    signature_algorithm: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Failure tracking
    fail_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<SSLCache domain={self.domain!r} not_after={self.not_after}>"


# ---------------------------------------------------------------------------
# dns_cache (Этап 14, ADR 032)
# ---------------------------------------------------------------------------
class DNSCache(Base):
    """Общий кэш DNS-записей по доменам (ADR 032).

    Параллельно ``ssl_cache`` и ``whois_cache``: одна запись на домен
    (PK ``domain``), обслуживает всех подписчиков. Adaptive
    ``next_check_at`` зависит от состояния (см. ``src.dns_monitor.scheduler``).

    Поля ``is_reachable=None`` до первой проверки. После первой: True
    если резолв удался, False при network/NXDOMAIN.
    """

    __tablename__ = "dns_cache"
    __table_args__ = (Index("ix_dns_cache_next_check_at", "next_check_at"),)

    domain: Mapped[str] = mapped_column(Text, primary_key=True)

    # Scheduling
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_successful_check_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    next_check_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    last_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # DNS records
    a_records: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    aaaa_records: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    ns_records: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)

    # ASN enrichment — placeholder для v0.8.0 (rir2localdb v0.1.1 не
    # отдаёт IP→ASN; полная сборка в v0.8.x).
    asn_set: Mapped[list[int] | None] = mapped_column(
        ARRAY(Integer),
        nullable=True,
        comment="Unique ASNs from a/aaaa IPs",
    )

    # Resolution state
    resolution_state: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'unknown'"),
        comment="resolved / mx_only / no_dns / error / unknown",
    )
    is_reachable: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    resolver_used: Mapped[str | None] = mapped_column(Text, nullable=True)

    # NS-mismatch tracking — DNS-NS vs WHOIS-NS, критический сигнал.
    ns_mismatch_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )

    # Failure tracking
    fail_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<DNSCache domain={self.domain!r} state={self.resolution_state!r}>"


# ---------------------------------------------------------------------------
# email_intel_cache (TASK-0015, ADR 036)
# ---------------------------------------------------------------------------
class EmailIntelCache(Base):
    """Общий кэш email/policy-записей по доменам (ADR 036).

    Параллельно ``whois_cache``, ``ssl_cache``, ``dns_cache``: одна запись
    на домен (PK ``domain``), обслуживает всех подписчиков. Adaptive
    ``next_check_at`` зависит от состояния (scheduler в ``src.email_intel.scheduler``).

    Хранит разобранные данные:
    - MX: список host+priority (JSONB)
    - SPF: сырая запись + режим (all/sp=...)
    - DMARC: policy, sp/p, pct
    - DKIM: найденные селекторы
    """

    __tablename__ = "email_intel_cache"
    __table_args__ = (Index("ix_email_intel_cache_next_check_at", "next_check_at"),)

    domain: Mapped[str] = mapped_column(Text, primary_key=True)

    # Scheduling
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_successful_check_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    next_check_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Reachability
    is_reachable: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    # Email records
    mx_records: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment='Список MX-записей [{"priority": 10, "host": "mail.example.com"}]',
    )

    # SPF
    spf_record: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Сырая SPF-запись",
    )
    spf_mode: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Режим SPF: none, neutral, pass, fail, softfail, temperror, permerror",
    )

    # DMARC
    dmarc_policy: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="DMARC policy: none, quarantine, reject",
    )
    dmarc_subpolicy: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="DMARC sp/p: none, quarantine, reject",
    )
    dmarc_pct: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="DMARC pct (0-100), NULL = дефолт 100",
    )

    # DKIM
    dkim_selectors: Mapped[list[str] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Список найденных DKIM-селекторов",
    )

    # Failure tracking
    fail_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<EmailIntelCache domain={self.domain!r} mx={len(self.mx_records) if self.mx_records else 0}>"


# ---------------------------------------------------------------------------
# email_deep_cache (TASK-0039, ADR 040)
# ---------------------------------------------------------------------------
class EmailDeepCache(Base):
    """Кэш результатов deep email (SPF recursion + MTA-STS + TLS-RPT + DANE + BIMI).

    On-demand только (короткий TTL, нет периодического scheduler'а в v0.13).
    Одна запись на domain (PK ``domain``). Хранит сериализованные
    dataclass-результаты из ``src.email_intel.deep_types`` как JSONB.
    """

    __tablename__ = "email_deep_cache"
    __table_args__ = (Index("ix_email_deep_cache_next_check_at", "next_check_at"),)

    domain: Mapped[str] = mapped_column(Text, primary_key=True)

    # Deep results (сериализованные dataclass'ы из TASK-0038)
    spf: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True, comment="SpfResolution as dict (sources, lookup_count, exceeds_limit)"
    )
    mta_sts: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="MtaStsResult (txt_present, policy_mode, mx[], max_age, reachable)",
    )
    tls_rpt: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True, comment="TlsRptResult (present, rua)"
    )
    dane: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True, comment="DaneResult (host_tlsa: {host: bool})"
    )
    bimi: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True, comment="BimiResult (present, logo_url, vmc_url)"
    )

    # Scheduling (short TTL для on-demand)
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_check_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Reachability / failure (graceful degradation)
    is_reachable: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    fail_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<EmailDeepCache domain={self.domain!r} reachable={self.is_reachable}>"


# ---------------------------------------------------------------------------
# wishlist (ADR 039)
# ---------------------------------------------------------------------------
class Wishlist(Base):
    """Wishlist: домены, за которыми пользователь следит (ожидание освобождения) (ADR 039).

    Независимая таблица от ``user_domains``. После TASK-0031/0032 один домен может
    одновременно быть и в tracking (``/list``), и в wishlist (``/wishlist``).
    """

    __tablename__ = "wishlist"
    __table_args__ = (
        UniqueConstraint("user_id", "domain", name="uq_wishlist_user_domain"),
        Index("ix_wishlist_user_id", "user_id"),
        Index("ix_wishlist_domain", "domain"),
        Index("ix_wishlist_registrable_domain", "registrable_domain"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="ID пользователя (FK → users.id ON DELETE CASCADE)",
    )
    # punycode-форма (нормализация на стороне приложения, см. utils/idn.py)
    domain: Mapped[str] = mapped_column(Text, nullable=False)
    # registrable-домен (eTLD+1) — для WHOIS-джойна, ADR 035
    registrable_domain: Mapped[str] = mapped_column(Text, nullable=False)
    # Признак поддомена: True если domain != registrable_domain
    is_subdomain: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    # Когда добавлен в wishlist
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    # Когда последнее уведомление об освобождении (для одноразовости)
    last_notified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user: Mapped[User] = relationship("User", back_populates="wishlist_items")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Wishlist user={self.user_id} domain={self.domain!r}>"


# ---------------------------------------------------------------------------
# subdomain_enum_cache (ADR 037)
# ---------------------------------------------------------------------------
class SubdomainEnumCache(Base):
    """Кэш результатов subdomain enumeration через crt.sh (ADR 037).

    Параллельно ``whois_cache``, ``ssl_cache``, ``dns_cache``, ``email_intel_cache``:
    одна запись на registrable-домен (PK ``registrable_domain``), обслуживает
    всех подписчиков. Хранит найденные поддомены из CT-логов с TTL.

    Хранит разобранные данные:
    - ``subdomains`` — список найденных поддоменов (JSONB, нормализованных)
    - Scheduling-поля для adaptive TTL (scheduler в будущем ADR 038)
    - Reachability/failure tracking для graceful degradation
    """

    __tablename__ = "subdomain_enum_cache"
    __table_args__ = (Index("ix_subdomain_enum_cache_next_check_at", "next_check_at"),)

    registrable_domain: Mapped[str] = mapped_column(
        Text,
        primary_key=True,
        comment="Registrable-домен (eTLD+1, ADR 035)",
    )

    # Subdomains (результат enumeration)
    subdomains: Mapped[list[str] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Список найденных поддоменов (нормализованных: lowercase, punycode, без wildcard)",
    )

    # Scheduling
    fetched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Когда последний раз запрашивали у crt.sh",
    )
    next_check_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="Когда можно снова обновить (TTL кэша)",
    )

    # Reachability
    is_reachable: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
        comment="True если crt.sh доступен, False при ошибках, NULL до первой проверки",
    )

    # Failure tracking
    fail_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
        comment="Количество последовательных неудач",
    )
    last_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Текст последней ошибки (если была)",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<SubdomainEnumCache registrable={self.registrable_domain!r} subdomains={len(self.subdomains) if self.subdomains else 0}>"
