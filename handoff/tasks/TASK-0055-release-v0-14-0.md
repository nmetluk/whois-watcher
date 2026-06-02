---
id: TASK-0055
title: Релиз v0.14.0 — стабилизация (FSM/Redis, html.escape, тех-долг)
status: done
milestone: v0.14.0
adr: 041
area: docs
depends_on: [TASK-0054]
branch: ""
owner: architect
session: ""
pr: ""
created: 2026-06-04
completed: 2026-06-08
---

> **Итог (2026-06-08):** релиз сделан архитектором напрямую на main — bump
> `pyproject` 0.13.0→0.14.0, секция CHANGELOG `[0.14.0]`, аннотированный тег
> `v0.14.0`. Деплой — отдельным шагом (`bash scripts/deploy.sh`).

# TASK-0055 — Релиз v0.14.0 (стабилизация)

> Тело самодостаточно. Перед стартом:
> `git checkout main && git pull --rebase origin main`, затем `claim`.
> **Гейт:** аудит TASK-0054 — вердикт go; TASK-0049…0053 смержены; CI зелёный.

## Цель

Выпустить минорный релиз **v0.14.0** — стабилизация/тех-долг (без новых
пользовательских фич): FSM→Redis (ADR 041), html.escape во всех нотификациях,
DENIC-значок, интеграционные тесты, доки.

## Изменения по файлам

- `pyproject.toml` — bump `version` `0.13.0` → `0.14.0`.
- `CHANGELOG.md` — секция `## [0.14.0]`: FSM-state в Redis (переживает рестарт,
  TTL), html.escape во всех change-нотификациях, значок «expiry скрыт реестром»
  (DENIC), интеграционные тесты ARQ (pytest-docker), MIGRATIONS.md + нормы
  алертов.
- `STATE.md` — отметить релиз.

## Definition of Done

- [ ] Предусловия (0049–0053 в main, аудит go, CI зелёный)
- [ ] `pyproject` bump → 0.14.0; секция CHANGELOG `[0.14.0]`
- [ ] Аннотированный тег `v0.14.0`; деплой (`bash scripts/deploy.sh`)
- [ ] `handoff.py validate`; STATE обновлён; PR + зелёный CI

## Ссылки

- ADR 041; аудит TASK-0054; образец релиза — TASK-0044
