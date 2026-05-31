---
id: TASK-0039
title: Deep email — on-demand ARQ-задача + кэш с коротким TTL
status: done
milestone: v0.13.0
adr: 040
area: code
depends_on: [TASK-0038]
branch: task/0039-deep-email-arq-cache
owner: claude-code
session: docs/sessions/2026-05-31_task-0039-deep-email-arq-cache.md
pr: ""
created: 2026-05-31
completed: 2026-05-31
---

> ## ✅ Ревью архитектора (2026-05-31) — merged
>
> Миграция `email_deep_cache` корректна: `down_revision=20260530_subdomain_monitor`
> (единственный head), обратима (drop_table), дефолты SQL-литералами. Задача
> `check_email_deep`: redis-guard NX, вызов `fetch_deep_email`, upsert с TTL,
> `update_fail`, graceful. Тесты со `spec`/AsyncMock.
> **Два пункта на доработку в TASK-0041 (не блокеры):** (1) `fetch_deep_email`
> вызывается **без `mx_hosts`** → DANE сейчас всегда пустой; в 0041 передать
> MX из базового `email_intel_cache`. (2) Freshness-гейт (не бить сеть в окне
> TTL) — сама задача всегда фетчит; проверку свежести `next_check_at` сделать
> в хэндлере 0041 перед enqueue.

# TASK-0039 — Deep email: ARQ-задача + кэш (ADR 040)

> Тело самодостаточно. Перед стартом:
> `git checkout main && git pull --rebase origin main`, затем `claim`.
> Контекст — ADR 040; зависит от TASK-0038 (парсеры/коллекторы).

## Цель

ARQ-задача `check_email_deep`, которая по запросу собирает углублённый
почтовый разбор (через коллекторы TASK-0038), кэширует результат с **коротким
TTL** (повторное нажатие в окне TTL не бьёт DNS/HTTP) и защищена redis-флагом.

## Контекст / корень проблемы

ADR 040: deep email — **on-demand** (не периодический мониторинг). Сбор тяжелее
базового (HTTP к mta-sts, TLSA per-MX), поэтому через ARQ + «⏳ ищу…» (UX — в
TASK-0041), а результат — в кэше, чтобы не дёргать сеть повторно.

## Изменения по файлам

- `migrations/versions/<новая>.py` — таблица `email_deep_cache` (PK `domain`,
  JSONB-поля под результаты SPF-resolution/MTA-STS/TLS-RPT/DANE/BIMI,
  `fetched_at`, `next_check_at`/TTL, reachability/fail-поля). Дефолты —
  SQL-литералами (урок TASK-0008); **down_revision сверить с актуальным
  alembic-head на свежем main**; round-trip на Postgres (TASK-0009).
- `src/db/models.py` + `src/db/repositories/email_deep_cache.py` — модель +
  репозиторий (`get`, `upsert`, `update_fail`).
- `src/tasks/check_email_deep.py` — ARQ-задача: redis-guard
  `email_deep_in_progress:<domain>`, вызов коллекторов, upsert в кэш,
  graceful degradation; возврат статуса для хэндлера.
- `src/tasks/arq_config.py` — регистрация функции (on-demand, **без cron**).

## Миграции БД

Да — `email_deep_cache`. Применяется на Postgres, обратима, round-trip-smoke
в CI. Дефолты SQL-литералами.

## Инварианты (защитить тестами)

- Redis-guard: параллельный запуск для одного домена → ранний выход.
- TTL: свежий кэш в окне TTL → задача не бьёт сеть (или хэндлер не enqueue'ит —
  зафиксировать, где именно проверяется свежесть).
- Ошибка коллектора → `update_fail` + сохранённое «недоступно», без падения.
- Миграция round-trip на Postgres.

## Требования к тестам

- Unit на задачу (моки коллекторов/сессии/redis со `spec`/`autospec`),
  репозиторий round-trip, миграция (CI-smoke на Postgres).

## Definition of Done

- [ ] Код + миграция реализованы
- [ ] `pytest` зелёный; миграция применяется на чистой Postgres
- [ ] `ruff` / `black --check` / `mypy src` чисто
- [ ] Per-session отчёт в `docs/sessions/`
- [ ] `handoff.py validate` проходит; PR открыт, CI зелёный

## Ссылки

- ADR: `docs/decisions.md` (ADR 040)
- Образцы: `src/tasks/check_subdomains.py`, `src/db/repositories/subdomain_enum_cache.py`
- Связанные: TASK-0038 (коллекторы), TASK-0041 (UX-кнопка)
