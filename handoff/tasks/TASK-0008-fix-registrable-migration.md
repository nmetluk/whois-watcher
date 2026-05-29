---
id: TASK-0008
title: Починить миграцию registrable_domain (не применяется на Postgres)
status: open
milestone: v0.9.0
adr: 035
area: code
depends_on: [TASK-0007]
branch: ""
owner: ""
session: ""
pr: ""
created: 2026-05-29
---

# TASK-0008 — Починить миграцию registrable_domain (🔴 не применяется на Postgres)

> 🔴 critical (эскалировано с medium при повторном аудите — см. дополнение в
> `handoff/audits/AUDIT-2026-05-29-v0-9-0-poddomeny-psl.md`). Тело
> самодостаточно: исполнитель видит только этот файл, `handoff/STATE.md`,
> отчёт аудита и репозиторий.
>
> **Перед стартом:** `git checkout main && git pull --rebase origin main`,
> затем `python scripts/handoff.py claim TASK-0008 --owner <agent>`.
> `down_revision` сверить с актуальным alembic-head на свежем main.

## Цель

Миграция `20260529_0000_add_registrable_domain_fields.py` применяется на
чистом PostgreSQL без ошибок; схема `user_domains` совпадает с моделью
(`registrable_domain` NOT NULL, без `server_default` после backfill).

## Контекст / корень проблемы

Первый аудит (TASK-0007) расценил проблему как **medium** — «косметический
рассинхрон `server_default`». Повторная проверка с offline-рендером alembic
показала, что миграция **вообще не применяется на PostgreSQL**. Реальный SQL,
который alembic отправляет в БД:

```sql
ALTER TABLE user_domains ADD COLUMN registrable_domain TEXT DEFAULT  NOT NULL;   -- пустой DEFAULT
ALTER TABLE user_domains ADD COLUMN is_subdomain BOOLEAN DEFAULT false NOT NULL; -- корректно (для сравнения)
UPDATE user_domains SET registrable_domain = domain WHERE registrable_domain = "";
```

Два дефекта в `migrations/versions/20260529_0000_add_registrable_domain_fields.py`:

1. **Пустой `DEFAULT`.** `server_default=sa.text("")` (для `registrable_domain`)
   рендерится в `DEFAULT  NOT NULL` — пустая default-клауза. Это невалидный
   DDL для Postgres (после `DEFAULT` ожидается выражение; `is_subdomain` рядом
   с `sa.text("false")` рендерится корректно — наглядный контраст).
2. **Двойные кавычки в backfill.** `WHERE registrable_domain = ""` — в
   PostgreSQL `""` это **идентификатор нулевой длины** →
   `ERROR: zero-length delimited identifier`. Должен быть строковый литерал
   `''` (одинарные кавычки).

Почему пропущено: миграции не покрыты ни одним тестом (см. TASK-0009),
`conftest.py` к реальной БД не подключается, sqlite молча принимает `""` как
строку — баг не виден без Postgres.

## Изменения по файлам

- `migrations/versions/20260529_0000_add_registrable_domain_fields.py`
  (правка in-place — на прод не раскатывалась, история чистая):
  - `registrable_domain`: `server_default=sa.text("''")` (строковый литерал),
    `nullable=False`.
  - Backfill: `UPDATE user_domains SET registrable_domain = domain WHERE
    registrable_domain = ''` (одинарные кавычки; либо
    `... WHERE registrable_domain IS NULL OR registrable_domain = ''`).
  - **После backfill снять server_default** (модель его не имеет):
    `op.alter_column("user_domains", "registrable_domain", server_default=None)`.
  - `is_subdomain` не трогать (корректен), `downgrade()` не трогать.

## Миграции БД

Правка существующей миграции, без новой ревизии. `down_revision="20260519_dns"`
— сверить с актуальным alembic-head перед стартом.

## Инварианты (защитить тестами)

- `alembic upgrade head` на чистом Postgres проходит без ошибок.
- После миграции `registrable_domain` — NOT NULL, без `server_default`.
- Backfill: существующие apex-домены → `registrable_domain = domain`,
  `is_subdomain = false`.

## Требования к тестам

- Покрывается smoke-тестом миграций из **TASK-0009**. Если 0009 ещё не
  смержен — добавить здесь минимальный прогон `upgrade head`/`downgrade base`
  на эфемерном Postgres (сервис в `ci.yml` уже есть).

## Definition of Done

- [ ] Миграция применяется на чистой БД (Postgres), `downgrade` обратим
- [ ] Схема совпадает с моделью (NOT NULL, без server_default)
- [ ] `pytest` зелёный, `ruff` / `black --check` / `mypy src` чисто
- [ ] Per-session отчёт в `docs/sessions/`, вписан в `session:`
- [ ] `handoff.py validate` проходит; PR открыт, CI зелёный
- [ ] Только после этого — тег v0.9.0

## Ссылки

- Аудит (+ дополнение): `handoff/audits/AUDIT-2026-05-29-v0-9-0-poddomeny-psl.md`
- Миграция: `migrations/versions/20260529_0000_add_registrable_domain_fields.py`
- Связанные: TASK-0007 (аудит), TASK-0009 (CI smoke-test миграций)
