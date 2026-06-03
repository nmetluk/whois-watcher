---
id: TASK-0063
title: Релиз v0.15.0 — админ/ops-слой (бекапы, отчёты, аудит-лог)
status: done
milestone: v0.15.0
adr: 042
area: docs
depends_on: [TASK-0062]
branch: ""
owner: architect
session: docs/sessions/2026-06-09_task-0063-release-v0-15-0.md
pr: ""
created: 2026-06-08
completed: 2026-06-09
---

> **Итог (2026-06-09):** релиз сделан архитектором — bump 0.14.0→0.15.0, секция
> CHANGELOG `[0.15.0]`, тег `v0.15.0`. Деплой: пересобрать образ (pg-client-16),
> том `ww_backups`, env. Подтвердить зелёный CI перед деплоем.

# TASK-0063 — Релиз v0.15.0 (ADR 042)

> Тело самодостаточно. Перед стартом:
> `git checkout main && git pull --rebase origin main`, затем `claim`.
> **Гейт:** аудит TASK-0062 — вердикт go; TASK-0057…0061 смержены; CI зелёный.

## Цель

Выпустить минорный релиз **v0.15.0** — админ/ops-слой (бекапы, ежечасный/дневной
отчёты, аудит-лог).

## Изменения по файлам

- `pyproject.toml` — bump `version` 0.14.0 → 0.15.0.
- `CHANGELOG.md` — секция `## [0.15.0]`: ежечасные бекапы Postgres (rotate 36,
  verify), ежечасный ops-отчёт + статус бекапа, дневной графический отчёт
  21:00 МСК (matplotlib), аудит-лог (`audit_log`, retention 90д). Отметить
  deploy-нюансы: pg-client в образе, новый том `backups`, новые env.
- `STATE.md` — отметить релиз.

## Definition of Done

- [ ] Предусловия (0057–0061 в main, аудит go, CI зелёный)
- [ ] bump → 0.15.0; секция CHANGELOG; аннотированный тег `v0.15.0`
- [ ] Деплой: пересобрать образ (pg-client), создать том `backups`, выставить env
- [ ] `handoff.py validate`; STATE обновлён; PR + зелёный CI

## Ссылки

- ADR 042; аудит TASK-0062; образец релиза — TASK-0055
