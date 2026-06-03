---
id: TASK-0057
title: Аудит-лог — таблица audit_log + репозиторий + helper audit()
status: done
milestone: v0.15.0
adr: 042
area: code
depends_on: []
branch: task/0057-audit-log-schema
owner: grok-4.3
session: docs/sessions/2026-06-09_task-0057-audit-log-schema.md
pr: 39
created: 2026-06-08
completed: 2026-06-09
---

> ✅ Ревью архитектора (2026-06-09) — merged. Миграция `20260609_audit_log`
> (down_revision=email_deep, single-head, обратима, SQL-литералы); `audit()`
> best-effort (try/except, никогда не бросает); модель в стиле SystemEvent.

# TASK-0057 — audit_log: схема + репозиторий + helper (ADR 042)

> Тело самодостаточно. Перед стартом:
> `git checkout main && git pull --rebase origin main`, затем `claim`.
> Контекст — ADR 042. Перед миграцией прочитай `MIGRATIONS.md`.

## Цель

Таблица `audit_log` для разбора нештатных ситуаций + репозиторий + best-effort
helper `audit(...)`, который вписывается в инцидент-точки (TASK-0061).

## Контекст

`system_events` — аналитика для сводок (retention 30д). `audit_log` —
**инциденты с контекстом** (retention 90д). Это разные таблицы (ADR 042).

## Готовые факты (сверено архитектором)

- Образец модели — `SystemEvent` (`src/db/models.py`): `id BigInteger` PK
  autoincrement, поля `String(...)`, `details JSONB nullable`, `created_at
  DateTime(timezone=True) server_default=func.now()` + индексы. `audit_log`
  делать **в том же стиле**, но это **отдельная** таблица (system_events —
  аналитика, retention 30д; audit_log — инциденты, 90д). Не сливать.
- Репозиторий — паттерн из `src/db/repositories/` (наследовать `BaseRepository`,
  `self.session`). Регистрация в `repositories/__init__.py`.

## Изменения по файлам

- `migrations/versions/<new>.py` — таблица `audit_log`: `id` PK,
  `created_at timestamptz NOT NULL server_default now()` (+index),
  `level` (text: info|warning|error|critical), `category` (text:
  task_failure|rate_limit|admin_action|webhook|startup|other),
  `actor` (text, nullable: user_id или "system"), `message` (text),
  `context` (JSONB, nullable). Index по `(category, created_at)`.
  `down_revision` от актуального head; SQL-литералы в дефолтах (урок 0008);
  round-trip на Postgres.
- `src/db/models.py` — модель `AuditLog`.
- `src/db/repositories/audit_log.py` — `AuditLogRepository` (`record(...)`,
  `delete_older_than(days)`); регистрация в `repositories/__init__.py`.
- `src/services/audit.py` — `async def audit(level, category, message, *,
  actor=None, context=None) -> None`: **best-effort** (всё внутри в try/except,
  никогда не бросает — не ломает горячий путь); открывает свою сессию.
  Не логировать секреты/контакты/заметки в context (ADR 019).

## Миграции БД

Да — `audit_log`. Применяется на Postgres, обратима, round-trip-smoke в CI.

## Инварианты (защитить тестами)

- `audit()` не пробрасывает исключение (например, при сбое сессии — глотает).
- `record`/`delete_older_than` работают (unit + интеграц. на реальном PG —
  можно опереться на pytest-docker из TASK-0052).
- Миграция round-trip.

## Definition of Done

- [ ] Схема + модель + репозиторий + `audit()`; миграция применяется/обратима
- [ ] **Полный `pytest` зелёный**; `ruff`/`black`/`mypy`
- [ ] Per-session отчёт; `handoff.py validate`; PR + зелёный CI

## Ссылки

- ADR 042; `MIGRATIONS.md`; `src/db/models.py` (`SystemEvent` как образец)
- Связанные: TASK-0061 (вписать audit() + retention)
