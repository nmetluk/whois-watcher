---
id: TASK-0009
title: Smoke-test Alembic-миграций на эфемерном Postgres в CI
status: open
milestone: v0.9.0
adr: 035
area: infra
depends_on: [TASK-0008]
branch: ""
owner: ""
session: ""
pr: ""
created: 2026-05-29
---

# TASK-0009 — Smoke-test миграций на эфемерном Postgres в CI

> 🟠 high. Тело самодостаточно. Перед стартом:
> `git checkout main && git pull --rebase origin main`, затем `claim`.

## Цель

CI прогоняет `alembic upgrade head` (и `downgrade base`) на эфемерном
PostgreSQL при каждом PR, чтобы дефекты DDL/backfill ловились автоматически,
а не в проде.

## Контекст / корень проблемы

Повторный аудит нашёл критичную миграцию, которая падает на Postgres
(`""` → zero-length identifier; пустой `DEFAULT`) — см. TASK-0008. Она прошла
«зелёный» CI, потому что **миграции не покрыты ни одним тестом**:
`tests/conftest.py` прямо заявляет «фактических подключений к БД/Redis тесты
не делают», таблицы через Alembic не создаются.

**Важно (проверено при аудите):** инфраструктура в CI уже готова —
`.github/workflows/ci.yml` поднимает `services: postgres` (postgres:16,
user/db `whoiswatcher`, pass `testpass`, `localhost:5432`) и `redis:7`, а шаг
`pytest` уже получает `POSTGRES_HOST/PORT/USER/PASSWORD/DB`. Комментарий в
ci.yml (строки 20-22) даже обещает «проверку, что миграции применяются» — но
самого теста нет. **Поднимать сервис не нужно**; нужен только тест.

## Изменения по файлам

- `tests/integration/test_migrations.py` (новый) — собирает `DATABASE_URL`
  из существующих `POSTGRES_*` env (как `src/config/settings.py`) и прогоняет
  `alembic upgrade head` → `downgrade base` → `upgrade head` (round-trip)
  через `alembic.config.Config` + `alembic.command`. Если БД недоступна
  (локальный прогон без Postgres) — `pytest.skip`; в CI Postgres есть всегда.
- `.github/workflows/ci.yml` — сервис **не добавлять** (уже есть); убедиться,
  что env pytest-шага достаточно для сборки DATABASE_URL. Опционально —
  отдельный шаг `Migrations smoke`.
- При необходимости — фикстура в `tests/integration/conftest.py`.

## Миграции БД

Не требуется (тестовая инфраструктура).

## Инварианты (защитить тестами)

- `upgrade head` на чистой БД проходит для всей цепочки ревизий.
- `downgrade base` обратим без ошибок (round-trip).
- Единственный alembic-head (нет ветвлений).

## Требования к тестам

- Тест реально подключается к Postgres (не sqlite — sqlite молча принимает
  `""` как строку и маскирует ровно тот баг, что в TASK-0008).

## Definition of Done

- [ ] Тест миграций реально гоняет Postgres и проходит на исправленной цепочке
- [ ] Подключается к существующему postgres-сервису ci.yml; job зелёный
- [ ] Локально без Postgres тест аккуратно skip-ается
- [ ] Per-session отчёт в `docs/sessions/`
- [ ] `handoff.py validate` проходит; PR открыт, CI зелёный

## Ссылки

- Аудит: `handoff/audits/AUDIT-2026-05-29-v0-9-0-poddomeny-psl.md`
- Связанные: TASK-0008 (исправляемая миграция)
