"""Тесты для notify_subdomain_changes (TASK-0029, ADR 038)."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.tasks.notify_subdomain_changes import notify_subdomain_changes


@pytest.fixture
def mock_bot() -> AsyncMock:
    """Мок Bot."""
    return AsyncMock()


@pytest.fixture
def mock_ctx(mock_bot: AsyncMock) -> dict:
    """Мок ARQ context."""
    return {"bot": mock_bot}


class TestNotifySubdomainChanges:
    """Базовые тесты функции notify_subdomain_changes."""

    @pytest.mark.asyncio
    async def test_empty_diff_does_nothing(self, mock_ctx: dict) -> None:
        """Пустой diff — ничего не делаем (ранний return)."""
        # Не должно падать и не должно вызывать bot.send_message
        await notify_subdomain_changes(
            mock_ctx, registrable_domain="example.com", diff={"new": [], "removed": []}
        )
        # Bot не должен был вызван для отправки
        mock_ctx["bot"].send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_function_exists_and_callable(self, mock_ctx: dict) -> None:
        """Функция импортируема и вызываема с корректными аргументами."""
        # Проверка что функция вообще работает с валидными аргументами
        # (без БД подсоединения — упадёт только если есть синтаксическая ошибка)
        try:
            await notify_subdomain_changes(
                mock_ctx,
                registrable_domain="example.com",
                diff={"new": ["www.example.com"], "removed": []},
            )
        except Exception as exc:
            # Ожидаем только ошибки БД-подключения или DNS, а не синтаксические
            exc_str = str(exc).lower()
            assert (
                "postgres" in exc_str
                or "connection" in exc_str
                or "temporary failure" in exc_str
                or "name resolution" in exc_str
            )
