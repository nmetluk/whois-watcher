"""Тесты best-effort audit() helper (TASK-0057, ADR 042).

Проверяем главный инвариант: audit() никогда не пробрасывает исключение.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.audit import audit


@pytest.mark.asyncio
async def test_audit_calls_record_via_repo_and_session() -> None:
    """audit() открывает сессию, создаёт репозиторий и вызывает record."""
    mock_repo = MagicMock()
    mock_repo.record = AsyncMock()

    mock_session = AsyncMock()
    # Контекст-менеджер возвращает мок сессии
    mock_session_cm = AsyncMock()
    mock_session_cm.__aenter__.return_value = mock_session
    mock_session_cm.__aexit__.return_value = None

    with (
        patch("src.services.audit.get_session", return_value=mock_session_cm),
        patch("src.services.audit.AuditLogRepository", return_value=mock_repo),
    ):
        await audit(
            "warning",
            "rate_limit",
            "rate limit hit for user",
            actor="12345",
            context={"ip": "1.2.3.4"},
        )

    mock_repo.record.assert_awaited_once_with(
        level="warning",
        category="rate_limit",
        message="rate limit hit for user",
        actor="12345",
        context={"ip": "1.2.3.4"},
    )


@pytest.mark.asyncio
async def test_audit_swallows_any_exception() -> None:
    """audit() — best-effort: любое исключение внутри (в т.ч. из get_session/record)
    глотается, наружу ничего не бросается.
    """
    mock_session_cm = AsyncMock()
    mock_session_cm.__aenter__.side_effect = RuntimeError("db pool exhausted")

    with patch("src.services.audit.get_session", return_value=mock_session_cm):
        # Не должно поднять исключение
        await audit("error", "task_failure", "something broke", actor="system")

    # Если дошли сюда — исключение было проглочено (тест пройден)
    assert True


@pytest.mark.asyncio
async def test_audit_swallows_repo_error() -> None:
    """Ошибка внутри record (после получения сессии) тоже глотается."""
    mock_repo = MagicMock()
    mock_repo.record = AsyncMock(side_effect=Exception("flush failed"))

    mock_session = AsyncMock()
    mock_session_cm = AsyncMock()
    mock_session_cm.__aenter__.return_value = mock_session
    mock_session_cm.__aexit__.return_value = None

    with (
        patch("src.services.audit.get_session", return_value=mock_session_cm),
        patch("src.services.audit.AuditLogRepository", return_value=mock_repo),
    ):
        await audit("critical", "startup", "failed to init foo")

    # Не упали — хорошо
    mock_repo.record.assert_awaited_once()
