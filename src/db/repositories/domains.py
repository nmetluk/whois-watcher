"""Репозиторий ``user_domains``."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.db.models import UserDomain, WhoisCache
from src.db.repositories.base import BaseRepository
from src.utils.idn import from_punycode, to_punycode

# Дефолтные значения флагов уведомлений (ADR 012).
DEFAULT_NOTIFICATION_FLAGS: dict[str, bool] = {
    "notify_expiry": True,
    "notify_ns_change": False,
    "notify_registrar_change": True,
    "notify_status_change": True,
}

# WHOIS-статусы, считающиеся «критическими» для фильтра ``/list critical``.
# Список синхронен с severity="critical" в ``src.locales.{ru,en}.WHOIS_STATUSES``
# — здесь продублирован, чтобы не дёргать UI-таблицы из SQL-уровня.
_CRITICAL_STATUS_CODES: tuple[str, ...] = (
    "clientHold",
    "serverHold",
    "pendingDelete",
    "BLOCKED",
    "failed",
)


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

    async def bulk_add(self, user_id: int, domains: Iterable[str]) -> int:
        """Bulk INSERT в ``user_domains`` с пропуском дублей.

        Используется ``/download`` после превью и подтверждения. Возвращает
        фактическое количество вставленных строк (``ON CONFLICT DO NOTHING``
        отсеет уже добавленные).
        """
        rows = [{"user_id": user_id, "domain": d} for d in domains]
        if not rows:
            return 0
        stmt = (
            pg_insert(UserDomain)
            .values(rows)
            .on_conflict_do_nothing(constraint="uq_user_domains_user_domain")
            .returning(UserDomain.id)
        )
        result = await self.session.execute(stmt)
        return len(result.scalars().all())

    async def bulk_existing_for_user(self, user_id: int, domains: Iterable[str]) -> set[str]:
        """Возвращает множество доменов, уже отслеживаемых пользователем."""
        domains_list = list(domains)
        if not domains_list:
            return set()
        stmt = select(UserDomain.domain).where(
            UserDomain.user_id == user_id,
            UserDomain.domain.in_(domains_list),
        )
        result = await self.session.execute(stmt)
        return set(result.scalars().all())

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

    async def get_for_user(self, user_id: int, domain: str) -> UserDomain | None:
        """Возвращает строку ``user_domains`` для конкретной пары или None.

        Нужна задачам уведомлений: перед send_message проверяем актуальные
        флаги ``notify_*`` и ``last_problem_notified_at`` — на момент рассылки
        пользователь мог уже выключить уведомления.
        """
        stmt = select(UserDomain).where(UserDomain.user_id == user_id, UserDomain.domain == domain)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def mark_problem_notified(self, user_id: int, domain: str, *, at: datetime) -> None:
        """Проставляет ``last_problem_notified_at`` после отправки problem-уведомления."""
        stmt = (
            update(UserDomain)
            .where(and_(UserDomain.user_id == user_id, UserDomain.domain == domain))
            .values(last_problem_notified_at=at)
        )
        await self.session.execute(stmt)

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

    async def iter_all_with_whois(
        self,
        user_id: int,
    ) -> Sequence[tuple[UserDomain, WhoisCache | None]]:
        """Все домены пользователя с WHOIS-кэшем — для экспорта в CSV.

        Без LIMIT/OFFSET: вызывающая сторона должна понимать, что для
        ``MAX_DOMAINS_PER_USER=50_000`` это до 50 тыс. строк.
        """
        stmt = (
            select(UserDomain, WhoisCache)
            .outerjoin(WhoisCache, WhoisCache.domain == UserDomain.domain)
            .where(UserDomain.user_id == user_id)
            .order_by(
                WhoisCache.expires_at.asc().nulls_last(),
                UserDomain.added_at.desc(),
            )
        )
        result = await self.session.execute(stmt)
        return [(row[0], row[1]) for row in result.all()]

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

    async def list_with_whois_filtered(
        self,
        user_id: int,
        *,
        filter_type: str = "all",
        search_query: str = "",
        include_wishlist: bool = False,
        limit: int = 50,
        offset: int = 0,
        now: datetime | None = None,
    ) -> tuple[list[tuple[UserDomain, WhoisCache | None]], int]:
        """Версия ``list_with_whois`` с фильтрами + поиском (для ``/list``).

        ``filter_type``:

        - ``"all"``       — все домены пользователя
        - ``"expiring"``  — ``expires_at`` в окне ближайших 30 дней
        - ``"no_data"``   — ``whois_cache.expires_at IS NULL`` (или нет записи)
        - ``"muted"``     — все 4 ``notify_*`` флага выключены
        - ``"critical"``  — ``status &&`` ARRAY критических EPP-кодов
        - ``"expired"``   — ``expires_at < now()``
        - ``"wishlist"``  — только ``is_wishlist=True`` записи

        ``search_query`` — подстрока имени домена (case-insensitive ILIKE).
        Поиск делается и по punycode-форме, и по unicode-варианту (для
        кириллических доменов: пользователь ищет «пример», находит
        ``xn--e1afmkfd.xn--p1ai``).

        ``include_wishlist`` — по умолчанию ``False``: обычный ``/list`` не
        показывает wishlist-домены (у них свой раздел). Только
        ``filter_type="wishlist"`` или явное ``include_wishlist=True``.

        Возвращает ``(rows, total)`` — страница и общее количество под
        фильтром+поиском.
        """
        moment = now if now is not None else datetime.now(tz=UTC)
        in_30 = moment + timedelta(days=30)

        base = (
            select(UserDomain, WhoisCache)
            .outerjoin(WhoisCache, WhoisCache.domain == UserDomain.domain)
            .where(UserDomain.user_id == user_id)
        )

        # Wishlist: либо строго wishlist (фильтр), либо строго обычные.
        if filter_type == "wishlist":
            base = base.where(UserDomain.is_wishlist.is_(True))
        elif not include_wishlist:
            base = base.where(UserDomain.is_wishlist.is_(False))

        if filter_type == "expiring":
            base = base.where(
                WhoisCache.expires_at.is_not(None),
                WhoisCache.expires_at <= in_30,
                WhoisCache.expires_at >= moment,
            )
        elif filter_type == "no_data":
            base = base.where(WhoisCache.expires_at.is_(None))
        elif filter_type == "muted":
            base = base.where(
                UserDomain.notify_expiry.is_(False),
                UserDomain.notify_ns_change.is_(False),
                UserDomain.notify_registrar_change.is_(False),
                UserDomain.notify_status_change.is_(False),
            )
        elif filter_type == "critical":
            # Postgres array overlap: status && ARRAY['clientHold', ...].
            # ``overlap`` — SQLAlchemy-метод ARRAY-колонки.
            base = base.where(
                WhoisCache.status.is_not(None),
                WhoisCache.status.overlap(list(_CRITICAL_STATUS_CODES)),
            )
        elif filter_type == "expired":
            base = base.where(
                WhoisCache.expires_at.is_not(None),
                WhoisCache.expires_at < moment,
            )
        # else: filter_type=="all" / "wishlist" — никаких доп. WHERE кроме wishlist.

        if search_query:
            base = base.where(_search_clause(search_query))

        # Считаем total отдельным запросом — пагинированный COUNT.
        count_stmt = select(func.count()).select_from(base.subquery())
        total_result = await self.session.execute(count_stmt)
        total = int(total_result.scalar_one())

        page_stmt = (
            base.order_by(
                WhoisCache.expires_at.asc().nulls_last(),
                UserDomain.added_at.desc(),
            )
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(page_stmt)
        rows: list[tuple[UserDomain, WhoisCache | None]] = [
            (row[0], row[1]) for row in result.all()
        ]
        return rows, total

    async def get_subscribers_for_domain(self, domain: str) -> Sequence[UserDomain]:
        """Все ``user_domains``-записи для домена (для followup'ов воркера).

        Воркер ``check_domain`` после обновления кэша зовёт этот метод и шлёт
        ``send_change_notice`` подписчикам. Метод НЕ фильтрует по флагам
        уведомлений — это забота вызывающей стороны (разные типы изменений
        смотрят разные флаги).
        """
        stmt = select(UserDomain).where(UserDomain.domain == domain)
        result = await self.session.execute(stmt)
        return result.scalars().all()

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

    # ------------------------------------------------------------------
    # Wishlist (Этап 9)
    # ------------------------------------------------------------------

    async def add_to_wishlist(self, user_id: int, domain: str) -> UserDomain:
        """Добавляет домен в wishlist пользователя или конвертирует
        существующую обычную подписку в wishlist.

        UPSERT через ON CONFLICT: если такая user_domains-запись уже есть,
        ставим ``is_wishlist=True`` поверх (и выключаем notify_*, чтобы не
        дублировать с tracking).
        """
        stmt = (
            pg_insert(UserDomain)
            .values(
                user_id=user_id,
                domain=domain,
                is_wishlist=True,
                notify_expiry=False,
                notify_ns_change=False,
                notify_registrar_change=False,
                notify_status_change=False,
            )
            .on_conflict_do_update(
                constraint="uq_user_domains_user_domain",
                set_={
                    "is_wishlist": True,
                    "notify_expiry": False,
                    "notify_ns_change": False,
                    "notify_registrar_change": False,
                    "notify_status_change": False,
                },
            )
            .returning(UserDomain.id)
        )
        await self.session.execute(stmt)
        await self.session.flush()
        row = await self.get_for_user(user_id, domain)
        assert row is not None  # invariant: только что upsert'нули
        return row

    async def remove_wishlist(self, user_id: int, domain: str) -> bool:
        """Удаляет запись wishlist (точный UNIQUE на (user_id, domain)).

        Возвращает True, если строка существовала и была удалена. Не
        фильтруем по ``is_wishlist`` — это идемпотентный DELETE на пару.
        """
        stmt = (
            delete(UserDomain)
            .where(
                UserDomain.user_id == user_id,
                UserDomain.domain == domain,
                UserDomain.is_wishlist.is_(True),
            )
            .returning(UserDomain.id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def get_wishlist_subscribers_for_domain(self, domain: str) -> Sequence[UserDomain]:
        """Только wishlist-подписчики домена — для ``send_wishlist_available_notice``."""
        stmt = select(UserDomain).where(
            UserDomain.domain == domain,
            UserDomain.is_wishlist.is_(True),
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def promote_from_wishlist(self, user_id: int, domain: str) -> bool:
        """Конвертирует wishlist-строку в обычное отслеживание.

        ``is_wishlist=False`` + восстановление дефолтных флагов
        ``notify_*`` из ``DEFAULT_NOTIFICATION_FLAGS``. SSL/DNS toggle'ы
        не трогаем — ``add_to_wishlist`` их не гасит.

        Возвращает True, если строка была wishlist и обновлена.
        """
        stmt = (
            update(UserDomain)
            .where(
                and_(
                    UserDomain.user_id == user_id,
                    UserDomain.domain == domain,
                    UserDomain.is_wishlist.is_(True),
                )
            )
            .values(
                is_wishlist=False,
                **DEFAULT_NOTIFICATION_FLAGS,
            )
            .returning(UserDomain.id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def update_notification_settings(
        self,
        user_id: int,
        domain: str,
        /,
        **values: Any,
    ) -> bool:
        """Частичное обновление настроек уведомлений (для конфигуратора).

        Принимает любые поля ``UserDomain``: boolean toggle'ы
        (``notify_*``, ``is_muted``) или ``notify_days: list[int] | None``.
        Неизвестные ключи пробрасываются как SQL-ошибка — намеренно.
        """
        if not values:
            return False
        stmt = (
            update(UserDomain)
            .where(and_(UserDomain.user_id == user_id, UserDomain.domain == domain))
            .values(**values)
            .returning(UserDomain.id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None


# ---------------------------------------------------------------------------
# Search-helper для /list (Этап 9)
# ---------------------------------------------------------------------------


def _search_clause(query: str) -> Any:
    """ILIKE-условие по domain: ищет и по punycode, и по unicode.

    Для русских доменов пользователь ввёл «пример» — без преобразования
    он не нашёл бы ``xn--e1afmkfd.xn--p1ai``. Поэтому пытаемся получить
    punycode-форму запроса, ищем по обоим вариантам через OR.
    """
    needle = query.strip().lower()
    if not needle:
        # Defensive fallback: пустой поиск возвращает «true»-условие.
        return func.true()
    like_unicode = f"%{from_punycode(needle)}%"
    candidates = [UserDomain.domain.ilike(f"%{needle}%"), UserDomain.domain.ilike(like_unicode)]
    try:
        punycoded = to_punycode(needle)
    except Exception:
        punycoded = ""
    if punycoded and punycoded != needle:
        candidates.append(UserDomain.domain.ilike(f"%{punycoded}%"))
    return or_(*candidates)
