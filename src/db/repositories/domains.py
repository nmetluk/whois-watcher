"""Репозиторий ``user_domains``."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import and_, delete, func, select, update

from src.db.models import UserDomain, WhoisCache
from src.db.repositories.base import BaseRepository

# Дефолтные значения флагов уведомлений (ADR 012).
DEFAULT_NOTIFICATION_FLAGS: dict[str, bool] = {
    "notify_expiry": True,
    "notify_ns_change": False,
    "notify_registrar_change": True,
    "notify_status_change": True,
}


@dataclass(frozen=True, slots=True)
class UserDomainStats:
    """Готовые цифры для ``/stats``: суммарно + истечения + muted + added_month."""

    total: int
    with_data: int
    expiring_7: int
    expiring_30: int
    expiring_90: int
    muted: int
    added_month: int

    @property
    def without_data(self) -> int:
        return self.total - self.with_data


class DomainRepository(BaseRepository):
    """Связь пользователь ↔ домен."""

    async def add(
        self,
        user_id: int,
        domain: str,
        *,
        note: str | None = None,
    ) -> UserDomain:
        """Добавляет домен в портфель пользователя.

        Вызывающая сторона должна заранее проверить ``exists`` и лимит:
        репозиторий пробросит ``IntegrityError`` при нарушении UNIQUE.
        """
        row = UserDomain(user_id=user_id, domain=domain, note=note)
        self.session.add(row)
        await self.session.flush()
        await self.session.refresh(row)
        return row

    async def remove(self, user_id: int, domain: str) -> bool:
        """Удаляет одну запись. Возвращает ``True`` если что-то удалили."""
        stmt = (
            delete(UserDomain)
            .where(UserDomain.user_id == user_id, UserDomain.domain == domain)
            .returning(UserDomain.id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def exists(self, user_id: int, domain: str) -> bool:
        """True, если домен уже отслеживается пользователем."""
        stmt = select(UserDomain.id).where(
            UserDomain.user_id == user_id, UserDomain.domain == domain
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def count_by_user(self, user_id: int) -> int:
        """Количество доменов в портфеле."""
        stmt = select(func.count()).select_from(UserDomain).where(UserDomain.user_id == user_id)
        result = await self.session.execute(stmt)
        return int(result.scalar_one())

    async def list_by_user(
        self,
        user_id: int,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[UserDomain]:
        """Простой список user_domains пользователя (без JOIN с whois_cache)."""
        stmt = (
            select(UserDomain)
            .where(UserDomain.user_id == user_id)
            .order_by(UserDomain.added_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_with_whois(
        self,
        user_id: int,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[tuple[UserDomain, WhoisCache | None]]:
        """Список доменов пользователя с присоединённым кэшем WHOIS.

        Используется для ``/list``: сортировка по ``expires_at ASC NULLS LAST``
        (``docs/commands.md``). Возвращает пары ``(UserDomain, WhoisCache|None)``.
        """
        stmt = (
            select(UserDomain, WhoisCache)
            .outerjoin(WhoisCache, WhoisCache.domain == UserDomain.domain)
            .where(UserDomain.user_id == user_id)
            .order_by(
                WhoisCache.expires_at.asc().nulls_last(),
                UserDomain.added_at.desc(),
            )
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        # outerjoin делает WhoisCache опциональным на рантайме, но стабы об этом не знают
        return [(row[0], row[1]) for row in result.all()]

    async def toggle_notifications(
        self,
        user_id: int,
        domain: str,
        *,
        enabled: bool,
    ) -> bool:
        """Включает/выключает все 4 типа уведомлений по домену (ADR 015).

        - ``enabled=True``  → возвращаем все флаги к дефолту (см. ADR 012)
        - ``enabled=False`` → выключаем все типы

        Возвращает True, если строка существовала и была обновлена.
        """
        if enabled:
            values: dict[str, Any] = dict(DEFAULT_NOTIFICATION_FLAGS)
        else:
            values = {k: False for k in DEFAULT_NOTIFICATION_FLAGS}
        stmt = (
            update(UserDomain)
            .where(and_(UserDomain.user_id == user_id, UserDomain.domain == domain))
            .values(**values)
            .returning(UserDomain.id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def get_user_stats(self, user_id: int, *, now: datetime | None = None) -> UserDomainStats:
        """Агрегаты для ``/stats``: один SQL-проход по портфелю пользователя.

        Использует FILTER-агрегаты Postgres, чтобы посчитать всё одним запросом
        с ``user_domains LEFT JOIN whois_cache``. ``now`` параметризован для
        тестов.
        """
        moment = now if now is not None else datetime.now(tz=UTC)
        in_7 = moment + timedelta(days=7)
        in_30 = moment + timedelta(days=30)
        in_90 = moment + timedelta(days=90)
        month_ago = moment - timedelta(days=30)

        has_data = WhoisCache.expires_at.is_not(None)
        muted_expr = and_(
            UserDomain.notify_expiry.is_(False),
            UserDomain.notify_ns_change.is_(False),
            UserDomain.notify_registrar_change.is_(False),
            UserDomain.notify_status_change.is_(False),
        )

        stmt = (
            select(
                func.count().label("total"),
                func.count().filter(has_data).label("with_data"),
                func.count()
                .filter(
                    and_(
                        WhoisCache.expires_at.is_not(None),
                        WhoisCache.expires_at <= in_7,
                        WhoisCache.expires_at >= moment,
                    )
                )
                .label("exp_7"),
                func.count()
                .filter(
                    and_(
                        WhoisCache.expires_at.is_not(None),
                        WhoisCache.expires_at <= in_30,
                        WhoisCache.expires_at >= moment,
                    )
                )
                .label("exp_30"),
                func.count()
                .filter(
                    and_(
                        WhoisCache.expires_at.is_not(None),
                        WhoisCache.expires_at <= in_90,
                        WhoisCache.expires_at >= moment,
                    )
                )
                .label("exp_90"),
                func.count().filter(muted_expr).label("muted"),
                func.count().filter(UserDomain.added_at >= month_ago).label("added_month"),
            )
            .select_from(UserDomain)
            .outerjoin(WhoisCache, WhoisCache.domain == UserDomain.domain)
            .where(UserDomain.user_id == user_id)
        )

        result = await self.session.execute(stmt)
        row = result.one()
        return UserDomainStats(
            total=int(row.total),
            with_data=int(row.with_data),
            expiring_7=int(row.exp_7),
            expiring_30=int(row.exp_30),
            expiring_90=int(row.exp_90),
            muted=int(row.muted),
            added_month=int(row.added_month),
        )

    async def update_notification_settings(
        self,
        user_id: int,
        domain: str,
        /,
        **flags: bool,
    ) -> bool:
        """Частичное обновление флагов уведомлений (для ``/settings`` → домен).

        Принимает любое подмножество из ``DEFAULT_NOTIFICATION_FLAGS``.
        Неизвестные ключи пробрасываются как ошибка SQL — это намеренно.
        """
        if not flags:
            return False
        stmt = (
            update(UserDomain)
            .where(and_(UserDomain.user_id == user_id, UserDomain.domain == domain))
            .values(**flags)
            .returning(UserDomain.id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None
