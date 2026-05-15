"""Глобальные фикстуры тестов.

ENV-дефолты — чтобы ``get_settings()`` не падал на отсутствии обязательных
переменных. Фактических подключений к БД/Redis тесты на Этапе 2 не делают.
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock

import pytest

# Подставляем безопасные дефолты для тестов: иначе ``get_settings`` упадёт
# на отсутствии обязательных переменных (BOT_TOKEN, WEBHOOK_*, POSTGRES_PASSWORD).
# Это поведение per-module: переменные ставятся ДО импорта тестов pytest'ом.
os.environ.setdefault("BOT_TOKEN", "test-bot-token")
os.environ.setdefault("WEBHOOK_BASE_URL", "https://test.local")
os.environ.setdefault("WEBHOOK_SECRET", "test-webhook-secret")
os.environ.setdefault("POSTGRES_PASSWORD", "test-postgres-password")


@pytest.fixture
def mock_redis() -> AsyncMock:
    """Async-мок Redis-клиента для тестов middleware/handlers.

    ``spec=Redis`` гарантирует, что попытки вызвать несуществующий метод
    не пройдут молча — лучше падать в тесте, чем ловить тонкую ошибку
    в проде.
    """
    from redis.asyncio import Redis

    return AsyncMock(spec=Redis)
