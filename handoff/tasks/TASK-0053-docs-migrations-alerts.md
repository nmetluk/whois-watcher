---
id: TASK-0053
title: Доки — MIGRATIONS.md + нормы дедупликации алертов (ADR 019)
status: in_review
milestone: v0.14.0
adr: ""
area: docs
depends_on: []
branch: task/0053-docs-migrations-alerts
owner: grok-4.3
session: docs/sessions/2026-06-08_task-0053-docs-migrations-alerts.md
pr: ""
created: 2026-06-04
---

# TASK-0053 — Доки: миграции + нормы алертов (v0.14)

> Тело самодостаточно. Перед стартом:
> `git checkout main && git pull --rebase origin main`, затем `claim`.

## Цель

Закрыть два docs-долга: гайд по миграциям и описание норм дедупликации алертов.

## Изменения по файлам

- `MIGRATIONS.md` (новый) — как создавать/проверять миграции: autogenerate,
  правило SQL-литералов в дефолтах (урок TASK-0008), `down_revision` от
  актуального head, single-head, round-trip smoke на Postgres (TASK-0009),
  чек-лист перед PR.
- `docs/decisions.md` (ADR 019) или отдельный раздел — задокументировать нормы
  дедупликации админ-алертов: какие severity и частоту считаем нормальными,
  окно дедупа в Redis (сейчас только в коде `src/services/alerts.py`).

## Миграции БД

Не требуется.

## Definition of Done

- [ ] `MIGRATIONS.md` написан; нормы алертов задокументированы
- [ ] Ссылки из CLAUDE.md/README при необходимости
- [ ] Per-session отчёт; `handoff.py validate`; PR

## Ссылки

- TODO.md (tech-debt: MIGRATIONS.md, ADR 019 нормы)
- `src/services/alerts.py`; TASK-0008/0009
