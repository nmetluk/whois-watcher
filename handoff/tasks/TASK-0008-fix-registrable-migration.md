---
id: TASK-0008
title: Починить миграцию registrable_domain (не применяется на Postgres)
status: claimed
milestone: v0.9.0
adr: 035
area: code
depends_on: [TASK-0007]
branch: task/0008-fix-registrable-migration
owner: claude
session: "docs/sessions/2026-05-29_task-0008_fix_registrable_migration.md"
pr: "https://github.com/nmetluk/whois-watcher/pull/6"
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

## ⛔ Ревью PR #5 — ОТКЛОНЁН. Переделать по этой спеке

Первая попытка (ветка `task/0008-registrable-server-default-fix`, PR #5)
**не принята**. Что сделано не так:

1. Добавлена **новая** миграция `20260529_0001_remove_registrable_server_default`
   с `op.alter_column(... server_default=None)`, а исходная
   `20260529_0000_add_registrable_domain_fields.py` **оставлена сломанной**.
   `alembic upgrade head` выполняет ревизии по порядку: `_0000` падает первой
   (пустой `DEFAULT` + backfill `WHERE … = ""`), и `_0001` никогда не
   выполняется. Корень не починен.
2. Ветка отрезана от **устаревшего main** (до коммита `b27700e`): правит файл
   таска `TASK-0008-registrable-server-default-fix.md`, которого на актуальном
   main уже нет, и расходится по `INDEX.md`.
3. «710 тестов проходят» проблему не закрывает — миграции тестами не покрыты
   (это TASK-0009), а sqlite молча принимает `""` как строку и прячет баг.

**Действия для переделки:**

- Начать с **чистого свежего main** и **новой** ветки
  `task/0008-fix-registrable-migration` (старую ветку/PR #5 закрыть).
- **Удалить** добавленную `20260529_0001_remove_registrable_server_default.py`.
- Чинить **in-place в `..._0000`** (см. «Изменения по файлам» ниже).
- Проверить реально на **Postgres** (`alembic upgrade head` → `downgrade`),
  не на sqlite.
- mypy-фикс в `whois.py` из PR #5 можно перенести, но лучше отдельным
  коммитом/таском — не мешать его с миграцией.

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
