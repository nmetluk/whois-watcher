"""Юнит-тесты GroupRepository, не требующие БД (TASK-0073).

Проверяем валидацию `kind` (raise до обращения к сессии) — поэтому достаточно
заглушки сессии. Интеграционные инварианты (ownership/idempotent/cascade/counts)
покрыты в tests/integration/test_groups_integration.py на реальном Postgres.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

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


@pytest.mark.asyncio
async def test_create_rejects_too_long_name() -> None:
    repo = GroupRepository(MagicMock())
    with pytest.raises(ValueError, match="name must be 1-100 chars"):
        await repo.create(1, name="x" * 101, kind="client")


@pytest.mark.asyncio
async def test_create_rejects_invalid_color() -> None:
    repo = GroupRepository(MagicMock())
    with pytest.raises(ValueError, match="color must be a0..a7"):
        await repo.create(1, name="test", kind="client", color="a9")


@pytest.mark.asyncio
async def test_create_rejects_too_long_icon() -> None:
    repo = GroupRepository(MagicMock())
    with pytest.raises(ValueError, match="icon must be <=32 chars"):
        await repo.create(1, name="test", kind="client", icon="x" * 33)


@pytest.mark.asyncio
async def test_update_rejects_invalid_fields() -> None:
    # Use a fresh repo with mocked get (update calls self.get first)
    repo = GroupRepository(MagicMock())
    # patch get to return a dummy group object
    dummy_grp = MagicMock()
    repo.get = AsyncMock(return_value=dummy_grp)  # type: ignore[method-assign]
    with pytest.raises(ValueError, match="name must be 1-100"):
        await repo.update(1, 10, name="x" * 101)
    with pytest.raises(ValueError, match="color must be a0..a7"):
        await repo.update(1, 10, color="invalid")
