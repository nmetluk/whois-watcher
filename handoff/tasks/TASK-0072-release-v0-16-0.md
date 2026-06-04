---
id: TASK-0072
title: Релиз v0.16.0 — Telegram WebApp (mini-app)
status: open
milestone: v0.16.0
adr: 043
area: docs
depends_on: [TASK-0071, TASK-0081, TASK-0082, TASK-0083]
branch: ""
owner: ""
session: ""
pr: ""
created: 2026-06-08
---

# TASK-0072 — Релиз v0.16.0 (ADR 043)

> Тело самодостаточно. Перед стартом:
> `git checkout main && git pull --rebase origin main`, затем `claim`.
> **Гейт:** аудит TASK-0071 — вердикт go; TASK-0066…0070 смержены; CI зелёный.

## Цель

Выпустить минорный релиз **v0.16.0** — Telegram WebApp (mini-app).

## Изменения по файлам

- `pyproject.toml` — bump `version` 0.15.0 → 0.16.0.
- `CHANGELOG.md` — секция `## [0.16.0]`: Telegram WebApp (6 экранов, PIN Voice),
  read/write `/api/webapp`, auth через initData. Deploy-нюансы: сборка фронта
  (`vite build`), nginx (static + `/api/webapp` proxy), новые env
  (webapp_origin, initData TTL), кнопка/меню запуска mini-app у бота.
- `STATE.md` — отметить релиз.

## Definition of Done

- [ ] Предусловия (0066–0070 в main, аудит go, CI зелёный)
- [ ] bump → 0.16.0; секция CHANGELOG; аннотированный тег `v0.16.0`
- [ ] Деплой: фронт-сборка + nginx + env + регистрация WebApp в боте (BotFather
  menu button / inline-кнопка)
- [ ] `handoff.py validate`; STATE обновлён; PR + зелёный CI

## Ссылки

- ADR 043; аудит TASK-0071; образец релиза — TASK-0063.
