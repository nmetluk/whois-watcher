"""Репозитории доступа к БД (ADR 022).

Хэндлеры и сервисы работают с БД **только** через эти классы.
Прямой SQL и ORM-запросы вне ``src/db/`` запрещены.

Пример::

    async with get_session() as session:
        users = UserRepository(session)
        user = await users.get_by_telegram_id(12345)
"""

from src.db.repositories.base import BaseRepository
from src.db.repositories.domains import DomainRepository
from src.db.repositories.notifications import NotificationRepository
from src.db.repositories.ssl_cache import SSLCacheRepository
from src.db.repositories.users import UserRepository
from src.db.repositories.whois_cache import WhoisCacheRepository

__all__ = [
    "BaseRepository",
    "DomainRepository",
    "NotificationRepository",
    "SSLCacheRepository",
    "UserRepository",
    "WhoisCacheRepository",
]
