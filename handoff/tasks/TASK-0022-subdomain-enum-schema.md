---
id: TASK-0022
title: Схема subdomain_enum_cache + миграция (ADR 037)
status: completed
milestone: v0.11.0
adr: 037
area: code
depends_on: [TASK-0021]
branch: task/0022-subdomain-enum-schema
owner: ""
session: docs/sessions/2026-05-30_task_0022_subdomain_enum_schema.md
pr: "15"
created: 2026-05-30
completed: 2026-05-30
---

# TASK-0022 — Схема subdomain_enum_cache (ADR 037)

> Тело самодостаточно. Перед стартом:
> `git checkout main && git pull --rebase origin main`, затем `claim`.
> `down_revision` сверить с актуальным alembic-head на свежем main.

## Цель

Хранилище результатов enumeration: одна запись на registrable-домен с
найденными поддоменами и TTL, чтобы повторные `/subdomains` не били crt.sh.

## Контекст

ADR 037: on-demand enumeration через crt.sh, результат кэшируется
per-registrable. Параллельная мини-подсистема (как ssl/dns/email-intel cache).

## Изменения по файлам

- Новая Alembic-миграция: таблица `subdomain_enum_cache`:
  - `registrable_domain` (Text, PK) — ключ (eTLD+1, ADR 035).
  - `subdomains` (JSONB) — список найденных поддоменов (нормализованных).
  - `fetched_at`, `next_check_at` (TIMESTAMP tz), `is_reachable` (Bool, nullable),
    `fail_count` (Int, default `0`), `last_error` (Text, nullable).
  - Индекс на `next_check_at` (под будущий мониторинг v0.12).
  - **Дефолты — валидным SQL-литералом** (урок TASK-0008): `now()`, `0` и т.п.
- `src/db/models.py` — модель `SubdomainEnumCache` (зеркалит миграцию; синхрон
  модель↔БД — без лишних server_default; anti-drift, CLAUDE.md).
- Репозиторий `src/db/repositories/` (get/upsert) по образцу email-intel/dns.

## Миграции БД

Требуется. Проверить применение на **Postgres** (smoke-test TASK-0009).

## Инварианты (защитить тестами)

- Миграция применяется на чистой БД и обратима (round-trip).
- Модель ↔ БД синхронны.

## Требования к тестам

- Модель-тест (наличие полей/дефолтов). Round-trip покрыт TASK-0009.

## Definition of Done

- [ ] Таблица + модель + репозиторий; синхрон модель↔миграция
- [ ] Миграция применяется на Postgres, обратима
- [ ] `pytest` зелёный; `ruff`/`black --check`/`mypy src` чисто
- [ ] Per-session отчёт; `handoff.py validate` OK; PR, CI зелёный

## Ссылки

- ADR 037; образец — `email_intel_cache` (TASK-0015), `dns_cache` (ADR 032).
