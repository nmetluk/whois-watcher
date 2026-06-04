"""Интеграционные тесты GroupRepository на реальном Postgres (TASK-0073).

Покрывают инварианты из тела таска:
- create/get скоупятся по user_id (чужую группу не видно);
- attach idempotent (повтор не плодит дубль на составном PK);
- ownership: нельзя положить чужой домен в свою группу и наоборот;
- detach снимает членство, не трогая домен/группу;
- cascade: удаление группы или user_domain каскадит membership;
- list_with_counts отдаёт корректные счётчики (один запрос).

Использует pytest-docker fixtures (real_db_session, TASK-0052). Вне CI/docker
gracefully skipped. Round-trip самой миграции покрыт test_migrations.py.
"""

from __future__ import annotations

import os

import pytest
from sqlalchemy import delete, func, select

from src.db.models import DomainGroup, User, UserDomain, UserDomainGroup
from src.db.repositories.groups import GroupRepository

pytestmark = pytest.mark.arq  # запускается вместе с интеграц. arq (pytest-docker)

_SKIP_REASON = "integration requires docker postgres (pytest-docker) or CI=1 with services"


async def _mk_user(session, telegram_id: int) -> User:
    user = User(telegram_id=telegram_id)
    session.add(user)
    await session.flush()
    return user


async def _mk_domain(session, user_id: int, domain: str) -> UserDomain:
    ud = UserDomain(user_id=user_id, domain=domain, registrable_domain=domain)
    session.add(ud)
    await session.flush()
    return ud


@pytest.mark.asyncio
async def test_create_get_scoped_by_user(real_db_session) -> None:
    if os.getenv("CI") != "1":
        pytest.skip(_SKIP_REASON)
    s = real_db_session
    owner = await _mk_user(s, 9_730_001)
    other = await _mk_user(s, 9_730_002)
    repo = GroupRepository(s)

    g = await repo.create(owner.id, name="Клиент А", kind="client", color="a1", icon="folder_special")
    assert g.id is not None
    # владелец видит
    assert (await repo.get(owner.id, g.id)) is not None
    # чужой — нет
    assert (await repo.get(other.id, g.id)) is None
    # невалидный kind
    with pytest.raises(ValueError):
        await repo.create(owner.id, name="x", kind="bogus")


@pytest.mark.asyncio
async def test_attach_idempotent_and_counts(real_db_session) -> None:
    if os.getenv("CI") != "1":
        pytest.skip(_SKIP_REASON)
    s = real_db_session
    owner = await _mk_user(s, 9_730_010)
    d1 = await _mk_domain(s, owner.id, "a-grp1.example")
    d2 = await _mk_domain(s, owner.id, "a-grp2.example")
    repo = GroupRepository(s)
    g = await repo.create(owner.id, name="G", kind="personal")

    # первый attach — новая связь
    assert await repo.attach(owner.id, g.id, d1.id) is True
    # повтор — idempotent, без дубля и без краша на составном PK
    assert await repo.attach(owner.id, g.id, d1.id) is False
    await repo.attach(owner.id, g.id, d2.id)

    # ровно 2 членства
    cnt = await s.scalar(
        select(func.count()).select_from(UserDomainGroup).where(UserDomainGroup.group_id == g.id)
    )
    assert cnt == 2

    # list_with_counts отражает 2
    pairs = await repo.list_with_counts(owner.id)
    by_id = {grp.id: c for grp, c in pairs}
    assert by_id[g.id] == 2


@pytest.mark.asyncio
async def test_ownership_cross_user_blocked(real_db_session) -> None:
    if os.getenv("CI") != "1":
        pytest.skip(_SKIP_REASON)
    s = real_db_session
    owner = await _mk_user(s, 9_730_020)
    other = await _mk_user(s, 9_730_021)
    repo = GroupRepository(s)

    owner_group = await repo.create(owner.id, name="OG", kind="client")
    other_domain = await _mk_domain(s, other.id, "foreign.example")
    owner_domain = await _mk_domain(s, owner.id, "own.example")
    other_group = await repo.create(other.id, name="XG", kind="client")

    # чужой домен в свою группу — нельзя
    assert await repo.attach(owner.id, owner_group.id, other_domain.id) is False
    # свой домен в чужую группу — нельзя (группа не принадлежит owner)
    assert await repo.attach(owner.id, other_group.id, owner_domain.id) is False
    # ничего не привязалось (скоупим к группам этого теста — БД общая между тестами)
    cnt = await s.scalar(
        select(func.count())
        .select_from(UserDomainGroup)
        .where(UserDomainGroup.group_id.in_([owner_group.id, other_group.id]))
    )
    assert cnt == 0


@pytest.mark.asyncio
async def test_detach_keeps_domain_and_group(real_db_session) -> None:
    if os.getenv("CI") != "1":
        pytest.skip(_SKIP_REASON)
    s = real_db_session
    owner = await _mk_user(s, 9_730_030)
    d = await _mk_domain(s, owner.id, "detach.example")
    repo = GroupRepository(s)
    g = await repo.create(owner.id, name="D", kind="personal")
    await repo.attach(owner.id, g.id, d.id)

    assert await repo.detach(owner.id, g.id, d.id) is True
    # членства нет (для этой группы), но домен и группа на месте
    assert (
        await s.scalar(
            select(func.count()).select_from(UserDomainGroup).where(UserDomainGroup.group_id == g.id)
        )
    ) == 0
    assert (await repo.get(owner.id, g.id)) is not None
    assert (await s.get(UserDomain, d.id)) is not None


@pytest.mark.asyncio
async def test_cascade_on_group_and_domain_delete(real_db_session) -> None:
    if os.getenv("CI") != "1":
        pytest.skip(_SKIP_REASON)
    s = real_db_session
    owner = await _mk_user(s, 9_730_040)
    d = await _mk_domain(s, owner.id, "cascade.example")
    repo = GroupRepository(s)

    # cascade при удалении ГРУППЫ
    g1 = await repo.create(owner.id, name="C1", kind="personal")
    await repo.attach(owner.id, g1.id, d.id)
    assert await repo.delete(owner.id, g1.id) is True
    assert (
        await s.scalar(
            select(func.count()).select_from(UserDomainGroup).where(UserDomainGroup.group_id == g1.id)
        )
    ) == 0

    # cascade при удалении ДОМЕНА
    g2 = await repo.create(owner.id, name="C2", kind="personal")
    await repo.attach(owner.id, g2.id, d.id)
    await s.execute(delete(UserDomain).where(UserDomain.id == d.id))
    await s.flush()
    # membership ушёл, но сама группа осталась
    assert (
        await s.scalar(
            select(func.count()).select_from(UserDomainGroup).where(UserDomainGroup.group_id == g2.id)
        )
    ) == 0
    assert (await repo.get(owner.id, g2.id)) is not None
