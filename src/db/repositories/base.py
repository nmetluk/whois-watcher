"""Базовый класс репозитория.

Тонкий — хранит только ``AsyncSession``. Никаких общих CRUD-методов:
у каждой сущности своя специфика, общие методы быстро обрастают
``# noqa: type:ignore``.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession


class BaseRepository:
    """Базовый репозиторий: только сессия (DI).

    Подклассы получают ``self.session: AsyncSession`` и реализуют свои
    запросы. Сессия создаётся снаружи (см. ``src.db.session.get_session``).
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
