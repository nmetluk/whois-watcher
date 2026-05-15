"""Репозиторий пользователей."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import delete, select, text, update

from src.db.models import User
from src.db.repositories.base import BaseRepository


class UserRepository(BaseRepository):
    """CRUD и спецзапросы по таблице ``users``."""

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        """Возвращает пользователя по Telegram ID или ``None``."""
        stmt = select(User).where(User.telegram_id == telegram_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_ids(self, user_ids: Sequence[int]) -> Sequence[User]:
        """Пакетная выборка пользователей по нашему ``users.id``.

        Используется задачами воркера (``check_domain`` followup): на входе —
        ``user_id`` подписчиков, нужно достать ``telegram_id`` и ``language``
        для рассылки. Пустой список — пустой результат, не SQL-запрос.
        """
        if not user_ids:
            return []
        stmt = select(User).where(User.id.in_(list(user_ids)))
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def create(
        self,
        telegram_id: int,
        *,
        username: str | None = None,
        language: str = "ru",
        timezone: str = "Europe/Moscow",
        notify_days: list[int] | None = None,
        notify_at_hour: int = 9,
    ) -> User:
        """Создаёт нового пользователя и возвращает закоммиченную запись.

        Сам ``commit`` делает контекст-менеджер ``get_session``; здесь мы
        только ``flush``, чтобы заполнить серверные дефолты и получить ``id``.
        """
        user = User(
            telegram_id=telegram_id,
            username=username,
            language=language,
            timezone=timezone,
            notify_at_hour=notify_at_hour,
        )
        if notify_days is not None:
            user.notify_days = notify_days
        self.session.add(user)
        await self.session.flush()
        await self.session.refresh(user)
        return user

    async def update_settings(self, user_id: int, /, **fields: Any) -> None:
        """Обновляет произвольный набор полей пользователя.

        Имена аргументов должны совпадать с именами колонок ``User``.
        Молча игнорирует пустой ``fields``.
        """
        if not fields:
            return
        stmt = update(User).where(User.id == user_id).values(**fields)
        await self.session.execute(stmt)

    async def touch_last_active(self, user_id: int) -> None:
        """Обновляет ``last_active_at = now()`` для пользователя."""
        stmt = update(User).where(User.id == user_id).values(last_active_at=text("now()"))
        await self.session.execute(stmt)

    async def delete(self, user_id: int) -> None:
        """Удаляет пользователя. Связанные user_domains и sent_notifications уйдут через ON DELETE CASCADE."""
        stmt = delete(User).where(User.id == user_id)
        await self.session.execute(stmt)

    async def get_users_due_for_notification(self) -> Sequence[User]:
        """Пользователи, у которых СЕЙЧАС локальный час равен ``notify_at_hour``.

        Реализация совпадает с SQL из ``docs/commands.md``::

            EXTRACT(HOUR FROM (now() AT TIME ZONE timezone)) = notify_at_hour

        Postgres делает преобразование TZ по строке из колонки ``timezone``.
        Метод не принимает час/смещение специально: тогда планировщик
        вызывает его раз в час и получает всех подходящих сразу.
        """
        stmt = select(User).where(
            User.is_blocked.is_(False),
            text(
                "EXTRACT(HOUR FROM (now() AT TIME ZONE users.timezone))::int "
                "= users.notify_at_hour"
            ),
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()
