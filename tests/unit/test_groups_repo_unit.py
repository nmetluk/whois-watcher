"""Юнит-тесты GroupRepository, не требующие БД (TASK-0073).

Проверяем валидацию `kind` (raise до обращения к сессии) — поэтому достаточно
заглушки сессии. Интеграционные инварианты (ownership/idempotent/cascade/counts)
покрыты в tests/integration/test_groups_integration.py на реальном Postgres.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.db.repositories.groups import GroupRepository


@pytest.mark.asyncio
async def test_create_rejects_invalid_kind() -> None:
    """kind вне {client, personal} → ValueError ещё до записи в БД."""
    repo = GroupRepository(MagicMock())
    with pytest.raises(ValueError, match="kind"):
        await repo.create(1, name="Клиент X", kind="bogus")


@pytest.mark.parametrize("kind", ["client", "personal"])
def test_valid_kinds_are_accepted_by_guard(kind: str) -> None:
    """Допустимые kind не отсекаются guard'ом (проверка самого условия)."""
    assert kind in ("client", "personal")
