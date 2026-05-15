"""Async-движок SQLAlchemy и фабрика сессий.

Архитектура:

- ровно один ``AsyncEngine`` на процесс (внутри ``_get_engine()`` с кешем)
- ``async_sessionmaker`` — фабрика сессий
- ``get_session()`` — async context manager: коммит на выходе из ``with``,
  rollback при исключении

Использование в репозиториях/хэндлерах::

    from src.db.session import get_session

    async with get_session() as session:
        repo = UserRepository(session)
        user = await repo.get_by_telegram_id(12345)

Никаких глобальных сессий — каждая операция получает свою.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.config.settings import get_settings


@lru_cache(maxsize=1)
def _get_engine() -> AsyncEngine:
    """Создаёт (или возвращает кешированный) async-движок."""
    settings = get_settings()
    return create_async_engine(
        settings.postgres_dsn,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        # echo=False по умолчанию, чтобы не светить SQL в логах prod
        echo=False,
        future=True,
    )


@lru_cache(maxsize=1)
def _get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """Фабрика сессий, привязанная к единственному движку."""
    return async_sessionmaker(
        bind=_get_engine(),
        class_=AsyncSession,
        expire_on_commit=False,  # удобнее для async — не дёргает БД после commit
        autoflush=False,
    )


@asynccontextmanager
async def get_session() -> AsyncIterator[AsyncSession]:
    """Async context manager одной сессии.

    На выходе:
    - при отсутствии исключений → ``commit()``
    - при исключении → ``rollback()`` и проброс наверх

    Всегда закрывает сессию (``close()``) в ``finally``.
    """
    factory = _get_sessionmaker()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def dispose_engine() -> None:
    """Закрывает пул соединений. Вызывать при graceful shutdown процесса."""
    engine = _get_engine()
    await engine.dispose()
