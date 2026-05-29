---
id: TASK-0014
title: Релиз v0.9.1 — починенная миграция + CI/mypy фиксы
status: done
milestone: v0.9.1
adr: ""
area: docs
depends_on: [TASK-0009]
branch: task/0014-release-v0-9-1
owner: claude
session: docs/sessions/2026-05-29_task-0014_release_v0.9.1.md
pr: "9"
created: 2026-05-29
---

# TASK-0014 — Релиз v0.9.1

> Тело самодостаточно. Перед стартом:
> `git checkout main && git pull --rebase origin main`, затем `claim`.

## Цель

Выпустить патч-релиз **v0.9.1**, который содержит починенную миграцию
registrable и сопутствующие CI/mypy фиксы. Опубликованный тег `v0.9.0`
**не трогать** (он указывает на коммит `c3abd78` со сломанной миграцией —
переписывать опубликованные теги нельзя).

## Контекст / корень проблемы

Тег `v0.9.0` создан **до** аудита и содержит миграцию
`20260529_0000_add_registrable_domain_fields.py` в сломанном виде
(`server_default=sa.text("")` + backfill `WHERE registrable_domain = ""`),
которая не применяется на PostgreSQL. CHANGELOG-секция `[0.9.0]` при этом
утверждает «Применяется на чистой БД без потерь» — на момент тега неверно.

После аудита влиты фиксы (на main, после тега): TASK-0008 (PR #6) — миграция
починена in-place; TASK-0013 (PR #8) — mypy narrowing в `whois.py`; TASK-0009
(PR #7) — CI smoke-test миграций на Postgres + `env.py
disable_existing_loggers=False` + subprocess-изоляция. CI на main зелёный.
Эти фиксы надо выпустить как v0.9.1.

## Изменения по файлам

- `pyproject.toml` — `version = "0.9.1"`.
- `CHANGELOG.md`:
  - Добавить секцию `## [0.9.1] — 2026-05-29` с разделом `### Fixed`:
    - Миграция `20260529_registrable_domain` теперь применяется на
      PostgreSQL (строковый литерал `''` вместо `""`, валидный
      `server_default` + снятие после backfill) — TASK-0008.
    - `mypy`: устранён type-narrowing в `src/bot/handlers/whois.py` — шаг
      `mypy` в CI снова зелёный (TASK-0013).
    - CI: добавлен smoke-test Alembic-миграций на Postgres; alembic больше
      не гасит логгеры приложения (`disable_existing_loggers=False`);
      миграционный тест изолирован в subprocess (TASK-0009).
  - В секции `[0.9.0]` поправить утверждение про миграцию: пометить, что в
    0.9.0 миграция была дефектной и исправлена в 0.9.1 (или убрать ложную
    фразу «Применяется на чистой БД без потерь»).
  - Обновить ссылки сравнения версий внизу файла, если они ведутся.

## Миграции БД

Не требуется (релизная бухгалтерия). Сама миграция уже починена в TASK-0008.

## Тег и публикация

После merge PR в `main`:
- Создать аннотированный тег `v0.9.1` на merge-коммите:
  `git tag -a v0.9.1 -m "v0.9.1 — fixed registrable migration + CI/mypy"`
- `git push origin v0.9.1`.
- (Тег `v0.9.0` оставить как есть.)

> Кто тегает — по процессу решает архитектор при мерже PR. Исполнитель
> готовит версию+CHANGELOG в ветке и PR; тег ставится на смерженный main.

## Definition of Done

- [ ] `pyproject.toml` → 0.9.1; CHANGELOG секция [0.9.1] заполнена, [0.9.0]
      исправлена
- [ ] `ruff` / `black --check` / `mypy src` чисто; `pytest` (с `CI=1` и
      Postgres) зелёный
- [ ] `handoff.py validate` проходит; PR открыт, CI зелёный
- [ ] После merge — тег `v0.9.1` создан и запушен
- [ ] Per-session отчёт в `docs/sessions/`

## Ссылки

- Аудит: `handoff/audits/AUDIT-2026-05-29-v0-9-0-poddomeny-psl.md`
- Связанные: TASK-0008 (миграция), TASK-0009 (CI-тест), TASK-0013 (mypy)
