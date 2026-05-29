---
id: TASK-0008
title: Убрать server_default с registrable_domain в миграции
status: claimed
milestone: v0.9.0
adr: ""
area: code
depends_on: [TASK-0007]
branch: task/0008-registrable-server-default-fix
owner: ""
session: docs/sessions/2026-05-29_task-0008_registrable_server_default.md
pr: https://github.com/nmetluk/whois-watcher/pull/5
created: 2026-05-29
---

# TASK-0008 — Убрать server_default с registrable_domain в миграции

> Тело должно быть самодостаточным: исполнитель в новой сессии НЕ видел
> чат архитектора и не имеет другого контекста, кроме этого файла,
> `handoff/STATE.md` и репозитория.
>
> **Перед стартом (обязательно, см. `handoff/README.md`):**
> `git checkout main && git pull --rebase origin main` → только потом
> `claim`. Ветка от устаревшего main откатывает чужую работу. Статусы —
> только через `handoff.py status` (без `completed`). Миграции —
> `down_revision` сверить с актуальным alembic-head на свежем main.

## Цель

Убрать рассинхрон между миграцией и моделью: колонка `registrable_domain`
в миграции имеет `server_default=""`, но модель его не имеет. После того
как код начал заполнять поле при вставке, server_default не нужен.

## Контекст / корень проблемы

**Finding из AUDIT-2026-05-29:**

- Миграция `20260529_registrable_domain` содержит:
  ```python
  sa.Column("registrable_domain", sa.Text(), nullable=False, server_default=sa.text(""))
  ```
- Модель `UserDomain` в `src/db/models.py` содержит:
  ```python
  registrable_domain: Mapped[str] = mapped_column(Text, nullable=False)
  ```
- **Проблема:** Разные дефолты на уровне БД и ORM. Если вставка пойдёт мимо
  кода (raw SQL, другая миграция), БД может создать строку с пустым
  `registrable_domain`, нарушая инвариант приложения (registrable должен
  быть вычислен из domain через PSL).

## Изменения по файлам

### Новая миграция `migrations/versions/YYYYMMDD_HHMM_remove_registrable_server_default.py`

```python
"""Remove server_default from registrable_domain.

Revision ID: remove_registrable_server_default
Revises: 20260529_registrable_domain
Create Date: 2026-05-29

TASK-0008 — убрать server_default с registrable_domain.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "remove_registrable_server_default"
down_revision: str | None = "20260529_registrable_domain"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Убираем server_default — поле теперь заполняется только кодом.
    op.alter_column("user_domains", "registrable_domain", server_default=None)


def downgrade() -> None:
    # Восстанавливаем server_default для отката.
    op.alter_column(
        "user_domains", "registrable_domain", server_default=sa.text("")
    )
```

## Миграции БД

Требуется. Новая миграция убирает `server_default` с существующей колонки.
Backfill не нужен — все существующие строки уже имеют непустой `registrable_domain`
(из изначального backfill в `20260529_registrable_domain`).

## Инварианты (защитить тестами)

- После миграции `ALTER COLUMN` таблица остаётся в консистентном состоянии:
  все строки имеют непустой `registrable_domain`.
- Вставка через ORM (`DomainRepository.create_for_user`) заполняет
  `registrable_domain` корректно.

## Требования к тестам

- Добавить интеграционный тест: проверка что миграция `remove_registrable_server_default`
  применяется без ошибок на свежей БД.
- Убедиться что существующие тесты `test_domain_service.py` покрывают заполнение
  `registrable_domain` при вставке.

## Definition of Done

- [ ] Код реализован по спецификации выше
- [ ] `pytest` зелёный (полный прогон)
- [ ] `ruff` / `black --check` / `mypy src` чисто
- [ ] Миграция применяется на чистой БД
- [ ] Per-session отчёт создан в `docs/sessions/` и вписан в `session:`
- [ ] `handoff.py validate` проходит
- [ ] PR открыт по шаблону, CI зелёный

## Ссылки

- Аудит: `handoff/audits/AUDIT-2026-05-29-v0-9-0-poddomeny-psl.md`
- Миграция: `migrations/versions/20260529_0000_add_registrable_domain_fields.py`
- Связанные таски: TASK-0007 (аудит)
