"""Репозиторий групп/тегов доменов (TASK-0073, ADR 043)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, cast

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import CursorResult

from src.db.models import DomainGroup, UserDomain, UserDomainGroup
from src.db.repositories.base import BaseRepository


class GroupRepository(BaseRepository):
    """CRUD групп (scoped user_id) + membership attach/detach (idempotent) + counts."""

    async def create(
        self,
        user_id: int,
        *,
        name: str,
        kind: str,
        color: str | None = None,
        icon: str | None = None,
    ) -> DomainGroup:
        """Создаёт новую группу для пользователя."""
        if kind not in ("client", "personal"):
            raise ValueError("kind must be 'client' or 'personal'")
        name = name.strip()
        if not name or len(name) > 100:
            raise ValueError("name must be 1-100 chars")
        if color is not None and (not isinstance(color, str) or len(color) > 2 or color not in {f"a{i}" for i in range(8)}):
            raise ValueError("color must be a0..a7 or None")
        if icon is not None and (not isinstance(icon, str) or len(icon) > 32):
            raise ValueError("icon must be <=32 chars or None")
        row = DomainGroup(
            user_id=user_id,
            name=name,
            kind=kind,
            color=color,
            icon=icon,
        )
        self.session.add(row)
        await self.session.flush()
        await self.session.refresh(row)
        return row

    async def get(self, user_id: int, group_id: int) -> DomainGroup | None:
        """Возвращает группу, если принадлежит пользователю."""
        stmt = select(DomainGroup).where(DomainGroup.id == group_id, DomainGroup.user_id == user_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_for_user(self, user_id: int) -> Sequence[DomainGroup]:
        """Список групп пользователя (без counts)."""
        stmt = (
            select(DomainGroup)
            .where(DomainGroup.user_id == user_id)
            .order_by(DomainGroup.kind, DomainGroup.name)
        )
        res = await self.session.execute(stmt)
        return res.scalars().all()

    async def list_with_counts(self, user_id: int) -> list[tuple[DomainGroup, int]]:
        """Группы + кол-во доменов в каждой (один запрос, outerjoin + group_by, без N+1)."""
        stmt = (
            select(DomainGroup, func.count(UserDomainGroup.group_id).label("cnt"))
            .outerjoin(UserDomainGroup, UserDomainGroup.group_id == DomainGroup.id)
            .where(DomainGroup.user_id == user_id)
            .group_by(DomainGroup.id)
            .order_by(DomainGroup.kind, DomainGroup.name)
        )
        res = await self.session.execute(stmt)
        return [(row[0], int(row[1] or 0)) for row in res.all()]

    async def update(
        self,
        user_id: int,
        group_id: int,
        *,
        name: str | None = None,
        color: str | None = None,
        icon: str | None = None,
    ) -> DomainGroup | None:
        """Обновляет поля группы (scoped)."""
        grp = await self.get(user_id, group_id)
        if not grp:
            return None
        if name is not None:
            name = name.strip()
            if not name or len(name) > 100:
                raise ValueError("name must be 1-100 chars")
            grp.name = name
        if color is not None:
            if not isinstance(color, str) or len(color) > 2 or color not in {f"a{i}" for i in range(8)}:
                raise ValueError("color must be a0..a7 or None")
            grp.color = color
        if icon is not None:
            if not isinstance(icon, str) or len(icon) > 32:
                raise ValueError("icon must be <=32 chars or None")
            grp.icon = icon
        await self.session.flush()
        return grp

    async def delete(self, user_id: int, group_id: int) -> bool:
        """Удаляет группу (и membership каскадом). Возвращает True если была."""
        stmt = delete(DomainGroup).where(DomainGroup.id == group_id, DomainGroup.user_id == user_id)
        result = cast(CursorResult[Any], await self.session.execute(stmt))
        return (result.rowcount or 0) > 0

    async def attach(self, user_id: int, group_id: int, user_domain_id: int) -> bool:
        """Привязывает домен к группе (idempotent via ON CONFLICT DO NOTHING).
        Проверяет, что group и user_domain принадлежат user_id.
        Возвращает True если добавлена новая связь, False если уже была.
        """
        # ownership checks (prevent cross-user attach)
        grp = await self.get(user_id, group_id)
        if not grp:
            return False
        ud_stmt = select(UserDomain.id).where(
            UserDomain.id == user_domain_id, UserDomain.user_id == user_id
        )
        ud_res = await self.session.execute(ud_stmt)
        if ud_res.scalar_one_or_none() is None:
            return False

        stmt = (
            pg_insert(UserDomainGroup)
            .values(user_domain_id=user_domain_id, group_id=group_id)
            .on_conflict_do_nothing(
                index_elements=[UserDomainGroup.user_domain_id, UserDomainGroup.group_id]
            )
        )
        result = cast(CursorResult[Any], await self.session.execute(stmt))
        await self.session.flush()
        return (result.rowcount or 0) > 0

    async def detach(self, user_id: int, group_id: int, user_domain_id: int) -> bool:
        """Отвязывает домен от группы (scoped по user_id группы)."""
        grp = await self.get(user_id, group_id)
        if not grp:
            return False
        # optional: also verify ud ownership, but since group owned, membership will be deleted only if exists
        stmt = delete(UserDomainGroup).where(
            UserDomainGroup.group_id == group_id,
            UserDomainGroup.user_domain_id == user_domain_id,
        )
        result = cast(CursorResult[Any], await self.session.execute(stmt))
        await self.session.flush()
        return (result.rowcount or 0) > 0

    async def get_groups_for_domain(
        self, user_id: int, user_domain_id: int
    ) -> Sequence[DomainGroup]:
        """Список групп для конкретного user_domain (scoped)."""
        stmt = (
            select(DomainGroup)
            .join(UserDomainGroup, UserDomainGroup.group_id == DomainGroup.id)
            .where(
                DomainGroup.user_id == user_id,
                UserDomainGroup.user_domain_id == user_domain_id,
            )
            .order_by(DomainGroup.name)
        )
        res = await self.session.execute(stmt)
        return res.scalars().all()

    async def list_user_domain_ids_in_group(self, user_id: int, group_id: int) -> list[int]:
        """Список user_domain_id в группе (с проверкой владения группой)."""
        grp = await self.get(user_id, group_id)
        if not grp:
            return []
        stmt = select(UserDomainGroup.user_domain_id).where(UserDomainGroup.group_id == group_id)
        res = await self.session.execute(stmt)
        return [int(r[0]) for r in res.all()]

    async def groups_by_user_domain_ids(self, ud_ids: list[int]) -> dict[int, list[int]]:
        """Batch: ud_id -> list[group_id] (no user scope here, caller ensures)."""
        if not ud_ids:
            return {}
        stmt = select(UserDomainGroup.user_domain_id, UserDomainGroup.group_id).where(
            UserDomainGroup.user_domain_id.in_(ud_ids)
        )
        res = await self.session.execute(stmt)
        out: dict[int, list[int]] = {}
        for udid, gid in res.all():
            out.setdefault(int(udid), []).append(int(gid))
        return out
